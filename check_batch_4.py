from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch

session = SessionLocal()
try:
    batch = session.query(TableSmoBatch).filter_by(batch_no=4).first()
    if batch:
        print(f"Batch #{batch.batch_no}:")
        print(f"  mo_id: {batch.mo_id}")
        print(f"  status_operation: {batch.status_operation}")
        print(f"  status_manufacturing: {batch.status_manufacturing}")
        print(f"  odoo_cancelled: {getattr(batch, 'odoo_cancelled', 'N/A')}")
        print(f"  update_odoo: {batch.update_odoo}")
    else:
        print("Batch #4 not found")
finally:
    session.close()
