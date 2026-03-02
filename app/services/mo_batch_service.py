import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union, cast

import json

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

_LIQUID_NUMBER_TO_FIELDS = {
    114: ("component_lq_tetes_name", "consumption_lq_tetes"),
    115: ("component_lq_fml_name", "consumption_lq_fml"),
}

_EQUIPMENT_NUMBER_TO_FIELDS: Dict[int, tuple[str, str]] = {
    **{
        number: (f"component_silo_{letter}_name", f"consumption_silo_{letter}")
        for number, letter in _SILO_NUMBER_TO_LETTER.items()
    },
    **_LIQUID_NUMBER_TO_FIELDS,
}


def _normalize_equipment_key(raw: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(raw or "").strip().lower())


def _load_equipment_aliases() -> Dict[str, int]:
    aliases: Dict[str, int] = {}
    reference_path = Path(__file__).parent.parent / "reference" / "EQUIPMENT_REFERENCE.json"

    if not reference_path.exists():
        return aliases

    try:
        with open(reference_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        for item in data.get("raw_list", []):
            equipment_id = item.get("id")
            if not isinstance(equipment_id, int):
                continue

            for key in ("equipment", "equipment_code", "Product"):
                alias = _normalize_equipment_key(item.get(key))
                if alias:
                    aliases[alias] = equipment_id

            if equipment_id == 114:
                aliases.setdefault("lqtetes", 114)
                aliases.setdefault("lqtestes", 114)
                aliases.setdefault("lqtest", 114)
            if equipment_id == 115:
                aliases.setdefault("lqfml", 115)

    except Exception:
        return aliases

    return aliases


_EQUIPMENT_ALIAS_TO_NUMBER = _load_equipment_aliases()


def _extract_silo_number(equipment: Optional[Dict[str, Any]]) -> Optional[int]:
    if not equipment:
        return None

    code = str(equipment.get("code") or "")
    name = str(equipment.get("name") or "")
    combined = f"{code} {name}".lower()

    match = re.search(r"(\d{3})", combined)
    if match:
        number = int(match.group(1))
        if number in _EQUIPMENT_NUMBER_TO_FIELDS:
            return number

    for candidate in (_normalize_equipment_key(code), _normalize_equipment_key(name)):
        mapped = _EQUIPMENT_ALIAS_TO_NUMBER.get(candidate)
        if mapped in _EQUIPMENT_NUMBER_TO_FIELDS:
            return mapped

    return None


def _apply_component_to_batch(batch: TableSmoBatch, component: Dict[str, Any]) -> None:
    silo_number = _extract_silo_number(component.get("equipment"))
    if not silo_number:
        return

    component_name_field, consumption_field = _EQUIPMENT_NUMBER_TO_FIELDS[silo_number]

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

    for component_name_field, consumption_field in _EQUIPMENT_NUMBER_TO_FIELDS.values():
        setattr(batch, component_name_field, None)
        setattr(batch, consumption_field, None)

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

            batch_data["lq114"] = getattr(batch, "lq114", None) or 114
            batch_data["lq115"] = getattr(batch, "lq115", None) or 115
            batch_data["component_lq_tetes_name"] = getattr(batch, "component_lq_tetes_name", None)
            batch_data["component_lq_fml_name"] = getattr(batch, "component_lq_fml_name", None)
            batch_data["consumption_lq_tetes"] = getattr(batch, "consumption_lq_tetes", None)
            batch_data["consumption_lq_fml"] = getattr(batch, "consumption_lq_fml", None)

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
