"""
Demo script: Full cycle auto-sync test
Mendemonstrasikan scheduler behavior dengan clear → trigger sync → verify
"""
import asyncio
import httpx


async def demo_auto_sync_cycle():
    base_url = "http://localhost:8000/api"
    
    print("=" * 70)
    print("AUTO-SYNC FULL CYCLE DEMO")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Step 1: Check initial status
        print("\n[Step 1] Check current batch status...")
        response = await client.get(f"{base_url}/admin/batch-status")
        data = response.json()
        
        initial_count = data["data"]["total_batches"]
        print(f"  Current batches: {initial_count}")
        
        if initial_count > 0:
            print("  Sample batches:")
            for batch in data["data"]["batches"][:3]:
                print(f"    - Batch #{batch['batch_no']}: {batch['mo_id']}")
        
        # Step 2: Clear table
        print("\n[Step 2] Clearing mo_batch table (simulate PLC done)...")
        response = await client.post(f"{base_url}/admin/clear-mo-batch")
        data = response.json()
        
        print(f"  ✓ Deleted: {data['deleted_count']} records")
        
        # Step 3: Verify empty
        print("\n[Step 3] Verify table is empty...")
        response = await client.get(f"{base_url}/admin/batch-status")
        data = response.json()
        
        print(f"  Table empty: {data['data']['is_empty']}")
        print(f"  Total batches: {data['data']['total_batches']}")
        
        # Step 4: Trigger manual sync
        print("\n[Step 4] Trigger manual sync (fetch new batches from Odoo)...")
        response = await client.post(f"{base_url}/admin/trigger-sync")
        data = response.json()
        
        print(f"  Status: {data['status']}")
        print(f"  Message: {data['message']}")
        
        # Step 5: Verify data inserted
        print("\n[Step 5] Verify new batches inserted...")
        await asyncio.sleep(1)  # Wait for database commit
        
        response = await client.get(f"{base_url}/admin/batch-status")
        data = response.json()
        
        final_count = data["data"]["total_batches"]
        print(f"  Total batches: {final_count}")
        
        if final_count > 0:
            print("  New batches fetched:")
            for batch in data["data"]["batches"][:5]:
                print(f"    - Batch #{batch['batch_no']}: {batch['mo_id']} ({batch['consumption']} kg)")
        
        print("\n" + "=" * 70)
        print("DEMO COMPLETED!")
        print("=" * 70)
        print(f"""
Summary:
  Initial count : {initial_count} batches
  After clear   : 0 batches
  After sync    : {final_count} batches (fetched from Odoo)

Next steps:
  1. PLC akan membaca batch dari table mo_batch
  2. PLC proses setiap batch (mixing, silo control, dll)
  3. Setelah semua batch selesai, panggil /api/admin/clear-mo-batch
  4. Scheduler (setiap 5 menit) akan detect table kosong
  5. Fetch batch berikutnya otomatis
  
To test auto-sync with scheduler:
  1. Keep table clear (already cleared in this demo)
  2. Wait 5 minutes (SYNC_INTERVAL_MINUTES)
  3. Check table again: should have new data
  4. Monitor logs: "✓ Auto-sync completed: X MO batches synced"
        """)


if __name__ == "__main__":
    print("\nMake sure uvicorn is running: python -m uvicorn app.main:app --reload\n")
    asyncio.run(demo_auto_sync_cycle())
