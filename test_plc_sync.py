"""
Test PLC Sync Service
Tests reading from PLC and updating mo_batch table.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import requests


def test_plc_sync():
    """Test syncing data from PLC to database"""
    base_url = "http://localhost:8000/api"

    print("=" * 80)
    print("Testing PLC Sync Service")
    print("=" * 80)

    # Test 1: Sync from PLC
    print("\n[1] Sync data from PLC to database")
    response = requests.post(f"{base_url}/plc/sync-from-plc", timeout=30.0)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")

    if data.get("status") == "success":
        print(f"✓ MO_ID: {data['data']['mo_id']}")
        print(f"✓ Updated: {data['data']['updated']}")
    else:
        print(f"✗ Error: {data}")

    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("PLC SYNC SERVICE TEST")
    print("=" * 80)
    print("\nMake sure:")
    print("1. FastAPI server is running (uvicorn app.main:app --reload)")
    print("2. PLC is accessible at configured IP")
    print("3. Database migration is applied (alembic upgrade head)")
    print("4. At least one MO batch exists in database")
    print("\nPress Ctrl+C to cancel or Enter to continue...")
    input()

    try:
        test_plc_sync()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        raise
