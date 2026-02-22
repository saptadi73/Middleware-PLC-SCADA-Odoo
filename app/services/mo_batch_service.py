import re
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Union, cast

from sqlalchemy.orm import Session

from app.models.tablesmo_batch import TableSmoBatch
from app.models.tablesmo_history import TableSmoHistory
from app.services.plc_handshake_service import get_handshake_service
from app.services.plc_write_service import get_plc_write_service


NumericValue = Union[Decimal, float, int]


def _to_float(value: Optional[NumericValue]) -> float:
    if value is None:
        return 0.0
    return float(value)


_SILO_NUMBER_TO_LETTER = {
    101: "a",
    102: "b",
    103: "c",
    104: "d",
    105: "e",
    106: "f",
    107: "g",
    108: "h",
    109: "i",
    110: "j",
    111: "k",
    112: "l",
    113: "m",
}


def _extract_silo_number(equipment: Optional[Dict[str, Any]]) -> Optional[int]:
    if not equipment:
        return None

    code = str(equipment.get("code") or "")
    name = str(equipment.get("name") or "")
    combined = f"{code} {name}".lower()

    match = re.search(r"(\d{3})", combined)
    if not match:
        return None

    number = int(match.group(1))
    if number in _SILO_NUMBER_TO_LETTER:
        return number
    return None


def _apply_component_to_batch(batch: TableSmoBatch, component: Dict[str, Any]) -> None:
    silo_number = _extract_silo_number(component.get("equipment"))
    if not silo_number:
        return

    letter = _SILO_NUMBER_TO_LETTER[silo_number]
    component_name_field = f"component_silo_{letter}_name"
    consumption_field = f"consumption_silo_{letter}"

    component_name = component.get("product_name")
    consumption_value = component.get("to_consume")
    if consumption_value is None:
        consumption_value = component.get("consumed")

    setattr(batch, component_name_field, component_name)
    setattr(batch, consumption_field, consumption_value)


def _upsert_batch(db: Session, mo_data: Dict[str, Any], batch_no: int) -> TableSmoBatch:
    mo_id = mo_data.get("mo_id")
    equipment = mo_data.get("equipment") or {}

    batch = (
        db.query(TableSmoBatch)
        .filter(TableSmoBatch.mo_id == mo_id)
        .one_or_none()
    )

    if batch is None:
        batch = TableSmoBatch(mo_id=mo_id)
        db.add(batch)

    # Assign required fields (all non-nullable in model)
    batch.batch_no = batch_no  # type: ignore[assignment]
    batch.consumption = float(mo_data.get("quantity") or 0)  # type: ignore[assignment]
    batch.equipment_id_batch = str(equipment.get("code") or "")  # type: ignore[assignment]
    batch.finished_goods = str(mo_data.get("product_name") or "")  # type: ignore[assignment]

    for letter in _SILO_NUMBER_TO_LETTER.values():
        setattr(batch, f"component_silo_{letter}_name", None)
        setattr(batch, f"consumption_silo_{letter}", None)

    for component in mo_data.get("components_consumption", []):
        _apply_component_to_batch(batch, component)

    return batch


def sync_mo_list_to_db(
    db: Session,
    mo_list: Iterable[Dict[str, Any]],
    commit: bool = True,
) -> int:
    count = 0
    for index, mo_data in enumerate(mo_list, start=1):
        _upsert_batch(db, mo_data, index)
        count += 1

    if commit:
        db.commit()
    else:
        db.flush()
    return count


def clear_mo_batch_table(db: Session) -> int:
    deleted_count = db.query(TableSmoBatch).count()
    if deleted_count == 0:
        return 0

    db.query(TableSmoBatch).delete()
    db.commit()
    return deleted_count


def is_mo_batch_empty(db: Session) -> bool:
    return db.query(TableSmoBatch).count() == 0


def write_mo_batch_queue_to_plc(
    db: Session,
    start_slot: int = 1,
    limit: int = 30,
) -> int:
    if start_slot < 1 or start_slot > 30:
        raise ValueError(f"start_slot must be 1-30, got {start_slot}")

    if limit < 1:
        return 0

    batches = (
        db.query(TableSmoBatch)
        .order_by(TableSmoBatch.batch_no)
        .limit(limit)
        .all()
    )

    plc_service = get_plc_write_service()
    handshake = get_handshake_service()

    plc_ready = handshake.check_write_area_status()
    if not plc_ready:
        raise RuntimeError(
            "Cannot write batch queue: PLC handshake not ready (D7076=0). "
            "Wait for PLC to read previous data first."
        )

    written = 0
    plc_slot = start_slot
    try:
        for batch in batches:
            if plc_slot > 30:
                break

            consumption_val = cast(Optional[NumericValue], batch.consumption)
            actual_weight_val = cast(
                Optional[NumericValue], batch.actual_weight_quantity_finished_goods
            )

            batch_data = {
                "mo_id": batch.mo_id,
                "consumption": _to_float(consumption_val),
                "equipment_id_batch": batch.equipment_id_batch,
                "finished_goods": batch.finished_goods,
                "status_manufacturing": bool(batch.status_manufacturing),
                "status_operation": bool(batch.status_operation),
                "actual_weight_quantity_finished_goods": (
                    _to_float(actual_weight_val)
                ),
            }

            for letter in "abcdefghijklm":
                batch_data[f"silo_{letter}"] = getattr(batch, f"silo_{letter}", None)
                batch_data[f"component_silo_{letter}_name"] = getattr(
                    batch, f"component_silo_{letter}_name", None
                )
                batch_data[f"consumption_silo_{letter}"] = getattr(
                    batch, f"consumption_silo_{letter}", None
                )

            plc_service.write_mo_batch_to_plc(
                batch_data,
                batch_number=plc_slot,
                skip_handshake_check=True,
            )
            written += 1
            plc_slot += 1
    finally:
        # If any batch has been written, mark WRITE area as unread by PLC.
        if written > 0:
            handshake.reset_write_area_status()

    return written


def move_finished_batches_to_history(db: Session) -> int:
    finished_batches: List[TableSmoBatch] = (
        db.query(TableSmoBatch)
        .filter(TableSmoBatch.status_manufacturing.is_(True))
        .all()
    )

    if not finished_batches:
        return 0

    history_columns = [column.name for column in TableSmoHistory.__table__.columns]

    for batch in finished_batches:
        history = TableSmoHistory()
        for column_name in history_columns:
            if hasattr(batch, column_name):
                setattr(history, column_name, getattr(batch, column_name))

        # Ensure actual weight from PLC is copied to history
        history.actual_weight_quantity_finished_goods = (
            batch.actual_weight_quantity_finished_goods
        )

        db.add(history)
        db.delete(batch)

    db.commit()
    return len(finished_batches)
