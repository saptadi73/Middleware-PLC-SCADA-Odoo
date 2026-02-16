#!/usr/bin/env python3
"""
Test to verify what was actually written to DM memory in the PLC
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.plc_read_service import get_plc_read_service
from app.core.config import get_settings

def main():
    print("\n" + "=" * 80)
    print("CHECKING WHAT WAS WRITTEN TO PLC MEMORY")
    print("=" * 80)
    
    settings = get_settings()
    print(f"\nPLC: {settings.plc_ip}:{settings.plc_port}")
    
    try:
        plc_service = get_plc_read_service()
        
        addresses_to_check = [
            ("NO-MO", "WH/MO/00001"),
            ("Quantity Goods_id", 2500),
            ("SILO ID 101 (SILO BESAR)", 101),
            ("SILO ID 101 Consumption", 825.0),
            ("SILO ID 102 (SILO BESAR)", 102),
            ("SILO ID 102 Consumption", 375.0),
        ]
        
        print("\nReading sample fields from PLC:")
        print("-" * 80)
        
        for field_name, expected_value in addresses_to_check:
            try:
                actual_value = plc_service.read_field(field_name)
                status = "[OK]" if str(actual_value) == str(expected_value) else "[MISMATCH]"
                print(f"{status} {field_name:40} = {actual_value:15} (expected: {expected_value})")
            except Exception as e:
                print(f"[ERROR] {field_name:40} - {e}")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
