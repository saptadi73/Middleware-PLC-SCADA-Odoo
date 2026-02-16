"""
Test Script: Debug Equipment Failure Odoo Sync
Untuk diagnose kenapa data tidak terima di Odoo
"""
import asyncio
import logging
import httpx
from datetime import datetime
import json
import os
from dotenv import load_dotenv

# Load .env configuration
load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get configuration from .env
ODOO_BASE_URL = os.getenv("ODOO_BASE_URL", "http://localhost:8070")
ODOO_DB = os.getenv("ODOO_DB", "manukanjabung")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

print(f"\n==== Configuration from .env ====")
print(f"ODOO_BASE_URL: {ODOO_BASE_URL}")
print(f"ODOO_DB: {ODOO_DB}")
print(f"ODOO_USERNAME: {ODOO_USERNAME}")
print("================================\n")


async def test_odoo_connection():
    """Test 1: Check koneksi ke Odoo"""
    print("\n" + "="*60)
    print("TEST 1: Check Odoo Connection")
    print("="*60)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ODOO_BASE_URL}/")
            print(f"✓ Odoo reachable: Status {response.status_code}")
            print(f"  URL: {ODOO_BASE_URL}")
            return True
    except Exception as e:
        print(f"✗ Odoo not reachable: {e}")
        print(f"  Tried URL: {ODOO_BASE_URL}")
        return False


async def test_odoo_authentication():
    """Test 2: Check Odoo authentication"""
    print("\n" + "="*60)
    print("TEST 2: Check Odoo Authentication")
    print("="*60)
    
    auth_payload = {
        "db": ODOO_DB,
        "login": ODOO_USERNAME,
        "password": ODOO_PASSWORD,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Attempting auth at: {ODOO_BASE_URL}/api/scada/authenticate")
            response = await client.post(
                f"{ODOO_BASE_URL}/api/scada/authenticate",
                json=auth_payload
            )
            
            print(f"✓ Response status: {response.status_code}")
            result = response.json()
            print(f"✓ Response body: {json.dumps(result, indent=2)}")
            
            # Handle JSONRPC response format
            if response.status_code == 200 and (result.get("result", {}).get("status") == "success" or result.get("status") == "success"):
                print("✓ Authentication successful!")
                return True, client
            else:
                print(f"✗ Authentication failed")
                return False, None
                
    except Exception as e:
        print(f"✗ Auth request failed: {e}")
        return False, None


async def test_equipment_master():
    """Test 3: Check equipment master di Odoo"""
    print("\n" + "="*60)
    print("TEST 3: Check Equipment Master in Odoo")
    print("="*60)
    
    auth_payload = {
        "db": ODOO_DB,
        "login": ODOO_USERNAME,
        "password": ODOO_PASSWORD,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Authenticate
            auth_response = await client.post(
                f"{ODOO_BASE_URL}/api/scada/authenticate",
                json=auth_payload
            )
            auth_result = auth_response.json()
            
            # Check if authentication succeeded (JSONRPC format)
            auth_status = auth_result.get("result", {}).get("status") or auth_result.get("status")
            if auth_response.status_code != 200 or auth_status != "success":
                print(f"✗ Authentication failed")
                return False
            
            # Check equipment master
            equipment_codes = ["PLC01", "silo101", "silo102"]
            found_count = 0
            
            for equipment_code in equipment_codes:
                try:
                    response = await client.get(
                        f"{ODOO_BASE_URL}/api/scada/equipment",
                        params={"code": equipment_code}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Handle both formats
                        result_data = data.get("result", data.get("data"))
                        if result_data:
                            found_count += 1
                            print(f"✓ Equipment '{equipment_code}' found")
                        else:
                            print(f"ⓘ Equipment '{equipment_code}' not found (OK, might not be in Odoo)")
                    else:
                        print(f"ⓘ Equipment '{equipment_code}': Status {response.status_code}")
                        
                except Exception as e:
                    print(f"ⓘ Check equipment '{equipment_code}' failed: {e}")
            
            if found_count > 0:
                print(f"\nℹ Found {found_count}/{len(equipment_codes)} equipment in Odoo")
            
            return True
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


async def test_equipment_failure_api():
    """Test 4: Test POST /api/scada/equipment-failure endpoint"""
    print("\n" + "="*60)
    print("TEST 4: Test Equipment Failure API Endpoint")
    print("="*60)
    
    auth_payload = {
        "db": ODOO_DB,
        "login": ODOO_USERNAME,
        "password": ODOO_PASSWORD,
    }
    
    failure_payload = {
        "equipment_code": "PLC01",
        "description": "Motor overload saat proses mixing",
        "date": "2026-02-15 08:30:00"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Authenticate
            logger.info("Step 1: Authenticating...")
            auth_response = await client.post(
                f"{ODOO_BASE_URL}/api/scada/authenticate",
                json=auth_payload
            )
            auth_result = auth_response.json()
            
            # Check if authentication succeeded (JSONRPC format)
            auth_status = auth_result.get("result", {}).get("status") or auth_result.get("status")
            if auth_response.status_code != 200 or auth_status != "success":
                print(f"✗ Authentication failed")
                return False
            
            print(f"✓ Authentication successful")
            
            # Create failure report
            logger.info("Step 2: Creating equipment failure report...")
            failure_response = await client.post(
                f"{ODOO_BASE_URL}/api/scada/equipment-failure",
                json=failure_payload
            )
            
            print(f"✓ Response status: {failure_response.status_code}")
            result = failure_response.json()
            print(f"✓ Response body:")
            print(json.dumps(result, indent=2))
            
            # Handle both response formats
            result_data = result.get("result", result)
            if failure_response.status_code == 200 and (result_data.get("status") == "success" or "id" in str(result_data)):
                print(f"\n✓✓✓ SUCCESS! Equipment failure created in Odoo")
                return True
            else:
                print(f"\n✗ Creation might have failed or endpoint not configured")
                print(f"  Make sure equipment master exists in Odoo")
                return False
                
    except httpx.HTTPError as e:
        print(f"✗ HTTP error: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"  Response status: {e.response.status_code}")
            try:
                print(f"  Response body: {e.response.text}")
            except:
                pass
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║  Equipment Failure Odoo Sync - Debug Test Suite  ║")
    print("╚" + "="*58 + "╝")
    
    results = {}
    
    # Test 1: Connection
    results["Odoo Connection"] = await test_odoo_connection()
    
    if not results["Odoo Connection"]:
        print("\n⚠️  Odoo is not running! Cannot proceed with other tests.")
        return
    
    # Test 2: Authentication
    results["Odoo Authentication"] = await test_odoo_authentication()
    
    # Test 3: Equipment Master
    results["Equipment Master"] = await test_equipment_master()
    
    # Test 4: Equipment Failure API
    results["Equipment Failure API"] = await test_equipment_failure_api()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("✓✓✓ ALL TESTS PASSED! Odoo sync should work.")
    else:
        print("✗✗✗ Some tests failed. Check details above.")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
