#!/usr/bin/env python3
"""
Automated script to write PLC READ area from CSV without user interaction
Used for testing and debugging consumption value reads
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from test_write_read_area_from_csv import ReadAreaCsvWriter

def main():
    csv_path = Path("app/reference/read_data_plc_input.csv")
    
    print("\n" + "=" * 80)
    print("WRITE PLC READ AREA FROM CSV (Automated)")
    print("=" * 80)
    print(f"CSV path: {csv_path}")
    print("This will write values into D6001-D6058 using CSV Value column.")
    print("\nInitializing write operation...")
    
    try:
        writer = ReadAreaCsvWriter(csv_path)
        results = writer.write_from_csv()
        
        print("\n" + "=" * 80)
        print("WRITE RESULTS")
        print("=" * 80)
        print(f"[OK] Success: {results['success']} fields")
        print(f"[FAIL] Failed: {results['failed']} fields")
        
        if results["errors"]:
            print("\nErrors:")
            for error in results["errors"]:
                print(f"  - {error}")
        else:
            print("\n[OK] All fields written successfully!")
            print("\nNow call test_mo_sync.py to verify consumption values are correct")
        
        return 0
    
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
