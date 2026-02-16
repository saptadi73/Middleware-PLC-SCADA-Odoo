#!/usr/bin/env python3
"""
Test Task 2 dengan menulis data MO yang ACTIVE ke PLC memory.
Kemudian test consumption sync ke Odoo.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_write_service import get_plc_write_service

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_first_active_batch():
    """Get first active batch dari database."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        stmt = select(TableSmoBatch).where(
            TableSmoBatch.status_manufacturing.is_(False)
        )
        batches = db.execute(stmt).scalars().all()
        
        if not batches:
            print("✗ No active batches found!")
            return None
        
        batch = batches[0]
        print(f"✓ Found active batch: {batch.mo_id}")
        print(f"  - status_manufacturing: {batch.status_manufacturing}")
        print(f"  - update_odoo: {batch.update_odoo}")
        
        return batch
    finally:
        db.close()


def write_active_mo_to_plc(batch):
    """Write active MO data to PLC memory."""
    print("\n" + "="*80)
    print(f"STEP 1: Write Active MO {batch.mo_id} to PLC Memory")
    print("="*80)
    
    try:
        plc_write_service = get_plc_write_service()
        
        # Prepare data to write
        plc_data = {
            "mo_id": batch.mo_id,
            "product_name": batch.finished_goods or "PRODUCT",
            "bom_name": "BOM",  # Not available in model
            "quantity": float(batch.consumption or 0),
            "status_manufacturing": 0,  # 0 = not completed, 1 = completed
            "status_operation": 0,
            "weight_finished_good": float(batch.actual_weight_quantity_finished_goods or 0),
        }
        
        # Add silo consumption data
        silos_data = {}
        for letter in "abcdefghijklm":
            attr_name = f"actual_consumption_silo_{letter}"
            consumption = getattr(batch, attr_name, 0) or 0
            silos_data[letter] = {
                "id": 100 + ord(letter) - ord('a') + 1,  # 101-113
                "consumption": float(consumption),
            }
        
        plc_data["silos"] = silos_data
        
        print(f"\nData Summary from Active Batch {batch.mo_id}:")
        print(f"  - finished_goods: {plc_data['product_name']}")
        print(f"  - consumption: {plc_data['quantity']}")
        print(f"  - Status Manufacturing: {plc_data['status_manufacturing']} (ACTIVE)")
        print(f"  - actual_weight_quantity_finished_goods: {plc_data['weight_finished_good']}")
        
        consumption_count = 0
        for letter, silo in silos_data.items():
            if silo['consumption'] > 0:
                print(f"  - actual_consumption_silo_{letter}: {silo['consumption']}")
                consumption_count += 1
        
        print(f"\n  Silos with consumption: {consumption_count}/13")
        
        return plc_data
        
    except Exception as e:
        logger.exception(f"Error processing batch: {e}")
        raise


async def test_task2_with_active_mo():
    """Test Task 2 with active MO."""
    print("\n\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "Test Task 2: Write Active MO to PLC, then read & sync to Odoo" + " "*5 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # Get first active batch
        batch = get_first_active_batch()
        if not batch:
            return
        
        # Write to PLC
        plc_data = write_active_mo_to_plc(batch)
        
        print("\n" + "="*80)
        print("NEXT STEPS:")
        print("="*80)
        print("1. Write the above data to PLC memory via FINS protocol")
        print("2. Run test_task2_debug.py again to see if PLC reads data")
        print("3. Check if consumption is synced to Odoo")
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_task2_with_active_mo())
