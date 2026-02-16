#!/usr/bin/env python3
"""
Debug script to trace silo_a consumption value through the entire read process
"""

import json
import sys
from app.services.plc_read_service import PLCReadService
from app.core.config import get_settings

def check_plc_read_service():
    """Check how PLC read service processes silo_a"""
    print("\n" + "=" * 80)
    print("CHECKING PLC READ SERVICE CONFIG")
    print("=" * 80)
    
    # Load reference files
    with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
        mapping = json.load(f)
    
    # Check silo mapping
    print("\nSilo mapping configuration (from plc_read_service.py):")
    silo_mapping = {
        101: "a", 102: "b", 103: "c", 104: "d", 105: "e",
        106: "f", 107: "g", 108: "h", 109: "i", 110: "j",
        111: "k", 112: "l", 113: "m"
    }
    
    # Check SILO 101 (silo_a)
    silo_id = 101
    print(f"\nLooking for SILO {silo_id} configuration...")
    
    for item in mapping.get('raw_list', []):
        key = item.get('Informasi', '')
        if f"SILO ID {silo_id}" in key:
            print(f"\n  Found field: {key}")
            print(f"  Data Type: {item['Data Type']}")
            print(f"  Memory Address: {item['DM - Memory']}")
            print(f"  Scale: {item['scale']}")
            print(f"  Sample value in mapping: {item.get('Sample')}")
            
            # Check if there's a SILO 101 ID field (which gets the silo number)
            if 'ID' in key:
                print(f"\n  NOTE: This field contains the SILO number, not consumption!")
        
        if "SILO ID 101 Consumption" in key:
            print(f"\n  Consumption field: {key}")
            print(f"    Memory Address: {item['DM - Memory']}")
            print(f"    Scale: {item['scale']}")

def check_silo_101_number_field():
    """Check if SILO ID 101 (number) field is being confused with consumption"""
    print("\n" + "=" * 80)
    print("CHECKING FOR SILO ID vs CONSUMPTION FIELD CONFUSION")
    print("=" * 80)
    
    with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
        mapping = json.load(f)
    
    print("\nAll SILO 101 related fields in mapping:")
    for item in mapping.get('raw_list', []):
        key = item.get('Informasi', '')
        if 'SILO ID 101' in key or 'SILO 101' in key:
            print(f"  - {key:35} | Address: {item.get('DM - Memory')} | Scale: {item['scale']}")

def check_consumption_silo_a_in_csv():
    """Check CSV to see what value SILO A should have"""
    print("\n" + "=" * 80)
    print("CHECKING CSV FOR SILO A CONSUMPTION")
    print("=" * 80)
    
    with open('app/reference/read_data_plc_input.csv', 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        if 'SILO ID 101' in line and 'Consumption' in line:
            parts = line.strip().split(',')
            print(f"\nCSV Entry for SILO ID 101 Consumption:")
            print(f"  Field: {parts[1]}")
            print(f"  Raw PLC Value: {parts[4]}")
            print(f"  Scale: {parts[5]}")
            print(f"  Final Value: {parts[6]} kg")

def analyze_655_value():
    """Analyze if 655.35 has a mathematical relationship to expected values"""
    print("\n" + "=" * 80)
    print("ANALYZING THE 655.35 VALUE")
    print("=" * 80)
    
    reported = 655.35
    expected = 825.0
    
    print(f"\nExpected value: {expected}")
    print(f"Actual value: {reported}")
    print(f"Difference: {expected - reported} = {((expected - reported) / expected * 100):.1f}% less")
    
    # Check if it's a max unsigned value
    max_unsigned_16bit = 65535 / 100
    print(f"\nMax unsigned 16-bit ÷ 100 = {max_unsigned_16bit}")
    if abs(reported - max_unsigned_16bit) < 0.01:
        print("  ⚠️  MATCH! The value 655.35 = 65535 / 100 (max unsigned 16-bit)")
        print("  This suggests silo_a is reading FF FF (max value) instead of correct value")
    
    # Check if it's related to CSV values
    csv_raw = 82500
    print(f"\nCSV raw value for SILO 101: {csv_raw}")
    print(f"If read as: {csv_raw / 100} (correct)")
    print(f"If read as: {65535 / 100} (max value)")
    
    # Check memory address confusion
    print(f"\nPossible issue: Is silo_a reading from wrong memory address?")
    print(f"  Expected to read SILO ID 101 Consumption → ~825.0")
    print(f"  Actually reading → 655.35 (which = max 16-bit)")

def main():
    try:
        check_plc_read_service()
        check_silo_101_number_field()
        check_consumption_silo_a_in_csv()
        analyze_655_value()
        
        print("\n" + "=" * 80)
        print("DIAGNOSIS")
        print("=" * 80)
        print("""
The value 655.35 suggests:
1. Either a wrong memory address is being read for silo_a
2. Or the raw value being read is 65535 (max unsigned 16-bit)
3. Or there's a conversion issue specific to silo_a

The data sync IS working (actual_consumption_silo_a is no longer NULL).
But the VALUE being read appears incorrect.

Recommendation:
1. Check plc_read_service.py to see how silo_a value is extracted
2. Verify the memory address for "SILO ID 101 Consumption" (should be D6027)
3. Check if there's a hardcoded address or default value for silo_a
4. Run a direct PLC read test to see raw memory values
        """)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
