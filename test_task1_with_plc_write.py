#!/usr/bin/env python3
"""
Test Task 1 dengan WRITE ke PLC (bypass pre-handshake check).

Flow:
1. Clear queue (mo_batch)
2. Fetch dari Odoo, stage ke DB (deferred commit)
3. WRITE ke PLC tanpa pre-check D7076 (khusus test)
4. Commit DB jika write sukses penuh
5. Verify queue hasil test
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.services.mo_batch_service import _to_float, sync_mo_list_to_db
from app.services.odoo_auth_service import fetch_mo_list_detailed
from app.services.plc_handshake_service import get_handshake_service
from app.services.plc_write_service import get_plc_write_service


def print_section(title: str) -> None:
    print(f"\n{'=' * 90}")
    print(f"  {title}")
    print(f"{'=' * 90}\n")


def show_queue() -> int:
    """Show current queue in mo_batch."""
    db = SessionLocal()
    try:
        stmt = select(TableSmoBatch).order_by(TableSmoBatch.batch_no)
        batches = db.execute(stmt).scalars().all()

        if not batches:
            print("  [OK] Queue: EMPTY")
            return 0

        print(f"  [OK] Queue: {len(batches)} batch(es)")
        print(f"\n  {'Batch':>7} {'MO ID':>18} {'Status':>10} {'Finished Goods':>35}")
        print(f"  {'-' * 7} {'-' * 18} {'-' * 10} {'-' * 35}")

        for batch in batches:
            status = "COMPLETED" if batch.status_manufacturing else "ACTIVE"
            fg = (batch.finished_goods or "N/A")[:35]
            mo_id = (batch.mo_id or "N/A")[:18]
            print(f"  {batch.batch_no:>7} {mo_id:>18} {status:>10} {fg:>35}")

        return len(batches)
    finally:
        db.close()


def clear_database() -> None:
    """Clear mo_batch table."""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
            count = result.scalar() or 0

            if count > 0:
                conn.execute(text("DELETE FROM mo_batch"))
                conn.commit()
                print(f"  [OK] Cleared {count} batch(es) from mo_batch")
            else:
                print("  [OK] mo_batch already empty")
    finally:
        engine.dispose()


def _build_batch_data_from_row(batch: TableSmoBatch) -> dict:
    batch_data = {
        "mo_id": batch.mo_id,
        "consumption": _to_float(batch.consumption),
        "equipment_id_batch": batch.equipment_id_batch,
        "finished_goods": batch.finished_goods,
        "status_manufacturing": bool(batch.status_manufacturing),
        "status_operation": bool(batch.status_operation),
        "actual_weight_quantity_finished_goods": _to_float(
            batch.actual_weight_quantity_finished_goods
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
    return batch_data


def write_queue_to_plc_without_handshake_check(db: Session, limit: int) -> int:
    plc_service = get_plc_write_service()
    handshake = get_handshake_service()
    written = 0

    batches = db.query(TableSmoBatch).order_by(TableSmoBatch.batch_no).limit(limit).all()
    for plc_slot, batch in enumerate(batches, start=1):
        if plc_slot > 30:
            break

        batch_data = _build_batch_data_from_row(batch)
        plc_service.write_mo_batch_to_plc(
            batch_data,
            batch_number=plc_slot,
            skip_handshake_check=True,
        )
        written += 1

    if written > 0:
        handshake.reset_write_area_status()

    return written


async def main() -> None:
    settings = get_settings()

    print("\n")
    print("=" * 90)
    print("TEST TASK 1 - WITH PLC WRITE (BYPASS PRE-HANDSHAKE CHECK)")
    print("=" * 90)

    print_section("STEP 1: Check Initial Queue")
    show_queue()

    print_section("STEP 2: Clear mo_batch Table")
    clear_database()
    show_queue()

    print_section("STEP 3: Fetch from Odoo + Stage DB + Write PLC (no pre-handshake)")

    payload = await fetch_mo_list_detailed(limit=settings.sync_batch_limit, offset=0)
    result = payload.get("result", {})
    mo_list = result.get("data", [])
    if not mo_list:
        print("  [FAIL] No MO data returned from Odoo")
        return

    if len(mo_list) > 30:
        print("  [WARN] Odoo returned >30 MOs, only first 30 will be used")
        mo_list = mo_list[:30]

    db = SessionLocal()
    try:
        staged = sync_mo_list_to_db(db, mo_list, commit=False)
        print(f"  [OK] Staged {staged} batch(es) to mo_batch (not committed)")

        written = write_queue_to_plc_without_handshake_check(db=db, limit=staged)
        print(f"  [OK] PLC write done (no pre-handshake check): {written} batch(es)")

        if written != staged:
            raise RuntimeError(
                f"Partial PLC write detected (staged={staged}, written={written})."
            )

        db.commit()
        print("  [OK] DB commit successful")
    except Exception as exc:
        db.rollback()
        print(f"  [FAIL] Task 1 write failed: {exc}")
        import traceback

        traceback.print_exc()
        return
    finally:
        db.close()

    print_section("STEP 4: Verify Results in mo_batch")
    count = show_queue()

    print_section("SUMMARY")

    if count > 0:
        print("  [OK] SUCCESS")
        print("\n  Task 1 successfully:")
        print(f"    1. [OK] Fetched {count} batch(es) from Odoo")
        print("    2. [OK] Saved to mo_batch database")
        print("    3. [OK] Wrote to PLC memory without pre-handshake check")
    else:
        print("  [FAIL] FAILED - No batches in mo_batch")


if __name__ == "__main__":
    asyncio.run(main())
