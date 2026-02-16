#!/usr/bin/env python3
"""
Debug script to trace consumption_silo_a value through entire data flow
"""

import json
import sys
from app.services.plc_read_service import PLCReadService
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch

def trace_csv_value():
    """Trace value from CSV"""
    print("\n" + "=" * 70)
    print("1. CSV DATA (read_data_plc_input.csv)")
    print("=" * 70)
    
    with open('app/reference/read_data_plc_input.csv', 'r') as f:
        lines = f.readlines()
    
    # Find SILO ID 101 Consumption line
    for line in lines:
        if 'SILO ID 101 Consumption' in line:
            parts = line.strip().split(',')
            print(f"CSV Line: {line.strip()}")
            print(f"  Field: {parts[1]}")
            print(f"  Raw Value (from PLC): {parts[4]}")
            print(f"  Scale Factor: {parts[5]}")
            print(f"  Final Value: {parts[6]} kg")
            raw = int(parts[4])
            scale = float(parts[5])
            final = raw / scale
            print(f"  Calculation: {raw} ÷ {scale} = {final}")
            break

def trace_reference_mapping():
    """Trace mapping configuration"""
    print("\n" + "=" * 70)
    print("2. REFERENCE MAPPING (READ_DATA_PLC_MAPPING.json)")
    print("=" * 70)
    
    with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
        mapping = json.load(f)
    
    # Find SILO ID 101 Consumption in mapping
    for item in mapping.get('raw_list', []):
        if 'SILO ID 101 Consumption' in item.get('Informasi', ''):
            print(f"Found in mapping:")
            print(f"  Field: {item['Informasi']}")
            print(f"  Data Type: {item['Data Type']}")
            print(f"  Scale: {item['scale']}")
            print(f"  Memory Address: {item['DM - Memory']}")
            break

def trace_plc_read_logic():
    """Trace PLC read service logic"""
    print("\n" + "=" * 70)
    print("3. PLC READ LOGIC (plc_read_service.py)")
    print("=" * 70)
    
    # Simulate the search logic from plc_read_service.py
    with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
        mapping = json.load(f)
    
    silo_id = 101
    letter = 'a'
    
    print(f"Looking for SILO {silo_id} (letter='{letter}')...")
    
    # This is the logic from plc_read_service.py line 270
    consumption_key = None
    for item in mapping.get('raw_list', []):
        key = item.get('Informasi', '')
        if f"SILO ID {silo_id}" in key or f"SILO {silo_id}" in key:
            if "Consumption" in key:
                consumption_key = key
                print(f"  ✓ Found: {consumption_key}")
                print(f"  Scale: {item['scale']}")
                break
    
    if not consumption_key:
        print(f"  ✗ NOT FOUND - this would cause the issue!")

def trace_service_silo_map():
    """Trace plc_sync_service silo_map"""
    print("\n" + "=" * 70)
    print("4. SERVICE SILO MAP (plc_sync_service.py)")
    print("=" * 70)
    
    with open('app/services/plc_sync_service.py', 'r') as f:
        content = f.read()
    
    # Find silo_map
    import re
    match = re.search(r'silo_map = \{([^}]+)\}', content, re.DOTALL)
    if match:
        silo_map_str = match.group(1)
        
        # Extract entries for a and b
        for line in silo_map_str.split('\n'):
            if '"a":' in line or '"b":' in line:
                print(f"  {line.strip()}")

def trace_database_values():
    """Trace values in database"""
    print("\n" + "=" * 70)
    print("5. DATABASE VALUES (mo_batch table)")
    print("=" * 70)
    
    db = SessionLocal()
    try:
        batches = db.query(TableSmoBatch).order_by(TableSmoBatch.batch_no).limit(1).all()
        if batches:
            batch = batches[0]
            print(f"Batch #{batch.batch_no}: {batch.mo_id}")
            print(f"  consumption_silo_a: {batch.consumption_silo_a}")
            print(f"  consumption_silo_b: {batch.consumption_silo_b}")
    finally:
        db.close()

def analyze_discrepancy():
    """Analyze if there's a discrepancy"""
    print("\n" + "=" * 70)
    print("6. VALUE ANALYSIS")
    print("=" * 70)
    
    # Check if 655 is related to 825 somehow
    csv_value = 825.00
    unknown_value = 655
    
    print(f"CSV expected value: {csv_value}")
    print(f"User-reported value: {unknown_value}")
    print(f"Difference: {csv_value - unknown_value}")
    print(f"Ratio: {csv_value / unknown_value:.3f}")
    
    # Check different scale scenarios
    if 82500 / unknown_value == 100:
        print(f"\nPossible issue: Value {unknown_value} = 82500 ÷ {82500/unknown_value}")
    
    print(f"\nNote: Current database shows 825.0 which is CORRECT")

def main():
    try:
        trace_csv_value()
        trace_reference_mapping()
        trace_plc_read_logic()
        trace_service_silo_map()
        trace_database_values()
        analyze_discrepancy()
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print("The database currently shows correct values (825.0).")
        print("If you're seeing 655 somewhere, please specify:")
        print("  1. Where are you seeing 655? (Odoo UI, Postman, etc?)")
        print("  2. Which batch number?")
        print("=" * 70)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
