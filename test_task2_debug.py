#!/usr/bin/env python3
"""
Debug Script: Task 2 Flow
Test PLC Read → DB Update → Odoo Consumption Sync

Ini akan simulasi Task 2 step-by-step tanpa scheduler,
jadi kita bisa lihat exact flow dan debug errors.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_sync_service import get_plc_sync_service
from app.services.odoo_consumption_service import get_consumption_service

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_db_connection():
    """Check database connection."""
    print("\n" + "="*80)
    print("STEP 0: Check Database Connection")
    print("="*80)
    
    settings = get_settings()
    print(f"DATABASE_URL: {settings.database_url[:50]}...")
    
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
            count = result.scalar()
            print(f"✓ DB connected, mo_batch has {count} records")
        return engine
    except Exception as e:
        print(f"✗ DB connection failed: {e}")
        raise


def get_active_batches(engine):
    """Get active batches from DB."""
    print("\n" + "="*80)
    print("STEP 1: Get Active Batches from DB")
    print("="*80)
    
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        stmt = select(TableSmoBatch).where(
            TableSmoBatch.status_manufacturing.is_(False)
        )
        batches = db.execute(stmt).scalars().all()
        
        print(f"Found {len(batches)} active batches:")
        for batch in batches:
            print(f"  - {batch.mo_id}: update_odoo={batch.update_odoo}, status_mfg={batch.status_manufacturing}")
        
        return batches
    finally:
        db.close()


def read_plc_data():
    """Read data from PLC."""
    print("\n" + "="*80)
    print("STEP 2: Read Data from PLC")
    print("="*80)
    
    try:
        plc_service = get_plc_sync_service()
        result = asyncio.run(plc_service.sync_from_plc())
        
        print(f"PLC sync result:")
        print(f"  - success: {result.get('success')}")
        print(f"  - updated: {result.get('updated')}")
        print(f"  - mo_id: {result.get('mo_id')}")
        print(f"  - error: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.exception(f"Error reading PLC: {e}")
        raise


async def sync_to_odoo(engine, mo_id):
    """Sync consumption to Odoo for given MO."""
    print("\n" + "="*80)
    print(f"STEP 3: Sync Consumption to Odoo for {mo_id}")
    print("="*80)
    
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Get batch from DB
        stmt = select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
        batch = db.execute(stmt).scalar_one_or_none()
        
        if not batch:
            print(f"✗ Batch not found for MO {mo_id}")
            return
        
        print(f"✓ Found batch: {mo_id}")
        print(f"  - update_odoo (before): {batch.update_odoo}")
        print(f"  - status_manufacturing: {batch.status_manufacturing}")
        
        # Prepare batch data
        batch_data = {
            "status_manufacturing": int(batch.status_manufacturing) if batch.status_manufacturing else 0,
            "actual_weight_quantity_finished_goods": (
                float(batch.actual_weight_quantity_finished_goods) 
                if batch.actual_weight_quantity_finished_goods is not None 
                else 0.0
            ),
        }
        
        # Add consumption untuk setiap silo
        consumption_count = 0
        for letter in "abcdefghijklm":
            attr_name = f"actual_consumption_silo_{letter}"
            if hasattr(batch, attr_name):
                value = getattr(batch, attr_name)
                if value is not None and value > 0:
                    batch_data[f"consumption_silo_{letter}"] = float(value)
                    consumption_count += 1
        
        print(f"  - consumption entries to sync: {consumption_count}")
        
        if consumption_count == 0:
            print("  ⚠ No consumption data to sync")
            return
        
        # Call consumption service
        consumption_service = get_consumption_service(db)
        equipment_id = str(batch.equipment_id_batch or "PLC01")
        
        print(f"\n  Calling process_batch_consumption()...")
        print(f"    mo_id: {mo_id}")
        print(f"    equipment_id: {equipment_id}")
        print(f"    batch_data keys: {list(batch_data.keys())}")
        
        odoo_result = await consumption_service.process_batch_consumption(
            mo_id=mo_id,
            equipment_id=equipment_id,
            batch_data=batch_data
        )
        
        print(f"\n  Odoo result:")
        print(f"    - success: {odoo_result.get('success')}")
        print(f"    - error: {odoo_result.get('error')}")
        print(f"    - consumption_updated: {odoo_result.get('consumption', {}).get('consumption_updated')}")
        
        if odoo_result.get("success"):
            # Mark batch as updated
            batch.update_odoo = True
            db.commit()
            print(f"\n  ✓ Set update_odoo=True for {mo_id}")
        else:
            print(f"\n  ✗ Failed to sync to Odoo")
    
    finally:
        db.close()


async def main():
    print("\n\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "TASK 2 DEBUG: PLC Read → DB Update → Odoo Sync" + " "*14 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # Step 0: DB Connection
        engine = check_db_connection()
        
        # Step 1: Get active batches
        batches = get_active_batches(engine)
        
        if not batches:
            print("\n✗ No active batches. Cannot run test.")
            return
        
        # Step 2: Read PLC
        plc_result = read_plc_data()
        
        if not plc_result.get("success"):
            print(f"\n✗ PLC read failed: {plc_result.get('error')}")
            return
        
        mo_id = plc_result.get("mo_id")
        updated = plc_result.get("updated")
        
        print(f"\n✓ PLC read successful for MO {mo_id} (updated={updated})")
        
        # Step 3: Sync to Odoo
        if updated:
            await sync_to_odoo(engine, mo_id)
        else:
            print(f"\n⚠ PLC data not changed, skipping Odoo sync")
        
        print("\n" + "="*80)
        print("TEST COMPLETE")
        print("="*80)
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
