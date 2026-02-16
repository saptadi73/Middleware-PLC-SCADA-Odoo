"""
Live test: simulate Task 3 Odoo update using real batch data from DB.

Usage:
  python test_task3_live.py --mo-id WH/MO/00001
"""

import argparse
import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.models.tablesmo_history import TableSmoHistory
from app.services.odoo_consumption_service import get_consumption_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_task3_live")


def _build_batch_data(row: Any) -> Dict[str, Any]:
    batch_data: Dict[str, Any] = {
        "status_manufacturing": 1,
        "actual_weight_quantity_finished_goods": float(
            row.actual_weight_quantity_finished_goods or 0.0
        ),
    }

    # Prefer actual consumption if present; fallback to planned consumption
    for letter in "abcdefghijklm":
        actual_field = f"actual_consumption_silo_{letter}"
        planned_field = f"consumption_silo_{letter}"
        value = None
        if hasattr(row, actual_field):
            value = getattr(row, actual_field)
        if (value is None or value == 0) and hasattr(row, planned_field):
            value = getattr(row, planned_field)
        if value is not None and value > 0:
            batch_data[f"consumption_silo_{letter}"] = float(value)

    return batch_data


def _find_batch(mo_id: str) -> Optional[Any]:
    db = SessionLocal()
    try:
        result = db.execute(
            select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
        )
        row = result.scalar_one_or_none()
        if row:
            logger.info("Found mo_batch for %s (batch_no=%s)", mo_id, row.batch_no)
            return row

        result = db.execute(
            select(TableSmoHistory).where(TableSmoHistory.mo_id == mo_id)
        )
        row = result.scalar_one_or_none()
        if row:
            logger.info("Found mo_histories for %s (batch_no=%s)", mo_id, row.batch_no)
            return row
        return None
    finally:
        db.close()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mo-id", required=True, help="MO ID, e.g. WH/MO/00001")
    args = parser.parse_args()

    mo_id = args.mo_id.strip()
    row = _find_batch(mo_id)
    if not row:
        logger.error("MO %s not found in mo_batch or mo_histories", mo_id)
        return 1

    batch_data = _build_batch_data(row)
    logger.info("Prepared batch_data keys: %s", list(batch_data.keys()))

    service = get_consumption_service()
    result = await service.process_batch_consumption(
        mo_id=mo_id,
        equipment_id=str(getattr(row, "equipment_id_batch", "PLC01") or "PLC01"),
        batch_data=batch_data,
    )
    logger.info("Result: %s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
