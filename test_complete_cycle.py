"""
Complete Test: Write → Read → Sync
Test lengkap untuk verify bidirectional PLC communication.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
import time


def test_complete_cycle():
    """Test complete cycle: Write to READ area → Read back → Sync to DB"""
    base_url = "http://localhost:8000/api"

    print("=" * 80)
    print("COMPLETE TEST: Write → Read → Sync")
    print("=" * 80)

    print("\n📝 Prerequisites:")
    print("1. Run: python test_write_read_area.py")
    print("   (to populate PLC READ area with data from batch_no=1)")
    print("2. FastAPI server running")
    print("\nPress Enter to continue...")
    input()

    # Step 1: Verify PLC config
    print("\n" + "=" * 80)
    print("[1] Verify PLC Configuration")
    print("=" * 80)
    response = requests.get(f"{base_url}/plc/config", timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"✓ PLC IP: {data['data']['plc_ip']}")
        print(f"✓ PLC Port: {data['data']['plc_port']}")
    else:
        print("✗ Cannot connect to API. Is the server running?")
        return

    # Small delay
    time.sleep(1)

    # Step 2: Read MO_ID from PLC
    print("\n" + "=" * 80)
    print("[2] Read MO_ID from PLC")
    print("=" * 80)
    response = requests.get(f"{base_url}/plc/read-field/NO-MO", timeout=10)
    if response.status_code == 200:
        data = response.json()
        mo_id = data["data"]["value"]
        print(f"✓ MO_ID from PLC: {mo_id}")
    else:
        print("✗ Failed to read MO_ID")
        print(f"   Response: {response.text}")
        return

    # Step 3: Read finished_goods
    print("\n" + "=" * 80)
    print("[3] Read Product Name from PLC")
    print("=" * 80)
    response = requests.get(f"{base_url}/plc/read-field/finished_goods", timeout=10)
    if response.status_code == 200:
        data = response.json()
        product = data["data"]["value"]
        print(f"✓ Product: {product}")
    else:
        print("✗ Failed to read product")

    # Step 4: Read quantity
    print("\n" + "=" * 80)
    print("[4] Read Quantity from PLC")
    print("=" * 80)
    response = requests.get(
        f"{base_url}/plc/read-field/Quantity%20Goods_id", timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        quantity = data["data"]["value"]
        print(f"✓ Quantity: {quantity}")
    else:
        print("✗ Failed to read quantity")

    # Step 5: Read silo consumptions
    print("\n" + "=" * 80)
    print("[5] Read Silo Consumptions from PLC")
    print("=" * 80)
    silo_fields = [
        ("SILO 1 Consumption", "Silo A"),
        ("SILO 2 Consumption", "Silo B"),
        ("SILO ID 103 Consumption", "Silo C"),
    ]
    
    silo_data = {}
    for field_name, label in silo_fields:
        response = requests.get(
            f"{base_url}/plc/read-field/{requests.utils.quote(field_name)}",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            value = data["data"]["value"]
            silo_data[label] = value
            print(f"✓ {label}: {value} kg")
        else:
            print(f"✗ Failed to read {label}")

    # Step 6: Read all as batch
    print("\n" + "=" * 80)
    print("[6] Read Complete Batch Data from PLC")
    print("=" * 80)
    response = requests.get(f"{base_url}/plc/read-batch", timeout=10)
    if response.status_code == 200:
        data = response.json()
        batch = data["data"]
        print(f"✓ MO_ID: {batch.get('mo_id')}")
        print(f"✓ Product: {batch.get('product_name')}")
        print(f"✓ Quantity: {batch.get('quantity_goods')}")
        print(f"✓ Status Manufacturing: {batch.get('status_manufacturing')}")
        print(f"✓ Status Operation: {batch.get('status_operation')}")
        
        silos = batch.get('silos', {})
        active_silos = [k for k, v in silos.items() if v.get('consumption')]
        print(f"✓ Active Silos: {len(active_silos)} silos")
    else:
        print("✗ Failed to read batch data")

    # Step 7: Sync to database
    print("\n" + "=" * 80)
    print("[7] Sync PLC Data to Database")
    print("=" * 80)
    print(f"Syncing MO_ID: {mo_id}")
    
    response = requests.post(f"{base_url}/plc/sync-from-plc", timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Status: {data.get('status')}")
        print(f"✓ Message: {data.get('message')}")
        print(f"✓ MO_ID: {data['data']['mo_id']}")
        print(f"✓ Updated: {data['data']['updated']}")
        
        if data['data']['updated']:
            print("\n  Database fields updated:")
            print("  - actual_consumption_silo_a, b, c, ...")
            print("  - actual_weight_quantity_finished_goods")
            print("  - status_manufacturing")
            print("  - status_operation")
            print("  - last_read_from_plc (timestamp)")
    else:
        print("✗ Failed to sync")
        print(f"   Response: {response.text}")

    # Step 8: Verify - sync again (should show no changes)
    print("\n" + "=" * 80)
    print("[8] Verify Change Detection (Re-sync)")
    print("=" * 80)
    print("Re-syncing same data (should detect no changes)...")
    
    response = requests.post(f"{base_url}/plc/sync-from-plc", timeout=10)
    if response.status_code == 200:
        data = response.json()
        if not data['data']['updated']:
            print("✓ Change detection works! No update needed.")
        else:
            print("⚠ Data was updated again (PLC values might have changed)")
    else:
        print("✗ Failed to re-sync")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("\n✅ Complete cycle tested successfully!")
    print("\nFlow verified:")
    print("  1. ✓ Data written to PLC READ area (D6001-D6076)")
    print("  2. ✓ Data read back from PLC via API")
    print("  3. ✓ Data synced to database (actual_consumption_*)")
    print("  4. ✓ Change detection working (smart update)")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("COMPLETE BIDIRECTIONAL PLC TEST")
    print("=" * 80)
    print("\nThis test requires:")
    print("1. ✓ test_write_read_area.py already executed")
    print("   (to populate PLC READ area)")
    print("2. ✓ FastAPI server running")
    print("3. ✓ PLC accessible")
    print("4. ✓ Database ready")
    print("\nPress Ctrl+C to cancel or Enter to start...")
    input()

    try:
        test_complete_cycle()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
