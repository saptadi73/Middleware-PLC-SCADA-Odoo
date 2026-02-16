#!/usr/bin/env python3
"""
Debug script to trace exactly what's happening when reading silo_a from the real PLC
"""

import json
import sys
from app.services.plc_read_service import PLCReadService, get_plc_read_service
from app.core.config import get_settings

def trace_silo_a_read():
    """Trace the exact read process for silo_a"""
    print("\n" + "=" * 90)
    print("TRACING SILO A READS FROM ACTUAL PLC")
    print("=" * 90)
    
    settings = get_settings()
    print(f"\nPLC Configuration:")
    print(f"  IP: {settings.plc_ip}")
    print(f"  Port: {settings.plc_port}")
    print(f"  Timeout: {settings.plc_timeout_sec}s")
    
    try:
        # Get PLC read service
        plc_service = get_plc_read_service()
        
        # Step 1: Read SILO ID 101 (silo number)
        print(f"\n" + "-" * 90)
        print("Step 1: Read SILO ID 101 field (the silo number)")
        print("-" * 90)
        
        try:
            silo_id_value = plc_service.read_field("SILO ID 101 (SILO BESAR)")
            print(f"✓ SILO ID 101 (SILO BESAR) = {silo_id_value}")
            print(f"  (Should be 101)")
        except Exception as e:
            print(f"✗ Error reading SILO ID 101: {e}")
        
        # Step 2: Read SILO ID 101 Consumption
        print(f"\n" + "-" * 90)
        print("Step 2: Read SILO ID 101 Consumption")
        print("-" * 90)
        
        try:
            consumption_value = plc_service.read_field("SILO ID 101 Consumption")
            print(f"✓ SILO ID 101 Consumption = {consumption_value}")
            print(f"  (Test CSV shows: 825.0)")
            print(f"  (Real PLC shows: {consumption_value})")
            
            # Analyze the raw value
            if consumption_value == 655.35:
                print(f"\n  ⚠️  Value is 655.35 = 65535 ÷ 100")
                print(f"  This indicates the raw PLC memory is returning 65535 (max 16-bit)")
                print(f"\n  Possible causes:")
                print(f"    1. Memory address D6027 hasn't been initialized")
                print(f"    2. Memory address D6027 is incorrect")
                print(f"    3. PLC program isn't writing to that address")
                print(f"    4. The batch hasn't processed yet")
        except Exception as e:
            print(f"✗ Error reading SILO ID 101 Consumption: {e}")
        
        # Step 3: Read all fields and show what's in the all_fields dict
        print(f"\n" + "-" * 90)
        print("Step 3: Check all_fields dictionary")
        print("-" * 90)
        
        try:
            all_fields = plc_service.read_all_fields()
            
            # Show SILO 101 related fields
            silo_101_fields = {k: v for k, v in all_fields.items() if 'SILO ID 101' in k}
            print(f"\nFound {len(silo_101_fields)} SILO 101 fields in all_fields:")
            for field_name, value in silo_101_fields.items():
                print(f"  {field_name:40} = {value}")
            
        except Exception as e:
            print(f"✗ Error reading all_fields: {e}")
        
        # Step 4: Check mapping addresses
        print(f"\n" + "-" * 90)
        print("Step 4: Verify mapping addresses for SILO 101")
        print("-" * 90)
        
        with open('app/reference/READ_DATA_PLC_MAPPING.json', 'r') as f:
            mapping = json.load(f)
        
        for item in mapping.get('raw_list', []):
            if 'SILO ID 101' in item.get('Informasi', ''):
                print(f"\nMapping entry:")
                print(f"  Field: {item['Informasi']}")
                print(f"  Address: {item['DM - Memory']}")
                print(f"  Data Type: {item['Data Type']}")
                print(f"  Scale: {item['scale']}")
                print(f"  Sample: {item['Sample']}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

def main():
    print("\n" + "=" * 90)
    print("SILO A CONSUMPTION DEBUG")
    print("=" * 90)
    print("\nThis script will trace what's being read from the PLC")
    print("and show why actual_consumption_silo_a might be 655.35 instead of 825.0")
    
    return trace_silo_a_read()

if __name__ == '__main__':
    sys.exit(main())
