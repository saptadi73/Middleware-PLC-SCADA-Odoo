"""
Direct PLC Read Test - tanpa HTTP API
Test langsung menggunakan PLCReadService
"""
import logging

from app.services.plc_read_service import get_plc_read_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("DIRECT PLC READ TEST")
    print("=" * 70)
    
    service = get_plc_read_service()
    
    print(f"\nLoaded {len(service.mapping)} fields from READ_DATA_PLC_MAPPING.json")
    
    # Test 1: Read NO-MO
    print("\n[Test 1] Read NO-MO...")
    try:
        value = service.read_field("NO-MO")
        print(f"  ✓ NO-MO: {value}")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
    
    # Test 2: Read finished_goods
    print("\n[Test 2] Read finished_goods...")
    try:
        value = service.read_field("finished_goods")
        print(f"  ✓ finished_goods: {value}")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
    
    # Test 3: Read NO-BoM
    print("\n[Test 3] Read NO-BoM...")
    try:
        value = service.read_field("NO-BoM")
        print(f"  ✓ NO-BoM: {value}")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
    
    # Test 4: Read Quantity
    print("\n[Test 4] Read Quantity Goods_id...")
    try:
        value = service.read_field("Quantity Goods_id")
        print(f"  ✓ Quantity: {value}")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
    
    # Test 5: Read silo consumption (dengan scale)
    print("\n[Test 5] Read SILO 1 Consumption (scaled)...")
    try:
        value = service.read_field("SILO 1 Consumption")
        print(f"  ✓ SILO 1 Consumption: {value}")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
    
    # Test 6: Read formatted batch data
    print("\n[Test 6] Read Formatted Batch Data...")
    try:
        batch_data = service.read_batch_data()
        print(f"  ✓ MO ID: {batch_data['mo_id']}")
        print(f"  ✓ Product: {batch_data['product_name']}")
        print(f"  ✓ BoM: {batch_data['bom_name']}")
        print(f"  ✓ Quantity: {batch_data['quantity']}")
        print(f"  ✓ Weight Finished: {batch_data['weight_finished_good']}")
        print(f"  ✓ Status Manufacturing: {batch_data['status']['manufacturing']}")
        print(f"  ✓ Status Operation: {batch_data['status']['operation']}")
        
        print(f"\n  Silos:")
        for letter, silo in batch_data['silos'].items():
            if silo['consumption'] > 0:
                print(f"    - Silo {letter.upper()} (ID {silo['id']}): {silo['consumption']}")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
    
    # Test 7: Read all fields
    print("\n[Test 7] Read All Fields (summary)...")
    try:
        all_data = service.read_all_fields()
        print(f"  ✓ Total fields read: {len(all_data)}")
        
        # Show sample
        print("\n  Sample data (first 10 fields):")
        for idx, (key, value) in enumerate(all_data.items()):
            if idx >= 10:
                break
            print(f"    {idx+1}. {key}: {value}")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
    
    print("\n" + "=" * 70)
    print("DIRECT TEST COMPLETED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
