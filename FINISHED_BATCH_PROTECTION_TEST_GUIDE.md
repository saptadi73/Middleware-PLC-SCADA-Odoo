# 🧪 How to Verify: Finished Batch Protection Test Guide

## Quick Test: Mark Batch as Finished, Then Try to Update

### Test 1: PLC Update After Finished ✅

**Objective:** Verify PLC cannot update a batch marked as finished

**Steps:**

1. **Mark batch as finished:**
```bash
python -c "
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch

db = SessionLocal()
batch = db.query(TableSmoBatch).filter(TableSmoBatch.mo_id == 'WH/MO/00001').first()
if batch:
    batch.status_manufacturing = True
    db.commit()
    print(f'✓ Batch {batch.mo_id} marked as finished')
    print(f'  status_manufacturing = {batch.status_manufacturing}')
db.close()
"
```

2. **Try to read from PLC and update batch:**
```bash
curl -X POST http://localhost:8000/api/v1/plc/sync-from-plc
```

**Expected Result:**
```json
{
  "status": "success",
  "message": "No changes detected, skip update",
  "data": {
    "mo_id": "WH/MO/00001",
    "updated": false
  }
}
```

**Logs Should Show:**
```
Skip update for MO WH/MO/00001: status_manufacturing already completed (1)
```

---

### Test 2: Odoo Consumption Update After Finished ✅

**Objective:** Verify Odoo consumption cannot update a batch marked as finished

**Steps:**

1. **Ensure batch is marked as finished (from Test 1)**

2. **Send consumption update via API:**
```bash
python -c "
import asyncio
import httpx
import json

async def test():
    # Simulating consumption update
    consumption_data = {
        'silo101': 900.0,  # Different from before
        'silo102': 400.0
    }
    
    # Call the consumption update
    from app.services.odoo_consumption_service import get_consumption_service
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    service = get_consumption_service(db)
    
    result = await service.update_consumption_with_odoo_codes(
        mo_id='WH/MO/00001',
        consumption_data=consumption_data
    )
    
    print('API Result:')
    print(json.dumps(result, indent=2))
    db.close()

asyncio.run(test())
"
```

**Expected Result:**
- Odoo side: Update succeeds ✓
- Database side: Consumption NOT saved due to protection ✓

**Logs Should Show:**
```
Skip consumption update for MO WH/MO/00001: status_manufacturing already completed (1)
```

---

### Test 3: Scheduler Task 2 Skip ✅

**Objective:** Verify scheduler doesn't process finished batches

**Steps:**

1. **Check scheduler log during a run:**
```bash
# Watch logs
tail -f logs/app.log | grep "TASK 2"
```

2. **Observe behavior:**
   - When `status_manufacturing=0` (in progress): Task processes the batch
   - When `status_manufacturing=1` (finished): Task skips it

**Expected Logs:**
```
[TASK 2] Found 0 active batch(es) in queue
```
(All batches are finished, so none are processed)

---

## 📊 Database Verification

### Query to Verify Finished Batch Data Integrity

```sql
-- Show all finished batches with their final consumption
SELECT 
    batch_no,
    mo_id,
    status_manufacturing,
    actual_consumption_silo_a,
    actual_consumption_silo_b,
    actual_consumption_silo_c,
    actual_weight_quantity_finished_goods,
    last_read_from_plc
FROM mo_batch
WHERE status_manufacturing = true
ORDER BY batch_no DESC
LIMIT 5;
```

**Expected:** All finished batches show UNCHANGED consumption values (they shouldn't change)

---

## 🔍 Log Pattern Recognition

### When Protection Is Active (Good!)
```
Skip update for MO WH/MO/00001: status_manufacturing already completed (1)
```
→ Protection triggered ✓

### When Update Is Applied (Normal - In Progress Batch)
```
Updated actual_consumption_silo_a: 825.0 → 830.0
```
→ Batch is still in progress ✓

---

## 🚨 Scenarios Where Database Should Change

Protection should ONLY block updates, not prevent legitimate changes:

### ✅ DO Allow (In Progress Batch):
```
- Read from PLC and update actuall_consumption_* fields
- Receive consumption from Odoo and sync to DB
- Update weight_finished_goods
- Update timestamps
```

### ❌ DON'T Allow (Finished Batch):
```
- PLC reading tries to change finished batch data
- Odoo consumption arrives and tries to update finished batch
- Any new data tries to overwrite completed manufacturing
```

---

## 📈 Success Criteria

Your middleware passes the finalized batch protection test when:

- [ ] ✅ Finished batch receives PLC update → Database unchanged
- [ ] ✅ Finished batch receives Odoo consumption → Database unchanged  
- [ ] ✅ Logs show "status_manufacturing already completed (1)" message
- [ ] ✅ Scheduler Task 2 doesn't process finished batches
- [ ] ✅ In-progress batches still receive normal updates
- [ ] ✅ All 3 protection layers working independently

---

## 🔗 Protection Code References

**See:**
- [app/services/plc_sync_service.py#L257-L263](../app/services/plc_sync_service.py#L257-L263) - PLC protection
- [app/services/odoo_consumption_service.py#L370-L378](../app/services/odoo_consumption_service.py#L370-L378) - Consumption protection
- [app/core/scheduler.py#L92-L99](../app/core/scheduler.py#L92-L99) - Scheduler filtering

---

## 💡 Notes

- Protection is **proactive** (blocks at source) not reactive (cleanup after)
- Once `status_manufacturing=1`, NO rollback needed (nothing changed)
- Finished batches are moved to `mo_histories` for archival (read-only)
- This design ensures data integrity and audit compliance ✓
