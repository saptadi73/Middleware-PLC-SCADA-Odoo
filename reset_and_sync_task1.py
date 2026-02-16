#!/usr/bin/env python3
"""
Script untuk reset database dan jalankan Task 1 auto-sync dari Odoo.
"""

import asyncio
import logging
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.core.scheduler import auto_sync_mo_task

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_mo_batch():
    """Clear mo_batch table."""
    print("\n" + "="*80)
    print("STEP 1: Clear mo_batch Table")
    print("="*80)
    
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            # Get current count
            result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
            count = result.scalar() or 0
            
            if count > 0:
                print(f"  Clearing {count} records from mo_batch...")
                conn.execute(text("DELETE FROM mo_batch"))
                conn.commit()
                print(f"  ✓ Cleared successfully")
            else:
                print(f"  ✓ mo_batch already empty")
    finally:
        engine.dispose()


async def run_task1_sync():
    """Run Task 1 auto-sync."""
    print("\n" + "="*80)
    print("STEP 2: Run Task 1 Auto-Sync from Odoo")
    print("="*80)
    
    try:
        await auto_sync_mo_task()
        print("\n  ✓ Task 1 completed")
    except Exception as e:
        logger.exception(f"Task 1 failed: {e}")
        raise


def verify_synced_batches():
    """Verify batches were synced."""
    print("\n" + "="*80)
    print("STEP 3: Verify Synced Batches")
    print("="*80)
    
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT batch_no, mo_id, finished_goods, status_manufacturing, update_odoo
                FROM mo_batch
                ORDER BY batch_no
            """))
            
            batches = result.fetchall()
            print(f"\n  Total batches synced: {len(batches)}")
            
            if batches:
                print("\n  Batch Details:")
                print(f"  {'Batch':>8} {'MO ID':>15} {'Product':>20} {'Status':>10} {'Updated':>10}")
                print(f"  {'-'*8} {'-'*15} {'-'*20} {'-'*10} {'-'*10}")
                
                for batch in batches:
                    batch_no, mo_id, finished_goods, status_mfg, update_odoo = batch
                    status = "ACTIVE" if not status_mfg else "COMPLETE"
                    updated = "YES" if update_odoo else "NO"
                    product = (finished_goods or "N/A")[:20]
                    print(f"  {batch_no:>8} {mo_id:>15} {product:>20} {status:>10} {updated:>10}")
            
    finally:
        engine.dispose()


async def main():
    print("\n\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "Reset Database & Run Task 1 Auto-Sync" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # Step 1: Clear mo_batch
        clear_mo_batch()
        
        # Step 2: Run Task 1
        await run_task1_sync()
        
        # Step 3: Verify
        verify_synced_batches()
        
        print("\n" + "="*80)
        print("✓ COMPLETE - Ready to test Task 2 with active MOs")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.exception(f"Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
