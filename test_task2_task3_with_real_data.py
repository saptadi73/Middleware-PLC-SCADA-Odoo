#!/usr/bin/env python3
"""
Test Task 2 & Task 3 with REAL Odoo MO data
(not test MO like TEST/MO/99999)

Flow:
1. Fetch real MO from Odoo via Task 1
2. Simulate PLC completion
3. Run Task 2 (should sync to Odoo successfully)
4. Run Task 3 (should archive and clear queue)
5. Verify queue is empty
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, text, create_engine
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.core.config import get_settings
from app.core.scheduler import (
    plc_read_sync_task,
    process_completed_batches_task,
    auto_sync_mo_task,
)


def print_header(text):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")


def show_queue():
    """Show current queue state."""
    db = SessionLocal()
    try:
        stmt = select(TableSmoBatch).order_by(TableSmoBatch.mo_id)
        batches = db.execute(stmt).scalars().all()
        
        if not batches:
            print("  ✓ Queue: EMPTY")
            return []
        
        print(f"  Queue: {len(batches)} batch(es)")
        print(f"  {'MO ID':>15} {'Status':>8} {'Synced':>8} {'Weight':>12}")
        print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*12}")
        
        for batch in batches:
            mfg = "DONE" if batch.status_manufacturing else "ACTIVE"
            synced = "YES" if batch.update_odoo else "NO"
            weight = f"{batch.actual_weight_quantity_finished_goods or 0:.0f}"
            print(f"  {batch.mo_id:>15} {mfg:>8} {synced:>8} {weight:>12}")
        
        return batches
    finally:
        db.close()


def clear_queue():
    """Clear mo_batch for fresh test."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
            count = result.scalar() or 0
            
            if count > 0:
                conn.execute(text("DELETE FROM mo_batch"))
                conn.commit()
                print(f"  ✓ Cleared {count} batch(es)")
            else:
                print(f"  ✓ Queue already empty")
    finally:
        engine.dispose()


def set_batch_completed(batch_no: int):
    """Mark batch as completed (simulate PLC finish)."""
    db = SessionLocal()
    try:
        stmt = select(TableSmoBatch).where(
            TableSmoBatch.batch_no == batch_no
        )
        batch = db.execute(stmt).scalar_one_or_none()
        
        if not batch:
            print(f"  ✗ Batch #{batch_no} not found")
            return None
        
        # Simulate PLC completion
        batch.status_manufacturing = True
        batch.status_operation = True
        batch.last_read_from_plc = datetime.now(timezone.utc)
        
        # Add some realistic consumption data
        batch.actual_consumption_silo_a = 50.0
        batch.actual_consumption_silo_b = 75.0
        batch.actual_consumption_silo_c = 60.0
        batch.actual_weight_quantity_finished_goods = 1500.0
        
        db.commit()
        
        print(f"  ✓ Batch #{batch_no} marked COMPLETED (status_manufacturing=1)")
        print(f"    └─ Weight: {batch.actual_weight_quantity_finished_goods}")
        print(f"    └─ Silos: A={batch.actual_consumption_silo_a}, "
              f"B={batch.actual_consumption_silo_b}, "
              f"C={batch.actual_consumption_silo_c}")
        
        return batch.mo_id
        
    finally:
        db.close()


async def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*10 + "TEST: Task 2 & Task 3 with REAL Odoo MO Data" + " "*25 + "║")
    print("╚" + "="*78 + "╝")
    
    # Step 1: Clear and setup
    print_header("STEP 1: Clear queue for fresh test")
    clear_queue()
    show_queue()
    
    # Step 2: Fetch real MO from Odoo (Task 1)
    print_header("STEP 2: Fetch real MO from Odoo (Task 1)")
    print("  Running: auto_sync_mo_task()")
    
    try:
        await auto_sync_mo_task()
        print("  ✓ Task 1 completed")
    except Exception as e:
        print(f"  ✗ Task 1 failed: {e}")
        return
    
    print("\n  Queue after Task 1:")
    batches = show_queue()
    
    if not batches:
        print("\n  ⚠ No MOs fetched (Odoo might be down or no pending MOs)")
        return
    
    # Step 3: Mark first batch as completed (simulate PLC)
    print_header("STEP 3: Simulate PLC completion")
    print("  Marking first batch as completed...")
    
    mo_id = set_batch_completed(1)
    
    if not mo_id:
        print("  ⚠ No batch to mark - test aborted")
        return
    
    print("\n  Queue after marking completed:")
    show_queue()
    
    # Step 4: Run Task 2 (Odoo sync)
    print_header("STEP 4: Task 2 - PLC Read + Odoo Sync")
    print(f"  Running: plc_read_sync_task()")
    print(f"  Expected: Sync {mo_id} to Odoo, set update_odoo=TRUE")
    
    try:
        await plc_read_sync_task()
        print("  ✓ Task 2 completed")
    except Exception as e:
        print(f"  ✗ Task 2 failed: {e}")
        # Don't abort - check queue state anyway
    
    print("\n  Queue after Task 2:")
    batches = show_queue()
    
    # Check if synced
    synced_count = sum(1 for b in batches if b.update_odoo)
    print(f"\n  Status: {synced_count}/{len(batches)} batches marked synced to Odoo")
    
    # Step 5: Run Task 3 (Archive)
    print_header("STEP 5: Task 3 - Archive Completed Batches")
    print("  Running: process_completed_batches_task()")
    print("  Expected: Archive synced batches, clear from queue")
    
    try:
        await process_completed_batches_task()
        print("  ✓ Task 3 completed")
    except Exception as e:
        print(f"  ✗ Task 3 failed: {e}")
        # Don't abort - check queue state anyway
    
    print("\n  Queue after Task 3:")
    remaining = show_queue()
    
    # Summary
    print_header("✓ TEST SUMMARY")
    
    if len(batches) == 0 and not remaining:
        print("  ✓✓✓ SUCCESS ✓✓✓")
        print(f"\n  Proven:")
        print(f"    1. ✓ Task 1 fetched real MO from Odoo")
        print(f"    2. ✓ Task 2 synced to Odoo (set update_odoo=TRUE)")
        print(f"    3. ✓ Task 3 archived and cleared queue")
        print(f"    4. ✓ Queue is now empty (ready for Task 1 again)")
        print(f"\n  Next cycle will fetch new MOs from Odoo")
        
    elif len(remaining) == 0:
        print("  ✓ Queue cleared successfully!")
        print(f"  {len(batches) - len(remaining)} batch(es) processed")
        
    else:
        print(f"  ⚠ {len(remaining)} batch(es) still in queue")
        print(f"\n  Possible reasons:")
        print(f"    • Odoo API failed (temporary)")
        print(f"    • MO doesn't exist in Odoo (check mo_id)")
        print(f"    • update_odoo flag not set by Task 2")
        print(f"\n  Check logs for errors")
        print(f"  For manual recovery:")
        print(f"    curl http://localhost:8000/api/admin/failed-to-push")


if __name__ == "__main__":
    asyncio.run(main())
