"""
Test script untuk PLC Write Service
Mendemonstrasikan cara write data ke PLC menggunakan MASTER_BATCH_REFERENCE.json
"""
import asyncio
import httpx


async def test_plc_write():
    base_url = "http://localhost:8000/api"
    
    print("=" * 70)
    print("PLC WRITE SERVICE TEST")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Test 1: Get PLC configuration
        print("\n[Test 1] Get PLC Configuration...")
        response = await client.get(f"{base_url}/plc/config")
        config = response.json()
        
        print(f"  PLC IP: {config['data']['plc_ip']}")
        print(f"  PLC Port: {config['data']['plc_port']}")
        print(f"  Client Node: {config['data']['client_node']}")
        print(f"  PLC Node: {config['data']['plc_node']}")
        print(f"  Batches Loaded: {config['data']['batches_loaded']}")
        
        # Test 2: Write single field
        print("\n[Test 2] Write Single Field (BATCH number)...")
        response = await client.post(
            f"{base_url}/plc/write-field",
            json={
                "batch_name": "BATCH01",
                "field_name": "BATCH",
                "value": 1
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Message: {data['message']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 3: Write ASCII field
        print("\n[Test 3] Write ASCII Field (NO-MO)...")
        response = await client.post(
            f"{base_url}/plc/write-field",
            json={
                "batch_name": "BATCH01",
                "field_name": "NO-MO",
                "value": "WH/MO/00002"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Written: {data['data']['value']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 4: Write multiple fields
        print("\n[Test 4] Write Multiple Fields (Batch Data)...")
        response = await client.post(
            f"{base_url}/plc/write-batch",
            json={
                "batch_name": "BATCH01",
                "data": {
                    "BATCH": 1,
                    "NO-MO": "WH/MO/00002",
                    "NO-BoM": "JF PLUS 25",
                    "finished_goods": "JF PLUS 25",
                    "Quantity Goods_id": 2500,
                    "SILO ID 101 (SILO BESAR)": 101,
                    "SILO 1 Consumption": 825.0,
                }
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Fields Written: {data['data']['field_count']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 5: Write MO batch from database
        print("\n[Test 5] Write MO Batch from Database...")
        response = await client.post(
            f"{base_url}/plc/write-mo-batch",
            json={
                "batch_no": 1,
                "plc_batch_slot": 1
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ MO ID: {data['data']['mo_id']}")
            print(f"  ✓ PLC Batch: {data['data']['plc_batch_name']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        print("\n" + "=" * 70)
        print("TEST COMPLETED!")
        print("=" * 70)
        print("""
Note:
- Test akan gagal jika PLC tidak terkoneksi
- PLC IP default: 192.168.1.2 (bisa diubah di .env)
- MASTER_BATCH_REFERENCE.json digunakan sebagai mapping memory
- Data Type support: REAL, ASCII, boolean

API Endpoints:
1. POST /api/plc/write-field      - Write single field
2. POST /api/plc/write-batch      - Write multiple fields
3. POST /api/plc/write-mo-batch   - Write MO dari database
4. GET  /api/plc/config           - Check PLC config

Next Steps:
- Update PLC_IP di .env sesuai dengan IP PLC aktual
- Test dengan PLC simulator atau device real
- Integrate dengan workflow PLC processing
        """)


if __name__ == "__main__":
    print("\nMake sure uvicorn is running: python -m uvicorn app.main:app --reload\n")
    asyncio.run(test_plc_write())
