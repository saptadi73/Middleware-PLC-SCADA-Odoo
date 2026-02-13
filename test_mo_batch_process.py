"""
End-to-end MO batch process test.
Steps:
1. Clear mo_batch table
2. Fetch mo_list detailed and fill mo_batch if empty
3. Write mo_batch queue to PLC memory
4. Read PLC memory and update mo_batch based on MO_ID
5. Move finished MO (status_manufacturing=True) to mo_histories
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.models.tablesmo_history import TableSmoHistory
from app.services.mo_batch_service import (
    clear_mo_batch_table,
    is_mo_batch_empty,
    move_finished_batches_to_history,
    sync_mo_list_to_db,
    write_mo_batch_queue_to_plc,
)
from app.services.odoo_auth_service import fetch_mo_list_detailed
from app.services.plc_sync_service import get_plc_sync_service


def _print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _fetch_first_batch(db) -> TableSmoBatch | None:
    result = db.execute(select(TableSmoBatch).order_by(TableSmoBatch.batch_no))
    return result.scalars().first()


async def main() -> None:
    _print_header("MO BATCH PROCESS TEST")
    print("This test will execute:")
    print("1. Clear mo_batch")
    print("2. Fetch mo_list and fill mo_batch if empty")
    print("3. Write mo_batch queue to PLC")
    print("4. Read PLC and sync to mo_batch")
    print("5. Move finished MO to mo_histories")
    print("\nPrerequisites:")
    print("- Database migration applied (alembic upgrade head)")
    print("- PLC reachable (for steps 3-4)")
    print("- Odoo API reachable (for step 2)")
    print("\nPress Ctrl+C to cancel or Enter to continue...")
    input()

    settings = get_settings()

    with SessionLocal() as db:
        _print_header("STEP 1 - Clear mo_batch")
        deleted_count = clear_mo_batch_table(db)
        print(f"Cleared mo_batch rows: {deleted_count}")

        _print_header("STEP 2 - Fetch and fill mo_batch")
        if is_mo_batch_empty(db):
            payload = await fetch_mo_list_detailed(
                limit=settings.sync_batch_limit,
                offset=0,
            )
            mo_list = payload.get("result", {}).get("data", [])

            if not mo_list:
                print("No MO data returned from Odoo. Abort.")
                return

            inserted = sync_mo_list_to_db(db, mo_list)
            print(f"Inserted MO rows: {inserted}")
        else:
            print("mo_batch already has data. Skipping fetch.")

        first_batch = _fetch_first_batch(db)
        if not first_batch:
            print("No batch data available after sync. Abort.")
            return

        _print_header("STEP 3 - Write mo_batch queue to PLC")
        written = write_mo_batch_queue_to_plc(db, start_slot=1, limit=30)
        print(f"Batches written to PLC: {written}")

    _print_header("STEP 4 - Sync PLC data to mo_batch")
    plc_sync_service = get_plc_sync_service()
    sync_result = plc_sync_service.sync_from_plc()
    print(f"PLC sync result: {sync_result}")

    with SessionLocal() as db:
        _print_header("STEP 5 - Move finished MO to history")
        moved = move_finished_batches_to_history(db)

        if moved == 0 and sync_result.get("mo_id"):
            print("No finished MO found. Marking current MO as finished for testing.")
            batch = (
                db.query(TableSmoBatch)
                .filter(TableSmoBatch.mo_id == sync_result.get("mo_id"))
                .first()
            )
            if batch:
                batch.status_manufacturing = True  # type: ignore
                db.commit()
                moved = move_finished_batches_to_history(db)

        print(f"Moved to mo_histories: {moved}")

        history_count = db.query(TableSmoHistory).count()
        remaining_count = db.query(TableSmoBatch).count()
        print(f"Total history rows: {history_count}")
        print(f"Remaining mo_batch rows: {remaining_count}")

    _print_header("TEST COMPLETE")
    print("MO batch process test completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
