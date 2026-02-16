# TASK 1 Updated - With PLC WRITE Implementation

## ✓ CONFIRMED: Task 1 Harus WRITE ke PLC

**Alasan:**
- MO dari Odoo adalah "instruksi batch" yang PLC harus execute
- PLC membaca batch data dari memory (tidak dari network)
- Setelah PLC selesai execute batch, PLC menulis hasil di memory
- Task 2 akan membaca hasil tersebut

## Task 1 Flow (UPDATED)

```
┌─────────────────────────────────────────┐
│ TASK 1: Auto-Sync MO + Write to PLC     │
└─────────────────────────────────────────┘
         ↓
    1. Check Queue
       └→ if NOT empty: skip (tunggu PLC selesai batch saat ini)
       └→ if empty: continue
         ↓
    2. Fetch MO dari Odoo
       └→ GET /api/mo (MO yang status=open/ready)
         ↓
    3. Sync ke Database (mo_batch)
       └→ INSERT INTO mo_batch (mo_id, consumption, equipment, etc)
         ↓
    4. WRITE ke PLC Memory ✓ [NEW]
       └→ FINS Protocol → Write batch data ke PLC address
       └→ Batch 1 → Slot 1
       └→ Batch 2 → Slot 2
       └→ ... up to Slot 30
         ↓
    5. Log & Return
```

## Implementation Details

**File Modified:**
- `app/core/scheduler.py` (lines 40-101)

**Changes:**
1. Added step: `write_mo_batch_queue_to_plc(db, start_slot=1, limit=len(mo_list))`
2. This calls `plc_write_service.write_mo_batch_to_plc()` internally
3. Each batch written to PLC slot 1-30

**Code:**
```python
# 4. WRITE batch data ke PLC memory
from app.services.mo_batch_service import write_mo_batch_queue_to_plc

written = write_mo_batch_queue_to_plc(db, start_slot=1, limit=len(mo_list))
logger.info(f"[TASK 1] ✓ PLC write completed: {written} batches written to PLC")
```

## PLC Memory Map (Batch Data per Slot)

Each batch slot (1-30) contains:
- MO ID (string)
- Equipment ID
- Finished Goods Name
- Component/Silo Information (A-M)
- Consumption data per silo
- Status flags

**Service Used:** `app.services.plc_write_service.PLCWriteService`

## Complete Task Cycle

```
ODOO                              Task 1 (UPDATED)
  ↓ (MO List)                         ↓
Fetch MOs          →          Save to mo_batch
                               WRITE to PLC ←── [PLC will execute]
                                   ↓
                              Task 2 →→→ READ PLC results
                                        → Sync consumption to Odoo
                                        → Save actual_weight, status
                                   ↓
                              Task 3 →→→ Process completed batches
                                        → Archive to mo_histories
                                        → Clear queue
                                   ↓
                         (back to Task 1 when queue empty)
```

## Testing

**Run:**
```bash
python test_task1_with_plc_write.py
```

**Expected Output:**
1. ✓ Cleared old batches
2. ✓ Task 1 fetched N batches from Odoo
3. ✓ Saved to mo_batch
4. ✓ Wrote to PLC (check PLC logs for write confirmation)

## Safety Notes

1. **One batch at a time:** PLC only executes one batch, queue must be clear before Task 1 fetches new
2. **Atomic operation:** Write to DB first, then write to PLC (if DB fails, PLC write doesn't happen)
3. **Error handling:** If PLC write fails, batch stays in mo_batch, Task 1 will retry next cycle
4. **Max 30 batches:** PLC memory has 30 slots, limit enforced in `write_mo_batch_queue_to_plc()`

## Verification

Check PLC write success by:
1. Monitor Task 1 logs: `[TASK 1] ✓ PLC write completed: X batches`
2. Check PLC memory addresses (via PLC monitoring tool)
3. Wait for Task 2 to read and report results

## Status

✓ Implementation complete
✓ Test script created
⏳ Ready for testing
