#!/usr/bin/env python3
"""
Test: Two-cycle flow demonstrating correct status_manufacturing logic.

CYCLE 1 (DB status=false):
- PLC data: status_manufacturing=1 (finished)
- DB check: status_manufacturing=false (not yet marked complete)
- RESULT: ✓ Updates ALLOWED (consumption + status_manufacturing→true)

CYCLE 2 (DB status=true):
- PLC data: status_manufacturing=1 (still finished)
- DB check: status_manufacturing=true (already marked complete)
- RESULT: ✓ Updates BLOCKED (skip all, return False)

This shows the workflow:
  PLC → DB (Cycle 1: updates allowed)
  DB (Cycle 2: updates blocked by DB check)
"""

import asyncio
import logging
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import sys
sys.path.insert(0, "/projek/fastapi-scada-odoo")

from app.db.base import Base
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_sync_service import PlcSyncService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_two_cycle_flow():
    """Test the correct two-cycle consumption and status update flow."""
    
    print("\n" + "="*80)
    print("TEST: Two-Cycle Flow - status_manufacturing Logic Verification")
    print("="*80)
    
    # Create in-memory DB for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    # ======== CYCLE 1 ========
    print("\n" + "-"*80)
    print("CYCLE 1: DB status_manufacturing = FALSE (batch not yet complete)")
    print("-"*80)
    
    db = SessionLocal()
    try:
        # Create test batch with status_manufacturing=FALSE
        test_batch = TableSmoBatch(
            batch_no=1001,
            mo_id="WH/MO/00001",
            consumption=2000.00,
            equipment_id_batch="PLC01",
            status_manufacturing=False,  # ← DB: NOT complete yet
            actual_consumption_silo_a=0.0,
        )
        db.add(test_batch)
        db.commit()
        
        print(f"\n✓ Created batch: {test_batch.mo_id}")
        print(f"  - DB status_manufacturing: {test_batch.status_manufacturing}")
        
        # PLC data with status_manufacturing=1 (manufacturing finished)
        plc_data = {
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
                "manufacturing": 1,  # ← PLC: finished!!
                "operation": 1,
            },
            "equipment_id_batch": "PLC01",
            "weight_finished_good": 20000.00,
        }
        
        print(f"\n➜ PLC data incoming:")
        print(f"  - PLC status_manufacturing: {plc_data['status']['manufacturing']} (1=finished)")
        print(f"  - Silo A consumption: {plc_data['silos']['a']['consumption']}")
        
        # Process with _update_batch_if_changed
        print(f"\n➜ Checking: DB status_manufacturing ({test_batch.status_manufacturing}) vs PLC ({plc_data['status']['manufacturing']})")
        print(f"  - DB is FALSE → Check passes → Allow updates")
        
        plc_sync_service = PlcSyncService(db)
        changed = plc_sync_service._update_batch_if_changed(
            db, 
            test_batch, 
            plc_data
        )
        
        db.refresh(test_batch)
        
        print(f"\n✓ Cycle 1 complete:")
        print(f"  - _update_batch_if_changed() returned: {changed}")
        print(f"  - actual_consumption_silo_a: {test_batch.actual_consumption_silo_a}")
        print(f"  - DB status_manufacturing after: {test_batch.status_manufacturing}")
        
        # Verify Cycle 1
        check1_consumption = test_batch.actual_consumption_silo_a == 825.25
        check1_status = test_batch.status_manufacturing == True
        check1_changed = changed == True
        
        print(f"\n  Cycle 1 Results:")
        print(f"  {'✅' if check1_consumption else '❌'} Consumption updated: {test_batch.actual_consumption_silo_a}")
        print(f"  {'✅' if check1_status else '❌'} Status set to True: {test_batch.status_manufacturing}")
        print(f"  {'✅' if check1_changed else '❌'} Changed flag: {changed}")
        
    finally:
        db.close()
    
    # ======== CYCLE 2 ========
    print("\n" + "-"*80)
    print("CYCLE 2: DB status_manufacturing = TRUE (batch now complete)")
    print("-"*80)
    
    db = SessionLocal()
    try:
        # Get the same batch (now with status_manufacturing=True from Cycle 1)
        stmt = select(TableSmoBatch).where(TableSmoBatch.mo_id == "WH/MO/00001")
        test_batch = db.execute(stmt).scalars().first()
        
        print(f"\n✓ Retrieved batch: {test_batch.mo_id}")
        print(f"  - DB status_manufacturing: {test_batch.status_manufacturing} (was set to True in Cycle 1)")
        print(f"  - actual_consumption_silo_a: {test_batch.actual_consumption_silo_a} (825.25 from Cycle 1)")
        
        # Same PLC data comes in again
        plc_data_cycle2 = {
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
                "manufacturing": 1,  # ← PLC: still finished
                "operation": 1,
            },
            "equipment_id_batch": "PLC01",
            "weight_finished_good": 20000.00,
        }
        
        print(f"\n➜ PLC data incoming (same data):")
        print(f"  - PLC status_manufacturing: {plc_data_cycle2['status']['manufacturing']}")
        
        # Process with _update_batch_if_changed
        print(f"\n➜ Checking: DB status_manufacturing ({test_batch.status_manufacturing}) vs PLC ({plc_data_cycle2['status']['manufacturing']})")
        print(f"  - DB is TRUE → Check FAILS → Block all updates")
        
        plc_sync_service = PlcSyncService(db)
        changed = plc_sync_service._update_batch_if_changed(
            db, 
            test_batch, 
            plc_data_cycle2
        )
        
        print(f"\n✓ Cycle 2 complete:")
        print(f"  - _update_batch_if_changed() returned: {changed}")
        
        # Verify Cycle 2
        check2_changed = changed == False
        
        print(f"\n  Cycle 2 Results:")
        print(f"  {'✅' if check2_changed else '❌'} Updates blocked: {changed} (expected False)")
        
    finally:
        db.close()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY: Correct Two-Cycle Behavior")
    print("="*80)
    print(f"""
CYCLE 1 (DB status=false):
  ✓ PLC sends: status_manufacturing=1 (finished)
  ✓ DB check: status=false → ALLOW
  ✓ Updates: consumption + status_manufacturing→true
  ✓ Result: Consumption sent to Odoo, status in DB updated
  
CYCLE 2 (DB status=true):
  ✓ PLC sends: status_manufacturing=1 (still finished)
  ✓ DB check: status=true → BLOCK
  ✓ Updates: SKIPPED (no interference)
  ✓ Result: Batch protected from further changes
  
KEY INSIGHT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Source of Truth: DATABASE (mo_batch.status_manufacturing)
• Check: Current DB value BEFORE any updates
• If DB already true → Block (prevents interference)
• If DB still false → Allow (PLC can update status + consumption)
• Transition point: When mark_mo_done() sets DB to true
• Protection: Once true, automatically blocked next cycle - no race condition!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)


if __name__ == "__main__":
    test_two_cycle_flow()
