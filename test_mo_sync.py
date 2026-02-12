"""
Test script untuk memanggil endpoint mo-list-detailed dan cek database
"""
import asyncio
import httpx
from sqlalchemy import create_engine, text

from app.core.config import get_settings


async def test_mo_sync():
    settings = get_settings()
    
    print("=" * 60)
    print("Testing MO Sync to Database")
    print("=" * 60)
    
    # 1. Panggil endpoint FastAPI
    print("\n1. Fetching MO list from FastAPI endpoint...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8000/api/scada/mo-list-detailed",
            params={"limit": 10, "offset": 0}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Status: {data.get('status')}")
            print(f"   ✓ Message: {data.get('message')}")
            print(f"   ✓ Total fetched: {data.get('data', {}).get('total_fetched')}")
            print(f"   ✓ Count from Odoo: {data.get('data', {}).get('count')}")
        else:
            print(f"   ✗ Error: {response.status_code}")
            print(f"   ✗ Response: {response.text}")
            return
    
    # 2. Cek database
    print("\n2. Checking mo_batch table in database...")
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Count records
        result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
        count = result.scalar()
        print(f"   ✓ Total records in mo_batch: {count}")
        
        # Show sample data
        if count > 0:
            result = conn.execute(
                text("""
                SELECT 
                    batch_no, 
                    mo_id, 
                    consumption,
                    equipment_id_batch,
                    component_silo_a_name,
                    consumption_silo_a
                FROM mo_batch 
                ORDER BY batch_no 
                LIMIT 5
                """)
            )
            
            print("\n   Sample data from mo_batch:")
            print("   " + "-" * 55)
            for row in result:
                print(f"   Batch #{row.batch_no}: {row.mo_id}")
                print(f"     Equipment: {row.equipment_id_batch}")
                print(f"     Consumption: {row.consumption} kg")
                if row.component_silo_a_name:
                    print(f"     Silo A: {row.component_silo_a_name} ({row.consumption_silo_a} kg)")
                print()
    
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_mo_sync())
