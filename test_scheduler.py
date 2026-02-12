"""
Test script untuk verifikasi auto-sync scheduler behavior
"""
import time
from sqlalchemy import create_engine, text

from app.core.config import get_settings


def test_scheduler_logic():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    print("=" * 70)
    print("Testing Auto-Sync Scheduler Logic")
    print("=" * 70)
    
    # Tampilkan config
    print("\nConfiguration from .env:")
    print(f"  ENABLE_AUTO_SYNC       : {settings.enable_auto_sync}")
    print(f"  SYNC_INTERVAL_MINUTES  : {settings.sync_interval_minutes}")
    print(f"  SYNC_BATCH_LIMIT       : {settings.sync_batch_limit}")
    
    # Cek status table
    print("\nCurrent mo_batch table status:")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
        count = result.scalar()
        print(f"  Total records: {count}")
        
        if count > 0:
            print("\n  ⚠️  Table HAS DATA → Scheduler will SKIP sync")
            print("      (Waiting for PLC to complete all batches)")
            
            # Sample data
            result = conn.execute(
                text("SELECT batch_no, mo_id FROM mo_batch ORDER BY batch_no LIMIT 3")
            )
            print("\n  Current batches in queue:")
            for row in result:
                print(f"    - Batch #{row.batch_no}: {row.mo_id}")
        else:
            print("\n  ✓ Table is EMPTY → Scheduler will FETCH new data")
    
    print("\n" + "=" * 70)
    print("Scheduler Workflow:")
    print("=" * 70)
    print("""
1. Scheduler runs every {interval} minutes (if ENABLE_AUTO_SYNC=true)
2. Check mo_batch table:
   - If COUNT(*) > 0: SKIP (PLC masih proses)
   - If COUNT(*) = 0: FETCH {limit} batches dari Odoo
3. After fetch: Insert new batches to mo_batch
4. PLC reads from mo_batch and processes
5. After PLC done: Clear table (manual or via API)
6. Scheduler detects empty table → fetch next batches

To clear table manually:
  DELETE FROM mo_batch;

To test scheduler:
  1. Set ENABLE_AUTO_SYNC=true in .env
  2. Restart uvicorn
  3. Clear mo_batch table
  4. Wait {interval} minutes
  5. Check logs and database
    """.format(
        interval=settings.sync_interval_minutes,
        limit=settings.sync_batch_limit
    ))
    print("=" * 70)


if __name__ == "__main__":
    test_scheduler_logic()
