"""
Debug Consumption Data Sync Flow
Check where consumption values mismatch between PLC → DB → Odoo
"""
import json
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_read_service import get_plc_read_service

settings = get_settings()

print("\n" + "="*80)
print("DEBUG: Consumption Data Sync Flow")
print("="*80)

# Step 1: Read from PLC
print("\n[STEP 1] Reading consumption data from PLC...")
try:
    plc_service = get_plc_read_service()
    plc_data = plc_service.read_batch_data()
    
    print(f"\nPLC Read Result:")
    print(f"  MO_ID: {plc_data.get('mo_id')}")
    print(f"  Silos data:")
    
    silos = plc_data.get('silos', {})
    for letter, data in silos.items():
        consumption = data.get('consumption', 0)
        print(f"    SILO {letter.upper()}: {consumption}")
    
except Exception as e:
    print(f"  ✗ Error reading from PLC: {e}")
    silos = {}

# Step 2: Check database for this MO
print("\n[STEP 2] Checking database for matching MO record...")
try:
    mo_id = plc_data.get('mo_id', '')
    
    db = SessionLocal()
    result = db.execute(
        select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
    )
    batch = result.scalar_one_or_none()
    
    if batch:
        print(f"\n✓ Found mo_batch record: {batch.batch_no}")
        print(f"  MO_ID: {batch.mo_id}")
        print(f"  Status Manufacturing: {batch.status_manufacturing}")
        
        print(f"\n  Consumption values stored in database:")
        for letter in "abcdefghijklm":
            attr_name = f"actual_consumption_silo_{letter}"
            if hasattr(batch, attr_name):
                value = getattr(batch, attr_name)
                if value and value > 0:
                    print(f"    {attr_name}: {value}")
    else:
        print(f"  ✗ No mo_batch found for MO_ID: {mo_id}")
        batch = None
    
    db.close()
    
except Exception as e:
    print(f"  ✗ Error checking database: {e}")
    batch = None

# Step 3: Compare PLC vs Database
print("\n[STEP 3] Comparing PLC data vs Database...")
if silos and batch:
    print("\n  Comparison:")
    print("  Letter | PLC Value | DB Value | Match")
    print("  -------|-----------|----------|-------")
    
    for letter in "abcdefghijklm":
        plc_value = silos.get(letter, {}).get('consumption', 0)
        
        attr_name = f"actual_consumption_silo_{letter}"
        db_value = getattr(batch, attr_name, 0) if batch else 0
        
        match = "✓" if plc_value == db_value else "✗"
        
        if plc_value > 0 or db_value > 0:
            print(f"  {letter.upper():^6} | {plc_value:^9} | {db_value:^8} | {match}")

# Step 4: Show what will be sent to Odoo
print("\n[STEP 4] Simulating consumption data sending to Odoo...")
if batch:
    print(f"\n  Will send to Odoo (converted silo_a → silo101):")
    
    batch_data = {
        "status_manufacturing": batch.status_manufacturing,
    }
    
    conversion_map = {
        'a': 'silo101', 'b': 'silo102', 'c': 'silo103', 'd': 'silo104',
        'e': 'silo105', 'f': 'silo106', 'g': 'silo107', 'h': 'silo108',
        'i': 'silo109', 'j': 'silo110', 'k': 'silo111', 'l': 'silo112', 'm': 'silo113',
    }
    
    for letter in "abcdefghijklm":
        attr_name = f"actual_consumption_silo_{letter}"
        value = getattr(batch, attr_name, 0) if batch else 0
        
        if value and value > 0:
            odoo_code = conversion_map.get(letter)
            batch_data[odoo_code] = float(value)
            print(f"    {odoo_code}: {value}")

print("\n" + "="*80)
print("Debug Summary:")
print("  1. PLC reads SILO consumption values")
print("  2. Values stored in DB as actual_consumption_silo_{letter}")
print("  3. Values converted silo_a → silo101 for Odoo")
print("  4. Sent to Odoo at POST /api/scada/mo/update-with-consumptions")
print("\nIf values don't match in Odoo:")
print("  - Check Step 1 (PLC reading)")
print("  - Check Step 2 (Database storage)")
print("  - Check Step 3 (Comparison)")
print("  - Verify Odoo received correct values")
print("="*80 + "\n")
