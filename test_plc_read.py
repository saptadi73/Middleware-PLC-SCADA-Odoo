"""
Test script untuk PLC Read Service
Mendemonstrasikan cara read data dari PLC menggunakan READ_DATA_PLC_MAPPING.json
"""
import asyncio
import httpx


async def test_plc_read():
    base_url = "http://localhost:8000/api"
    
    print("=" * 70)
    print("PLC READ SERVICE TEST")
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
        
        # Test 2: Read single field (NO-MO)
        print("\n[Test 2] Read Single Field (NO-MO)...")
        response = await client.get(f"{base_url}/plc/read-field/NO-MO")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Field: {data['data']['field_name']}")
            print(f"  ✓ Value: {data['data']['value']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 3: Read another field (finished_goods)
        print("\n[Test 3] Read Finished Goods Field...")
        response = await client.get(f"{base_url}/plc/read-field/finished_goods")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Value: {data['data']['value']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 4: Read quantity
        print("\n[Test 4] Read Quantity Goods_id...")
        response = await client.get(f"{base_url}/plc/read-field/Quantity Goods_id")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Value: {data['data']['value']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 5: Read silo consumption
        print("\n[Test 5] Read SILO 1 Consumption...")
        response = await client.get(f"{base_url}/plc/read-field/SILO 1 Consumption")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Value: {data['data']['value']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 6: Read all fields
        print("\n[Test 6] Read All Fields...")
        response = await client.get(f"{base_url}/plc/read-all")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            print(f"  ✓ Message: {data['message']}")
            print(f"  ✓ Sample data:")
            for key, value in list(data['data'].items())[:5]:
                print(f"     - {key}: {value}")
            print(f"  ... and {len(data['data']) - 5} more fields")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        # Test 7: Read formatted batch data
        print("\n[Test 7] Read Formatted Batch Data...")
        response = await client.get(f"{base_url}/plc/read-batch")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Status: {data['status']}")
            batch = data['data']
            print(f"  ✓ MO ID: {batch['mo_id']}")
            print(f"  ✓ Product: {batch['product_name']}")
            print(f"  ✓ Quantity: {batch['quantity']}")
            print(f"  ✓ Silos loaded: {len(batch['silos'])}")
            print(f"  ✓ Status: Manufacturing={batch['status']['manufacturing']}, Operation={batch['status']['operation']}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            print(f"  ✗ Response: {response.text}")
        
        print("\n" + "=" * 70)
        print("TEST COMPLETED!")
        print("=" * 70)
        print("""
Note:
- Test akan gagal jika PLC tidak terkoneksi atau data belum di-write
- READ_DATA_PLC_MAPPING.json digunakan sebagai mapping memory
- Data Type support: REAL, ASCII, boolean
- Scale factor otomatis diterapkan untuk REAL values

API Endpoints:
1. GET /api/plc/read-field/{field_name}  - Read single field
2. GET /api/plc/read-all                 - Read all fields
3. GET /api/plc/read-batch               - Read formatted batch data
4. GET /api/plc/config                   - Check PLC config

Next Steps:
- Pastikan data sudah di-write ke PLC terlebih dahulu
- Gunakan test_plc_write_from_odoo.py untuk write data
- Verify hasil read dengan monitoring tool PLC
        """)


if __name__ == "__main__":
    print("\nMake sure uvicorn is running: python -m uvicorn app.main:app --reload\n")
    asyncio.run(test_plc_read())
