#!/usr/bin/env python3
"""
Check if WH/MO/00001 qualifies for Task 3 processing.
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.models.tablesmo_batch import TableSmoBatch
from app.services.mo_history_service import get_mo_history_service

def check_task3_conditions():
    """Check if WH/MO/00001 qualifies for Task 3."""
    print("\n" + "="*80)
    print("Check Task 3 Conditions for WH/MO/00001")
    print("="*80)
    
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Get the batch
        stmt = select(TableSmoBatch).where(TableSmoBatch.mo_id == "WH/MO/00001")
        batch = db.execute(stmt).scalar_one_or_none()
        
        if not batch:
            print("✗ Batch not found!")
            return
        
        print(f"\nBatch Details:")
        print(f"  MO ID: {batch.mo_id}")
        print(f"  Status Manufacturing: {batch.status_manufacturing}")
        print(f"  Update Odoo: {batch.update_odoo}")
        print(f"  Batch No: {batch.batch_no}")
        
        # Check Task 3 conditions
        print(f"\nTask 3 Conditions:")
        cond1 = batch.status_manufacturing == True
        cond2 = batch.update_odoo == True
        
        print(f"  1. status_manufacturing = True: {cond1} ✓" if cond1 else f"  1. status_manufacturing = True: {cond1} ✗")
        print(f"  2. update_odoo = True: {cond2} ✓" if cond2 else f"  2. update_odoo = True: {cond2} ✗")
        
        if cond1 and cond2:
            print(f"\n✓ SHOULD be processed by Task 3!")
            print(f"  - Move to mo_histories")
            print(f"  - Delete from mo_batch")
            print(f"  - This will free up the queue for Task 1 to fetch new MOs")
        else:
            print(f"\n✗ Won't be processed by Task 3 (missing conditions)")
        
        # Check other batches
        print(f"\n" + "="*80)
        print(f"Other Active Batches Status (waiting for PLC)")
        print("="*80)
        
        stmt = select(TableSmoBatch).where(
            TableSmoBatch.status_manufacturing.is_(False)
        )
        active_batches = db.execute(stmt).scalars().all()
        
        print(f"\n  Total active batches (waiting): {len(active_batches)}")
        for batch in active_batches:
            print(f"    - {batch.mo_id}: status=0, update_odoo={batch.update_odoo}")
        
    finally:
        db.close()


if __name__ == "__main__":
    check_task3_conditions()
