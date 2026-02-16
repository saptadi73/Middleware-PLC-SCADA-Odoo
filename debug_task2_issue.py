#!/usr/bin/env python3
"""
Debug: Check why PLC reads WH/MO/00001 yang completed
dan lihat apakah ada masalah dengan MO routing di PLC.
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings

def check_mo_status():
    """Check MO status di database."""
    print("\n" + "="*80)
    print("MO Status in Database")
    print("="*80)
    
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT mo_id, status_manufacturing, status_operation, update_odoo, 
                       batch_no, finished_goods
                FROM mo_batch
                ORDER BY mo_id
            """))
            
            batches = result.fetchall()
            
            print(f"\n{'MO ID':>15} {'Batch':>6} {'Mfg':>6} {'Op':>6} {'Updated':>10} {'Product':>20}")
            print(f"{'-'*15} {'-'*6} {'-'*6} {'-'*6} {'-'*10} {'-'*20}")
            
            for batch in batches:
                mo_id, status_mfg, status_op, update_odoo, batch_no, product = batch
                mfg = "DONE" if status_mfg else "ACTIVE"
                op = "RUN" if status_op else "IDLE"
                upd = "YES" if update_odoo else "NO"
                prod = (product or "N/A")[:20]
                print(f"{mo_id:>15} {batch_no:>6} {mfg:>6} {op:>6} {upd:>10} {prod:>20}")
            
            print(f"\n⚠ ISSUE: WH/MO/00001 has status_manufacturing=TRUE (COMPLETED)")
            print(f"  But it's being read by PLC when there are {len(batches)-1} other ACTIVE MOs")
            print(f"  This happens because status was updated in the DB from PLC read (STEP 2)")
            
    finally:
        engine.dispose()


def check_plc_memory():
    """Check what's actually stored in PLC memory."""
    print("\n" + "="*80)
    print("What PLC Currently Has in Memory")
    print("="*80)
    
    print("""
    PLC Device Memory Configuration (FINS Protocol):
    - DM 6001-6008: MO_ID (NO-MO) - 8 words = 16 chars = "WH/MO/00001"
    - Status at DM 6066: status_manufacturing = 1 (True/COMPLETED)
    
    The PLC memory contains ONLY what was last written to it.
    Currently this is WH/MO/00001 with status=1 (COMPLETED).
    
    When plc_sync_service reads this, it:
    1. Reads MO_ID = WH/MO/00001
    2. Finds matching batch in mo_batch table
    3. Updates actual_consumption_silo_* fields
    4. Sets status_manufacturing = 1 (from PLC)
    5. SKIP the write to Odoo because status already = 1
    
    But the code is WRONG! It should skip the Odoo write BEFORE updating status!
    """)


def check_task2_logic():
    """Analyze Task 2 logic issue."""
    print("\n" + "="*80)
    print("Task 2 Logic Analysis")
    print("="*80)
    
    print("""
    Current Task 2 Flow (WRONG):
    1. Read PLC → finds WH/MO/00001 with status=1
    2. Load DB record for WH/MO/00001
    3. Update actual_consumption_silo_* from PLC
    4. Update status_manufacturing = 1 from PLC
    5. Return updated=True (because consumption changed)
    6. TRY to sync to Odoo
    7. BUT in process_batch_consumption, check if status_manufacturing=1
    8. If yes, skip the operation
    
    PROBLEM: In test_task2_debug.py, it shows:
    - "consumption_updated: True" ✓ This is GOOD
    - But then: "Skip consumption update... status_manufacturing already completed"
    
    This happens because update_batch_if_changed() updates the status to 1,
    but then process_batch_consumption() checks if status is 1 and SKIPS.
    
    The consumption IS sent to Odoo successfully (we see the 200 OK response),
    but the skip message says it won't be processed.
    
    ACTUAL ISSUE:
    1. The consumption DID sync to Odoo ✓
    2. The update_odoo flag WAS set to True ✓
    3. But only for WH/MO/00001 which was already completed
    4. The 6 other ACTIVE MOs are waiting for PLC to read them
    5. PLC will never read them because it's stuck on WH/MO/00001
    
    SOLUTION:
    - Send consumption data to Odoo EVEN IF status is already 1
    - Or better yet: only update status from PLC if status was 0
    - OR: Handle already-completed batches differently
    """)


if __name__ == "__main__":
    print("\n\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "Debug: Why is PLC stuck on WH/MO/00001?" + " "*20 + "║")
    print("╚" + "="*78 + "╝")
    
    check_mo_status()
    check_plc_memory()
    check_task2_logic()
