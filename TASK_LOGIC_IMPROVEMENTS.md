# Task Logic Improvements - Summary

## Problem Yang Diperbaiki

Previous test (`test_task3_live.py`) gagal karena:
1. **Task 3 tidak update ke Odoo** → batch tidak bisa di-archive
2. **Batch stuck di mo_batch** (dengan status_manufacturing=1, update_odoo=true)
3. **Queue tidak bisa cleared** → Task 1 tidak bisa fetch MO baru
4. **Odoo API error tidak jelas** → sulit debug masalahnya apa

Error yang muncul:
```
Manufacturing Order "TEST/MO/99999" not found
```

Root Cause: Test MO tidak ada di Odoo, tapi logic tidak handle edge case ini dengan baik.

---

## Perbaikan Yang Dilakukan

### 1. ✓ Task 2 - Enhanced Odoo Sync Logging

**File:** `app/core/scheduler.py` (lines 160-230)

**Improvements:**
- Detailed logging untuk setiap step
- Show MO ID, equipment, silos, weight
- Clear error messages
- Better state tracking

**Before:**
```python
logger.warning(f"Failed to sync consumption to Odoo for MO {mo_id}")
```

**After:**
```python
logger.info(f"[TASK 2] ✓✓ Odoo sync SUCCESS: MO {mo_id} | status={status} | weight={weight} | silos={count}")
# or
logger.warning(f"[TASK 2] ⚠ Odoo sync FAILED for MO {mo_id}: {error_msg} | Will retry next cycle")
```

### 2. ✓ Task 3 - Two-Path Processing (NEW)

**File:** `app/core/scheduler.py` (lines 243-370)

**New Logic:**
- Path A: Batch sudah update_odoo=TRUE → direct archive
- Path B: Batch belum synced → sync first, then archive
- Proper retry mechanism

**Benefits:**
- Fresh completions: immediate Odoo sync + archive
- Retries: skip redundant API calls, go direct to archive
- Handles both new and stuck batches

**Code Structure:**
```python
# Check if already synced
if update_odoo_flag:
    # Direct archive (skip Odoo call)
    move_to_history() → delete_from_batch()
    
else:
    # Send to Odoo first
    process_batch_consumption() → 
    if success: set update_odoo=TRUE
    if failed: keep in queue, log warning
    
    # Only archive if sync succeeded
    if update_odoo now TRUE:
        move_to_history() → delete_from_batch()
```

### 3. ✓ Better Error Messages

**Task 2 errors:**
- `✓✓ Odoo sync SUCCESS` - with all details
- `⚠ Odoo sync FAILED` - with error reason and action (will retry)

**Task 3 errors:**
- `✓✓✓ COMPLETE` - batch archived and removed from queue
- `⚠ Odoo sync FAILED` - batch stays in queue for retry
- `✗ Exception processing` - with traceback

### 4. ✓ Proper State Tracking

**update_odoo flag semantics:**
- `False`: Not yet synced to Odoo (Task 2 will sync)
- `True`: Already synced to Odoo (Task 3 can archive)

**Task 2 sets flag:**
- Set to `TRUE` only if `process_batch_consumption()` returns success
- If sync fails: flag remains `FALSE` (batch stays in queue)
- Next cycle Task 2 tries again

**Task 3 checks flag:**
- If `TRUE`: Already synced, skip Odoo call, direct archive
- If `FALSE`: Call Odoo, wait for result
  - If success: set flag=TRUE, then archive
  - If failed: log warning, keep in queue

---

## Expected Behavior (Fixed)

### Success Case (Real MO)
```
TASK 2 (cycle 1):
  - Read PLC → consumption updated
  - Sync to Odoo → SUCCESS
  - Set update_odoo=TRUE
  - Log: ✓✓ Odoo sync SUCCESS
  
TASK 3 (cycle next):
  - Found completed batch with update_odoo=TRUE
  - Archive → move to mo_histories, delete from mo_batch
  - Log: ✓✓✓ COMPLETE: Batch archived
  
TASK 1 (cycle next):
  - Check mo_batch empty → YES!
  - Fetch new MOs from Odoo
  - Write to PLC
  → QUEUE CLEARED, CYCLE CONTINUES
```

### Failure Case (MO Not in Odoo)
```
TASK 3 (cycle 1):
  - Found completed batch with update_odoo=FALSE
  - Try sync to Odoo → FAILED (MO not found)
  - Don't set update_odoo flag
  - Log: ⚠ Odoo sync FAILED (Manufacturing Order not found)
  - Batch STAYS in mo_batch
  
TASK 3 (cycle next):
  - Same batch still there, retry
  - Still fails (MO still not in Odoo)
  - Stays in queue
  
TASK 1:
  - mo_batch still not empty
  - Can't fetch new MOs (waits for queue to clear)
  
FIX (manual):
  - Admin: GET /api/admin/failed-to-push
  - Shows: stuck batch, reason, timestamp
  - Can manually retry or delete
```

---

## File Changes Summary

| File | Change | Lines |
|------|--------|-------|
| `app/core/scheduler.py` | Task 2: Better error logging | 160-230 |
| | Task 3: Two-path logic | 243-370 |
| `TASK2_TASK3_IMPROVED_LOGIC.md` | New documentation | Created |

---

## Testing Improvements

### What Was Tested Before
- Only with test MO (TEST/MO/99999) that doesn't exist in Odoo
- Failure case, not success case

### What Should Be Tested Now
1. **Success case:** Use real MO from Odoo
2. **Failure case:** Keep test MO to verify stuck batch handling
3. **Retry case:** Recover from temporary Odoo failure
4. **Manual recovery:** Use admin endpoints to clear stuck batches

### Test Commands

```bash
# Check queue status
curl http://localhost:8000/api/admin/batch-status

# See failed batches
curl http://localhost:8000/api/admin/failed-to-push

# Manual retry
curl -X POST http://localhost:8000/api/admin/manual/retry-push-odoo/{mo_id}

# Clear batch (manual cleanup)
curl -X POST http://localhost:8000/api/admin/manual/reset-batch/{mo_id}
```

---

## Key Design Principles (Implemented)

### 1. Safety First
- Batch only deleted from queue if Odoo sync succeeds
- If API fails: batch stays in queue for retry
- Prevents data loss from failed API calls

### 2. Real-Time Sync (Task 2)
- Consumption sent to Odoo immediately after PLC update
- Don't wait for completion (status_manufacturing=1)
- Provides up-to-date consumption tracking to Odoo

### 3. Queue Management (Task 3)
- Only cleared when tasks succeed
- Stuck batches remain visible (not hidden)
- Auto-retry mechanism (retry every 3 minutes)
- Manual recovery endpoints available

### 4. Clear Error Messages
- Every failure logs reason + action
- Operators understand what went wrong
- Easy to debug issues

---

## Deployment Notes

- ✓ Logic improved and documented
- ✓ Type hints fixed (Pylance warnings resolved)
- ✓ Ready for testing with real data
- ✓ Demo/test credentials should use real Odoo MOs (not test data)

## Next Steps

1. Run with real Odoo MO data to verify success case
2. Test auto-retry mechanism with temporary failure
3. Verify manual recovery endpoints work
4. Monitor logs for any remaining issues

