"""
Test: Verify consumption updates work even after batch completion
"""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_sync_service import PLCSyncService

settings = get_settings()

print("\n" + "="*80)
print("TEST: Consumption Updates After Batch Completed")
print("="*80)

try:
    service = PLCSyncService()
    
    # Ambil data dari DB
    db = SessionLocal()
    result = db.execute(
        select(TableSmoBatch).where(TableSmoBatch.mo_id == "WH/MO/00001")
    )
    batch = result.scalar_one_or_none()
    db.close()
    
    if not batch:
        print("\n✗ MO WH/MO/00001 not found in database")
    else:
        print(f"\n✓ Found batch: {batch.batch_no}")
        print(f"  Status Manufacturing: {batch.status_manufacturing}")
        print(f"  Current Consumption Silo A: {getattr(batch, 'actual_consumption_silo_a', 0)}")
        
        # Simulate PLC data dengan consumption values BERBEDA dari saat ini
        plc_data = {
            "mo_id": "WH/MO/00001",
            "product_name": "JF Plus",
            "quantity": 2500,
            "status": {
                "manufacturing": True,  # Sudah completed
                "operation": False,
            },
            "weight_finished_good": 2000,
            "silos": {
                "a": {"consumption": 900.00},  # Updated dari 825.25 → 900.00
                "b": {"consumption": 400.00},  # Updated dari 375.15 → 400.00
                "c": {"consumption": 250.00},
                "d": {"consumption": 50.0},
                "e": {"consumption": 381.25},
                "f": {"consumption": 250.0},
                "g": {"consumption": 62.5},
                "h": {"consumption": 83.5},
                "i": {"consumption": 83.25},
                "j": {"consumption": 83.25},
                "k": {"consumption": 3.75},
                "l": {"consumption": 0.25},
                "m": {"consumption": 42.0},
            }
        }
        
        print(f"\n  Simulated new PLC data:")
        print(f"    SILO A: 900.00 (was {getattr(batch, 'actual_consumption_silo_a', 0)})")
        print(f"    SILO B: 400.00 (was {getattr(batch, 'actual_consumption_silo_b', 0)})")
        
        # Test update
        print(f"\n  Testing _update_batch_if_changed()...")
        db2 = SessionLocal()
        result2 = db2.execute(
            select(TableSmoBatch).where(TableSmoBatch.mo_id == "WH/MO/00001")
        )
        batch2 = result2.scalar_one_or_none()
        
        # Call the function
        changed = service._update_batch_if_changed(db2, batch2, plc_data)
        
        print(f"\n  Result: changed={changed}")
        
        if changed:
            print(f"  ✓ Consumption values WERE updated despite completion status!")
            print(f"    New SILO A: {getattr(batch2, 'actual_consumption_silo_a', 0)}")
            print(f"    New SILO B: {getattr(batch2, 'actual_consumption_silo_b', 0)}")
        else:
            print(f"  ✗ Consumption values were NOT updated")
        
        db2.close()
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("Test Complete")
print("="*80 + "\n")
