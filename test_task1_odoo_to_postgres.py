#!/usr/bin/env python3
"""
Task 1 test (Odoo -> PostgreSQL only, no PLC write).

Flow:
1. (Optional) clear mo_batch table
2. Fetch MO list from Odoo
3. Save MO list to mo_batch
4. Verify saved rows in PostgreSQL
"""

import argparse
import asyncio
from typing import Any, Dict, List

from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.services.mo_batch_service import sync_mo_list_to_db
from app.services.odoo_auth_service import fetch_mo_list_detailed


def _print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _clear_mo_batch() -> int:
    db = SessionLocal()
    try:
        existing = db.execute(text("SELECT COUNT(*) FROM mo_batch")).scalar() or 0
        db.execute(text("DELETE FROM mo_batch"))
        db.commit()
        return int(existing)
    finally:
        db.close()


def _verify_saved_rows(limit: int = 10) -> List[TableSmoBatch]:
    db = SessionLocal()
    try:
        stmt = select(TableSmoBatch).order_by(TableSmoBatch.batch_no.asc()).limit(limit)
        return list(db.execute(stmt).scalars().all())
    finally:
        db.close()


async def run(limit: int, clear_first: bool) -> int:
    settings = get_settings()

    _print_header("TASK 1 TEST: ODOO -> POSTGRES")
    print(f"Odoo base URL : {settings.odoo_base_url}")
    print(f"Database URL  : {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")
    print(f"Fetch limit   : {limit}")
    print(f"Clear first   : {clear_first}")

    if clear_first:
        deleted = _clear_mo_batch()
        print(f"\n[STEP 1] Cleared mo_batch rows: {deleted}")
    else:
        print("\n[STEP 1] Skip clear mo_batch")

    print("\n[STEP 2] Fetch MO list from Odoo...")
    payload: Dict[str, Any] = await fetch_mo_list_detailed(limit=limit, offset=0)
    mo_list = (payload.get("result") or {}).get("data") or []

    if not isinstance(mo_list, list):
        print("❌ Invalid response format from Odoo (result.data is not a list)")
        return 1

    print(f"Fetched MO count: {len(mo_list)}")
    if not mo_list:
        print("⚠️ No MO returned from Odoo, nothing to save")
        return 0

    print("\n[STEP 3] Save to PostgreSQL (mo_batch)...")
    db = SessionLocal()
    try:
        synced = sync_mo_list_to_db(db, mo_list, commit=True)
    finally:
        db.close()

    print(f"Saved rows: {synced}")

    print("\n[STEP 4] Verify saved rows...")
    rows = _verify_saved_rows(limit=10)
    print(f"Rows currently in mo_batch (showing up to 10): {len(rows)}")

    for row in rows:
        print(
            f"  batch_no={row.batch_no} | mo_id={row.mo_id} | "
            f"finished_goods={row.finished_goods} | consumption={row.consumption}"
        )

    if synced > 0 and len(rows) > 0:
        print("\n✅ SUCCESS: Task 1 (Odoo -> PostgreSQL) test passed")
        return 0

    print("\n❌ FAILED: Data was not saved to mo_batch")
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Task 1 Odoo -> PostgreSQL flow")
    parser.add_argument("--limit", type=int, default=10, help="Number of MO records to fetch")
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear mo_batch before test",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(run(limit=args.limit, clear_first=not args.no_clear)))
