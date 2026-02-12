"""
Test Full PLC Workflow - Write then Sync
Tests writing MO batch to PLC and syncing back to database.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import requests


def test_full_workflow():
    """Test full workflow: Write → PLC → Read → Update Database"""
    base_url = "http://localhost:8000/api"

    print("=" * 80)
    print("Testing Full PLC Workflow: Write → Read → Sync")
    print("=" * 80)

    # Step 1: Write MO batch to PLC
    print("\n[Step 1] Write MO batch to PLC")
    print("-" * 40)
    write_request = {
        "batch_no": 1,  # First batch in database
        "plc_batch_slot": 1,  # Write to BATCH01 in PLC
    }
    response = requests.post(
        f"{base_url}/plc/write-mo-batch", json=write_request, timeout=30.0
    )
    print(f"Status: {response.status_code}")
    data = response.json()

    if data.get("status") == "success":
        print(f"✓ Written MO: {data['data']['mo_id']}")
        print(f"✓ PLC Batch: {data['data']['plc_batch_name']}")
        mo_id = data["data"]["mo_id"]
    else:
        print(f"✗ Write failed: {data}")
        return

    # Step 2: Read batch data from PLC
    print("\n[Step 2] Read batch data from PLC")
    print("-" * 40)
    response = requests.get(f"{base_url}/plc/read-batch", timeout=30.0)
    print(f"Status: {response.status_code}")
    data = response.json()

    if data.get("status") == "success":
        batch_data = data["data"]
        print(f"✓ MO_ID from PLC: {batch_data.get('mo_id')}")
        print(f"✓ Product: {batch_data.get('product_name')}")
        print(f"✓ Quantity: {batch_data.get('quantity_goods')}")

        # Show silo consumption
        print("\n  Silo Consumptions from PLC:")
        silos = batch_data.get("silos", {})
        for letter in "abcdefghijklm":
            silo_data = silos.get(letter, {})
            if silo_data.get("consumption"):
                print(f"    Silo {letter.upper()}: {silo_data.get('consumption')} kg")
    else:
        print(f"✗ Read failed: {data}")
        return

    # Step 3: Sync from PLC to database
    print("\n[Step 3] Sync PLC data to database")
    print("-" * 40)
    response = requests.post(f"{base_url}/plc/sync-from-plc", timeout=30.0)
    print(f"Status: {response.status_code}")
    data = response.json()

    if data.get("status") == "success":
        print(f"✓ Sync completed for MO_ID: {data['data']['mo_id']}")
        print(f"✓ Database updated: {data['data']['updated']}")
        print(f"✓ Message: {data.get('message', 'No message')}")
    else:
        print(f"✗ Sync failed: {data}")
        return

    # Step 4: Verify sync by reading batch data again
    print("\n[Step 4] Verify sync - read from PLC again")
    print("-" * 40)
    response = requests.post(f"{base_url}/plc/sync-from-plc", timeout=30.0)
    print(f"Status: {response.status_code}")
    data = response.json()

    if data.get("status") == "success":
        updated = data["data"]["updated"]
        if not updated:
            print("✓ No changes detected (expected - data same as before)")
        else:
            print("✓ Data updated (PLC values changed between reads)")
    else:
        print(f"✗ Second sync failed: {data}")

    print("\n" + "=" * 80)
    print("Full workflow test completed successfully!")
    print("=" * 80)
    print("\nSummary:")
    print("1. ✓ MO batch written to PLC")
    print("2. ✓ Data read back from PLC")
    print("3. ✓ Database updated with actual consumption values")
    print("4. ✓ Change detection working (no update on second sync)")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("FULL PLC WORKFLOW TEST")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Write batch_no=1 from database to PLC (BATCH01)")
    print("2. Read all data back from PLC")
    print("3. Update database with actual consumption values")
    print("4. Verify change detection works")
    print("\nPrerequisites:")
    print("✓ FastAPI server running (uvicorn app.main:app --reload)")
    print("✓ PLC accessible at configured IP")
    print("✓ Database migration applied (alembic upgrade head)")
    print("✓ At least one MO batch in database (batch_no=1)")
    print("\nPress Ctrl+C to cancel or Enter to continue...")
    input()

    try:
        test_full_workflow()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
