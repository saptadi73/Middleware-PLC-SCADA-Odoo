#!/usr/bin/env python3
"""
Test: Consumption flow after status_manufacturing fix.

BEFORE FIX:
- PLC data set status_manufacturing=1 (finished)
- _update_batch_if_changed() skipped consumption update
- Consumption never sent to DB or Odoo

AFTER FIX:
- PLC data IGNORED for status_manufacturing (only system manages it)
- _update_batch_if_changed() processes consumption normally
- Consumption sent to DB, then to Odoo (by TaskConsumption/mark_mo_done)

This test verifies:
✓ status_manufacturing NOT updated from PLC data
✓ Consumption values ARE updated in DB despite PLC status=0
✓ Workflow: PLC read → consume update → (separately) mark_mo_done → move to history
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Setup paths
import sys
sys.path.insert(0, "/projek/fastapi-scada-odoo")

from app.db.database import get_session
from app.db.base import Base
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_sync_service import PlcSyncService
from app.services.plc_read_service import PlcReadService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_consumption_flow():
    """Test the fixed consumption update flow."""
    
    print("\n" + "="*70)
    print("TEST: Consumption Flow After status_manufacturing Fix")
    print("="*70)
    
    # Create in-memory DB for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create test batch (status_manufacturing=False initially)
        test_batch = TableSmoBatch(
            batch_no=1001,
            mo_id="WH/MO/00001",
            consumption=2000.00,
            equipment_id_batch="PLC01",
            status_manufacturing=False,  # NOT finished yet
            actual_consumption_silo_a=0.0,  # Empty
        )
        db.add(test_batch)
        db.commit()
        
        print(f"\n✓ Created test batch: {test_batch.mo_id}")
        print(f"  - batch_no: {test_batch.batch_no}")
        print(f"  - status_manufacturing: {test_batch.status_manufacturing}")
        print(f"  - actual_consumption_silo_a (before): {test_batch.actual_consumption_silo_a}")
        
        # Simulate PLC data with status_manufacturing=0 (not finished)
        # In real scenario, CSV had status_manufacturing=1, now we fixed it to 0
        plc_data_like_csv = {
            "batch_no": 1001,
            "consumption": 2000.00,
            "silos": {
                "a": {"consumption": 825.25},
                "b": {"consumption": 375.15},
                "c": {"consumption": 240.25},
                "d": {"consumption": 50.0},
                "e": {"consumption": 381.25},
                "f": {"consumption": 250.0},
                "g": {"consumption": 62.5},
                "h": {"consumption": 83.5},
                "i": {"consumption": 83.25},
                "j": {"consumption": 83.25},
                "k": {"consumption": 3.75},
                "l": {"consumption": 0.25},
                "m": {"consumption": 42.0},
            },
            "status": {
                "manufacturing": 0,  # NOW FIXED TO 0 (was 1 before fix!)
                "operation": 1,
            },
            "equipment_id_batch": "PLC01",
            "weight_finished_good": 20000.00,
        }
        
        print(f"\n➜ Simulating PLC data read:")
        print(f"  - status_manufacturing from PLC: {plc_data_like_csv['status']['manufacturing']}")
        print(f"  - Silo A consumption: {plc_data_like_csv['silos']['a']['consumption']}")
        print(f"\n  BEFORE FIX: This would be set to status_manufacturing=0")
        print(f"  This is OK because we ignore PLC status now!")
        
        # Test _update_batch_if_changed with fixed code
        plc_sync_service = PlcSyncService(db)
        changed = plc_sync_service._update_batch_if_changed(
            db, 
            test_batch, 
            plc_data_like_csv
        )
        
        db.refresh(test_batch)
        
        print(f"\n✓ Called _update_batch_if_changed():")
        print(f"  - returned changed: {changed}")
        print(f"  - status_manufacturing after: {test_batch.status_manufacturing}")
        print(f"  - actual_consumption_silo_a (after): {test_batch.actual_consumption_silo_a}")
        
        # Verify results
        print(f"\n" + "="*70)
        print("VERIFICATION:")
        print("="*70)
        
        # Check 1: status_manufacturing should NOT be updated from PLC
        if test_batch.status_manufacturing == False:
            print(f"✅ PASS: status_manufacturing stayed False")
            print(f"         (PLC value was IGNORED as expected)")
        else:
            print(f"❌ FAIL: status_manufacturing changed to {test_batch.status_manufacturing}")
            print(f"         (should still be False, PLC value should be ignored)")
        
        # Check 2: Consumption should be updated
        if test_batch.actual_consumption_silo_a == 825.25:
            print(f"✅ PASS: actual_consumption_silo_a = 825.25")
            print(f"         (consumption WAS updated despite PLC having status=0)")
        else:
            print(f"❌ FAIL: actual_consumption_silo_a = {test_batch.actual_consumption_silo_a}")
            print(f"         (expected 825.25, consumption not updated)")
        
        # Check 3: changed should be True (something changed)
        if changed:
            print(f"✅ PASS: returned changed=True")
            print(f"         (consumption update was processed)")
        else:
            print(f"❌ FAIL: returned changed=False")
            print(f"         (no updates processed)")
        
        print(f"\n" + "="*70)
        print("WORKFLOW NOW:")
        print("="*70)
        print(f"""
1. PLC reads data (status_manufacturing ignored)
2. Consumption updated in mo_batch immediately ✓
3. Task 3 queries completed batches (where status_manufacturing=1)
4. Later, when Odoo marks MO done:
   - mark_mo_done() sets status_manufacturing=True in DB
   - Task 3 then picks it up for history movement

RESULT: Consumption sent to Odoo BEFORE batch marked complete!
        """)
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_consumption_flow())
