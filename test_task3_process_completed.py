#!/usr/bin/env python3
"""
Test Task 3: Process completed batches dan archive mereka.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from app.core.config import get_settings
from app.core.scheduler import process_completed_batches_task

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def show_batch_status(label):
    """Show current batch status."""
    print(f"\n{label}:")
    
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            # mo_batch
            result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
            count = result.scalar() or 0
            
            # mo_histories
            result = conn.execute(text("SELECT COUNT(*) FROM mo_histories"))
            history_count = result.scalar() or 0
            
            result = conn.execute(text("""
                SELECT mo_id, status_manufacturing, update_odoo
                FROM mo_batch
                ORDER BY mo_id
            """))
            
            batches = result.fetchall()
            
            print(f"  mo_batch: {count} records, mo_histories: {history_count} records")
            
            if batches:
                print(f"  Batches in mo_batch:")
                for mo_id, status_mfg, update_odoo in batches:
                    status = "DONE" if status_mfg else "ACTIVE"
                    upd = "YES" if update_odoo else "NO"
                    print(f"    - {mo_id}: status={status}, updated={upd}")
    
    finally:
        engine.dispose()


async def main():
    print("\n\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "Test Task 3: Process Completed Batches" + " "*22 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # Show initial status
        show_batch_status("BEFORE Task 3")
        
        # Run Task 3
        print("\n" + "="*80)
        print("Running Task 3...")
        print("="*80)
        
        await process_completed_batches_task()
        
        # Show final status
        show_batch_status("AFTER Task 3")
        
        print("\n" + "="*80)
        print("✓ Task 3 completed")
        print("  - Completed batch has been moved to mo_histories")
        print("  - mo_batch is now ready for Task 1 to fetch new MOs")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.exception(f"Task 3 failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
