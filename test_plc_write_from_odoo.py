"""
Test script: write PLC directly from Odoo MO list.
- Clear mo_batch table first
- Fetch MO list from Odoo
- Map MO data to PLC fields
- Write to PLC using PLCWriteService
"""
import asyncio
import logging
import re
from typing import Any, Dict, Optional

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.odoo_auth_service import fetch_mo_list_detailed
from app.services.plc_write_service import get_plc_write_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def _build_mo_batch_data(mo_data: Dict[str, Any]) -> Dict[str, Any]:
    equipment = mo_data.get("equipment") or {}

    mo_batch_data: Dict[str, Any] = {
        "mo_id": mo_data.get("mo_id") or "",
        "consumption": float(mo_data.get("quantity") or 0),
        "equipment_id_batch": str(equipment.get("code") or ""),
        "finished_goods": str(mo_data.get("product_name") or ""),
        "status_manufacturing": bool(mo_data.get("status_manufacturing", False)),
        "status_operation": bool(mo_data.get("status_operation", False)),
        "actual_weight_quantity_finished_goods": float(mo_data.get("actual_weight_quantity_finished_goods") or 0),
    }

    # Defaults for silo IDs (A-M -> 101-113)
    for idx, letter in enumerate("abcdefghijklm"):
        mo_batch_data[f"silo_{letter}"] = 101 + idx
        mo_batch_data[f"component_silo_{letter}_name"] = None
        mo_batch_data[f"consumption_silo_{letter}"] = None

    # Map components consumption to silo fields
    for component in mo_data.get("components_consumption", []):
        silo_number = _extract_silo_number(component.get("equipment"))
        if not silo_number:
            continue

        letter = _SILO_NUMBER_TO_LETTER[silo_number]
        component_name = component.get("product_name")
        consumption_value = component.get("to_consume")
        if consumption_value is None:
            consumption_value = component.get("consumed")

        mo_batch_data[f"component_silo_{letter}_name"] = component_name
        mo_batch_data[f"consumption_silo_{letter}"] = consumption_value

    return mo_batch_data


def _clear_mo_batch_table() -> int:
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT COUNT(*) FROM mo_batch"))
        count = result.scalar() or 0
        db.execute(text("DELETE FROM mo_batch"))
        db.commit()
        return count
    finally:
        db.close()


async def main() -> None:
    settings = get_settings()

    logger.info("Clearing mo_batch table before testing...")
    deleted_count = _clear_mo_batch_table()
    logger.info("mo_batch cleared. Previous rows: %s", deleted_count)

    logger.info("Fetching MO list from Odoo...")
    payload = await fetch_mo_list_detailed(
        limit=settings.sync_batch_limit,
        offset=0,
    )

    result = payload.get("result", {})
    mo_list = result.get("data", [])
    if not mo_list:
        logger.warning("No MO data returned from Odoo.")
        return

    logger.info("Fetched %s MO items from Odoo", len(mo_list))

    service = get_plc_write_service()

    for idx, mo_data in enumerate(mo_list, start=1):
        if idx > 30:
            logger.warning("Only 30 PLC slots available. Stopping at item 30.")
            break

        mo_batch_data = _build_mo_batch_data(mo_data)
        logger.info("Writing MO %s to PLC slot BATCH%02d", mo_batch_data.get("mo_id"), idx)
        service.write_mo_batch_to_plc(mo_batch_data, batch_number=idx)

    logger.info("PLC write from Odoo completed.")


if __name__ == "__main__":
    asyncio.run(main())
