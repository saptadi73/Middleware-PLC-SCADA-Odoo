#!/usr/bin/env python3
"""
Test untuk verifikasi bahwa quantity (actual_weight_finished_good) dikirimkan
ke endpoint /api/scada/mo/update-with-consumptions
"""
import asyncio
import logging
from app.services.odoo_consumption_service import OdooConsumptionService

# Setup logging untuk melihat debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)

async def test_quantity_payload():
    """Test payload dikirimkan dengan quantity"""
    service = OdooConsumptionService()
    
    # Simulasi batch_data dari Task 3
    batch_data = {
        "status_manufacturing": 1,
        "actual_weight_quantity_finished_goods": 2500.75,  # ← QUANTITY yang harus dikirim
        "consumption_silo_a": 825.00,
        "consumption_silo_b": 600.00,
        "consumption_silo_c": 375.15,
    }
    
    print("\n" + "="*80)
    print("TEST: Quantity Payload Verification")
    print("="*80)
    print(f"\n✓ Input batch_data:")
    print(f"  - actual_weight_quantity_finished_goods: {batch_data['actual_weight_quantity_finished_goods']}")
    print(f"  - consumption_silo_a: {batch_data['consumption_silo_a']}")
    print(f"  - consumption_silo_b: {batch_data['consumption_silo_b']}")
    print(f"  - consumption_silo_c: {batch_data['consumption_silo_c']}")
    
    print(f"\n✓ Calling process_batch_consumption()...")
    
    result = await service.process_batch_consumption(
        mo_id="WH/MO/00001",
        equipment_id="PLC01",
        batch_data=batch_data
    )
    
    print(f"\n✓ Result: {result}")
    
    if result.get("success"):
        print("\n✅ SUCCESS: Payload dikirim dengan benar!")
        print("   Cek log di atas untuk melihat 'Complete payload to /update-with-consumptions'")
        print("   Pastikan payload termasuk: 'quantity': 2500.75")
    else:
        print(f"\n⚠️  Response indicates potential issue: {result}")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_quantity_payload())
