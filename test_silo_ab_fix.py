#!/usr/bin/env python3
"""
Test for verifying SILO A & B consumption data sync fix.
Tests that field names now match between reference files and service logic.
"""

import json
import sys

def load_reference_files():
    """Load reference JSON files"""
    with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
        mapping = json.load(f)
    
    with open('app/reference/MASTER_BATCH_REFERENCE.json', 'r') as f:
        batch_ref = json.load(f)
    
    with open('app/reference/read_data_plc_input.csv', 'r') as f:
        csv_lines = f.readlines()
    
    return mapping, batch_ref, csv_lines

def verify_field_names_in_mapping():
    """Verify field names in mapping are standardized"""
    print("=" * 70)
    print("FIELD NAME STANDARDIZATION CHECK")
    print("=" * 70)
    
    with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
        content = f.read()
    
    # Check for non-standard field names
    import re
    non_standard = re.findall(r'SILO [0-9]+ Consumption(?!.*ID)', content)
    if non_standard:
        print(f"❌ Non-standard field names found: {non_standard}")
        return False
    
    # Count standard field names
    standard = re.findall(r'SILO ID [0-9]+ Consumption', content)
    print(f"✓ All field names standardized ({len(set(standard))} unique)")
    return True

def verify_silo_map_in_service():
    """Verify plc_sync_service.py silo_map uses standardized names"""
    print("\n" + "=" * 70)
    print("SERVICE SILO MAP CHECK")
    print("=" * 70)
    
    with open('app/services/plc_sync_service.py', 'r') as f:
        content = f.read()
    
    # Extract silo_map dictionary
    import re
    match = re.search(r'silo_map = \{([^}]+)\}', content, re.DOTALL)
    if not match:
        print("❌ Could not find silo_map in plc_sync_service.py")
        return False
    
    silo_map_str = match.group(1)
    
    # Check field names in silo_map
    field_names = re.findall(r'"([^"]*Consumption[^"]*)"', silo_map_str)
    
    print("Silo map field names:")
    all_standard = True
    for field in field_names:
        if 'SILO ID' in field:
            print(f"  ✓ {field}")
        else:
            print(f"  ❌ {field} (NOT STANDARDIZED)")
            all_standard = False
    
    return all_standard

def verify_field_matching():
    """Verify field names in mapping can be found by service logic"""
    print("\n" + "=" * 70)
    print("FIELD MATCHING LOGIC CHECK")
    print("=" * 70)
    
    with open('app/services/plc_read_service.py', 'r') as f:
        service_content = f.read()
    
    with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
        mapping = json.load(f)
    
    # Silo mapping from plc_read_service.py line 262
    silo_mapping = {
        101: "a", 102: "b", 103: "c", 104: "d", 105: "e",
        106: "f", 107: "g", 108: "h", 109: "i", 110: "j",
        111: "k", 112: "l", 113: "m"
    }
    
    print("Testing field lookup by silo ID...")
    all_found = True
    for silo_id, letter in silo_mapping.items():
        # Check if field name can be found using service logic
        consumption_key = None
        
        # Simulate service logic from plc_read_service.py lines 270-272
        for item in mapping.get("raw_list", []):
            key = item.get("Informasi", "")
            if f"SILO ID {silo_id}" in key or f"SILO {silo_id}" in key:
                if "Consumption" in key:
                    consumption_key = key
                    break
        
        if consumption_key:
            print(f"  ✓ SILO {silo_id} (letter={letter}): {consumption_key}")
        else:
            print(f"  ❌ SILO {silo_id} (letter={letter}): NOT FOUND")
            all_found = False
    
    return all_found

def verify_csv_consistency():
    """Verify CSV file also has standardized field names"""
    print("\n" + "=" * 70)
    print("CSV FIELD CONSISTENCY CHECK")
    print("=" * 70)
    
    with open('app/reference/read_data_plc_input.csv', 'r') as f:
        lines = f.readlines()
    
    consumption_fields = [line.strip() for line in lines if 'Consumption' in line]
    
    print("CSV consumption fields:")
    all_standard = True
    for field in consumption_fields:
        if 'SILO ID' in field:
            print(f"  ✓ {field}")
        else:
            print(f"  ❌ {field} (NOT STANDARDIZED)")
            all_standard = False
    
    return all_standard

def main():
    try:
        print("\n" + "=" * 70)
        print("SILO A & B CONSUMPTION DATA SYNC - COMPLETE FIX VERIFICATION")
        print("=" * 70)
        
        checks = [
            ("Field names standardized in JSON files", verify_field_names_in_mapping),
            ("Service silo_map uses standardized names", verify_silo_map_in_service),
            ("Fields can be matched by service logic", verify_field_matching),
            ("CSV has consistent field names", verify_csv_consistency),
        ]
        
        all_passed = True
        results = []
        
        for check_name, check_func in checks:
            try:
                passed = check_func()
                results.append((check_name, passed))
                all_passed = all_passed and passed
            except Exception as e:
                print(f"\n❌ Error in {check_name}: {e}")
                results.append((check_name, False))
                all_passed = False
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        for check_name, passed in results:
            status = "✓ PASS" if passed else "❌ FAIL"
            print(f"{status}: {check_name}")
        
        print("\n" + "=" * 70)
        if all_passed:
            print("✓ ALL CHECKS PASSED - SILO A & B DATA SYNC SHOULD NOW WORK!")
            print("\nNext steps:")
            print("1. The data sync should now populate actual_consumption_silo_a and _silo_b")
            print("2. Run test_mo_sync.py to verify end-to-end data flow")
            print("3. Check mo_batch table for consumption values in database")
            return 0
        else:
            print("❌ SOME CHECKS FAILED - PLEASE REVIEW ABOVE")
            return 1
    
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
