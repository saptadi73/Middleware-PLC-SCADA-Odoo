#!/usr/bin/env python3
"""
Simple test to verify silo_a consumption value after writing to PLC
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.plc_read_service import get_plc_read_service

def main():
    print("\n" + "=" * 80)
    print("VERIFYING SILO A CONSUMPTION AFTER PLC WRITE")
    print("=" * 80)
    
    try:
        plc_service = get_plc_read_service()
        
        print("\nReading from PLC...")
        
        # Read silo_a consumption
        consumption = plc_service.read_field("SILO ID 101 Consumption")
        print(f"\nSILO ID 101 Consumption = {consumption}")
        
        if consumption == 825.0:
            print("[OK] Correct! Value is now 825.0 as expected")
            return 0
        elif consumption == 655.35:
            print("[WRONG] Value is still 655.35 (max 16-bit / 100)")
            return 1
        else:
            print(f"[INFO] Value is {consumption}")
            return 0
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
