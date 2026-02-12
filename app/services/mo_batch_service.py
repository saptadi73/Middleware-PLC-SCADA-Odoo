import re
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.tablesmo_batch import TableSmoBatch


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

    for letter in _SILO_NUMBER_TO_LETTER.values():
        setattr(batch, f"component_silo_{letter}_name", None)
        setattr(batch, f"consumption_silo_{letter}", None)

    for component in mo_data.get("components_consumption", []):
        _apply_component_to_batch(batch, component)

    return batch


def sync_mo_list_to_db(db: Session, mo_list: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for index, mo_data in enumerate(mo_list, start=1):
        _upsert_batch(db, mo_data, index)
        count += 1

    db.commit()
    return count
