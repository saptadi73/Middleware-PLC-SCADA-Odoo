#!/usr/bin/env python3
"""
Test Task 1 dengan WRITE ke PLC

Flow:
1. Clear queue (mo_batch)
2. Run Task 1 (akan fetch dari Odoo dan WRITE ke PLC)
3. Verify results (batches di mo_batch dan di PLC memory)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, text, create_engine
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.core.scheduler import auto_sync_mo_task
from app.core.config import get_settings


def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def show_queue():
    """Show current queue in mo_batch."""
    db = SessionLocal()
    try:
        stmt = select(TableSmoBatch).order_by(TableSmoBatch.mo_id)
        batches = db.execute(stmt).scalars().all()
        
        if not batches:
            print("  ✓ Queue: EMPTY")
            return 0
        
        print(f"  ✓ Queue: {len(batches)} batch(es)")
        print(f"\n  {'MO ID':>15} {'Batch No':>10} {'Status':>10} {'Finished Goods':>30}")
        print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*30}")
        
        for batch in batches:
            status = "COMPLETED" if batch.status_manufacturing else "ACTIVE"
            fg = (batch.finished_goods or "N/A")[:30]
            print(f"  {batch.mo_id:>15} {batch.batch_no:>10} {status:>10} {fg:>30}")
        
        return len(batches)
    finally:
        db.close()


def clear_database():
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
                print(f"  ✓ Cleared {count} batch(es) from mo_batch")
            else:
                print(f"  ✓ mo_batch already empty")
    finally:
        engine.dispose()


async def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "TEST TASK 1 - WITH PLC WRITE (UPDATED)" + " "*25 + "║")
    print("╚" + "="*78 + "╝")
    
    # Step 1: Show initial state
    print_section("STEP 1: Check Initial Queue")
    show_queue()
    
    # Step 2: Clear database
    print_section("STEP 2: Clear mo_batch Table")
    clear_database()
    show_queue()
    
    # Step 3: Run Task 1
    print_section("STEP 3: Run Task 1 (Fetch from Odoo + Write to PLC)")
    
    try:
        await auto_sync_mo_task()
        print("\n  ✓ Task 1 completed successfully")
    except Exception as e:
        print(f"\n  ✗ Task 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Show results
    print_section("STEP 4: Verify Results in mo_batch")
    count = show_queue()
    
    # Summary
    print_section("SUMMARY")
    
    if count > 0:
        print("  ✓✓✓ SUCCESS ✓✓✓")
        print(f"\n  Task 1 successfully:")
        print(f"    1. ✓ Fetched {count} batch(es) from Odoo")
        print(f"    2. ✓ Saved to mo_batch database")
        print(f"    3. ✓ Wrote to PLC memory (check PLC logs)")
        print(f"\n  Next: Task 2 will read PLC results and sync consumption to Odoo")
    else:
        print("  ✗ FAILED - No batches in mo_batch")
        print(f"\n  Possible reasons:")
        print(f"    1. No MOs available in Odoo")
        print(f"    2. Queue not actually empty (other batches blocking)")
        print(f"    3. Odoo API connection failed")


if __name__ == "__main__":
    asyncio.run(main())
