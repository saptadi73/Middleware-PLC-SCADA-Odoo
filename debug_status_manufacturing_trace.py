"""
Debug: Trace when status_manufacturing is set to True
Check if it's set BEFORE or AFTER consumption is sent to Odoo
"""
from sqlalchemy import select, create_engine, event
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch

settings = get_settings()

print("\n" + "="*80)
print("DEBUG: When is status_manufacturing set to True?")
print("="*80)

# Check current state
db = SessionLocal()

# Query all mo_batch records
result = db.execute(select(TableSmoBatch).order_by(TableSmoBatch.created_at.desc()))
batches = result.scalars().all()

print(f"\nTotal records in mo_batch: {len(batches)}\n")

print("Batch Status Survey:")
print("No | batch_no | mo_id | status_mfg | created_at | updated_at | in_history")
print("-"*80)

for i, batch in enumerate(batches[:10], 1):
    status_mfg = "✓" if batch.status_manufacturing else "✗"
    created = batch.created_at.strftime("%Y-%m-%d %H:%M:%S") if batch.created_at else "?"
    updated = batch.updated_at.strftime("%Y-%m-%d %H:%M:%S") if batch.updated_at else "?"
    
    # Check if in history
    in_history = "YES" if batch.batch_no.startswith("H-") or batch.mo_id.count("-") > 3 else "NO"
    
    print(f"{i:2} | {str(batch.batch_no):8} | {str(batch.mo_id):12} | {status_mfg:^10} | {created} | {updated} | {in_history}")

db.close()

# Now check for specific MO
print(f"\n\nDetailed check for MO_ID: WH/MO/00001")
print("-"*80)

db2 = SessionLocal()
result2 = db2.execute(
    select(TableSmoBatch).where(TableSmoBatch.mo_id == "WH/MO/00001")
)
batch = result2.scalar_one_or_none()

if batch:
    print(f"\n✓ Found batch: {batch.batch_no}")
    print(f"  MO_ID: {batch.mo_id}")
    print(f"  Status Manufacturing: {batch.status_manufacturing}")
    print(f"  Status Operation: {batch.status_operation}")
    print(f"\n  Timestamps:")
    print(f"    Created: {batch.created_at}")
    print(f"    Updated: {batch.updated_at}")
    print(f"    Last read from PLC: {batch.last_read_from_plc}")
    
    print(f"\n  Key question:")
    print(f"    - When did status_manufacturing become True?")
    print(f"    - Was it before or after consumption values were ready?")
    print(f"    - Check mo_histories table to see if batch was moved there")
    
    # Check consumption values
    print(f"\n  Consumption values:")
    has_consumption = False
    for letter in "abcdefghijklm":
        attr = f"actual_consumption_silo_{letter}"
        if hasattr(batch, attr):
            value = getattr(batch, attr)
            if value and value > 0:
                print(f"    Silo {letter.upper()}: {value}")
                has_consumption = True
    
    if not has_consumption:
        print(f"    (No consumption values found)")
else:
    print(f"\n✗ MO WH/MO/00001 not found")

db2.close()

print("\n" + "="*80)
print("Analysis:")
print("  1. If status_manufacturing=True AND batch STILL in mo_batch table:")
print("     → Batch marked completed but not yet removed from mo_batch")
print("     → Consumption update will be SKIPPED")
print("\n  2. If status_manufacturing=True AND batch MOVED to mo_histories:")
print("     → Batch is archived, no more updates possible")
print("\n  3. If status_manufacturing=False:")
print("     → Batch still active, consumption can be updated")
print("="*80 + "\n")
