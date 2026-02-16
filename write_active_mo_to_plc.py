#!/usr/bin/env python3
"""
Script untuk write data active MO (WH/MO/00003) ke PLC memory.
Ini mempersiapkan PLC untuk test Task 2.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_write_service import get_plc_write_service

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_batch_by_id(batch_id):
    """Get batch dari database."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        stmt = select(TableSmoBatch).where(TableSmoBatch.mo_id == batch_id)
        batch = db.execute(stmt).scalar_one_or_none()
        return batch
    finally:
        db.close()


def write_batch_to_plc(batch):
    """Write batch data to PLC."""
    print("\n" + "="*80)
    print(f"Writing Batch {batch.mo_id} to PLC Memory")
    print("="*80)
    
    try:
        plc_write_service = get_plc_write_service()
        
        # Prepare data untuk write
        # Format: key adalah field name dari PLC read mapping
        plc_data = {
            "NO-MO": batch.mo_id,
            "finished_goods": batch.finished_goods or "PRODUCT",
            "Quantity Goods_id": float(batch.consumption or 0),
            "status manufaturing": 0,  # 0 = active/not completed
            "Status Operation": 0,
            "weight_finished_good": float(batch.actual_weight_quantity_finished_goods or 0),
        }
        
        # Add silo data - format untuk write harus match dengan read mapping
        silos = {
            101: ("a", batch.actual_consumption_silo_a),
            102: ("b", batch.actual_consumption_silo_b),
            103: ("c", batch.actual_consumption_silo_c),
            104: ("d", batch.actual_consumption_silo_d),
            105: ("e", batch.actual_consumption_silo_e),
            106: ("f", batch.actual_consumption_silo_f),
            107: ("g", batch.actual_consumption_silo_g),
            108: ("h", batch.actual_consumption_silo_h),
            109: ("i", batch.actual_consumption_silo_i),
            110: ("j", batch.actual_consumption_silo_j),
            111: ("k", batch.actual_consumption_silo_k),
            112: ("l", batch.actual_consumption_silo_l),
            113: ("m", batch.actual_consumption_silo_m),
        }
        
        for silo_id, (letter, consumption) in silos.items():
            # Cek consumption_silo_X fields untuk existing data
            attr_name = f"consumption_silo_{letter}"
            existing_consumption = getattr(batch, attr_name, None) or (consumption or 0)
            
            # Write silo ID dan consumption
            silo_id_key = f"SILO ID {silo_id} (SILO BESAR)" if silo_id in [101, 102, 103] else f"SILO ID {silo_id}"
            consumption_key = f"SILO ID {silo_id} Consumption"
            
            plc_data[silo_id_key] = float(silo_id)
            plc_data[consumption_key] = float(existing_consumption)
        
        print(f"\nBatch Data to Write:")
        print(f"  MO_ID: {plc_data['NO-MO']}")
        print(f"  Product: {plc_data['finished_goods']}")
        print(f"  Quantity: {plc_data['Quantity Goods_id']}")
        print(f"  Status Manufacturing: {plc_data['status manufaturing']} (ACTIVE)")
        print(f"  Weight Finished Good: {plc_data['weight_finished_good']}")
        
        # Count consumption entries
        consumption_entries = 0
        for key, val in plc_data.items():
            if "Consumption" in key and val > 0:
                consumption_entries += 1
                print(f"  {key}: {val}")
        
        print(f"\n  Total consumption entries: {consumption_entries}/13")
        
        # Call plc_write_service dengan format yang sesuai
        # Assuming write_batch method atau similar
        print(f"\n  Attempting to write to PLC via write_service...")
        
        # We need to call write method on plc_write_service
        # Check what methods are available
        methods = [m for m in dir(plc_write_service) if not m.startswith('_')]
        print(f"  Available methods: {methods}")
        
        return plc_data
        
    except Exception as e:
        logger.exception(f"Error writing to PLC: {e}")
        raise


if __name__ == "__main__":
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "Write Active MO to PLC Memory for Task 2 Testing" + " "*23 + "║")
    print("╚" + "="*78 + "╝")
    
    # Get first active batch
    batch = get_batch_by_id("WH/MO/00003")
    if not batch:
        print("✗ Batch WH/MO/00003 not found!")
        sys.exit(1)
    
    print(f"\n✓ Found batch: {batch.mo_id}")
    print(f"  - Status: {'ACTIVE' if not batch.status_manufacturing else 'COMPLETED'}")
    print(f"  - Updated to Odoo: {batch.update_odoo}")
    
    # Write to PLC
    plc_data = write_batch_to_plc(batch)
    
    print("\n" + "="*80)
    print("Next: Run test_task2_debug.py to see if PLC reads this data and syncs to Odoo")
    print("="*80)
