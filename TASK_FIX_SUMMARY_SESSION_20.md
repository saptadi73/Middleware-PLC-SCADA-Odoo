# Task Logic Fix Summary - Session 20

## Overview
Fixed critical logic issues in Tasks 2 & 3 of scheduler to properly separate concerns and ensure correct flow of data between PLC, database, and Odoo.

---

## Changes Made

### Task 1: auto_sync_mo_task() ✓ VERIFIED CORRECT
**Status:** No changes needed - already correct

**Purpose:** Fetch MOs from Odoo and write to PLC  
**Flow:**
1. Check mo_batch is empty
2. Fetch from Odoo
3. Sync to mo_batch database
4. **WRITE to PLC memory** (PLC executes batches)

**Key:** Only runs when mo_batch is empty (queue available)

---

### Task 2: plc_read_sync_task() ✓ FIXED THIS SESSION
**Status:** CORRECTED - Removed all Odoo sync code

**Purpose:** Read PLC data and update database ONLY  
**Flow:**
1. Check active batches exist (status_manufacturing=0)
2. READ PLC once per cycle
3. UPDATE mo_batch with consumption data
4. **NO Odoo sync** ← THIS WAS THE PROBLEM

**Changes Made:**
- ✓ Removed all `consumption_service.process_batch_consumption()` calls
- ✓ Removed batch.update_odoo flag assignments
- ✓ Removed detailed Odoo sync logging
- ✓ Simplified to database-only operations

**Why?** Clean separation: Task 2 reads and stores, Task 3 handles Odoo sync

---

### Task 3: process_completed_batches_task() ✓ FIXED THIS SESSION
**Status:** CORRECTED - Changed query filter and simplified logic

**Purpose:** Archive completed batches and sync to Odoo  

**Old Logic (INCORRECT):**
```python
# Get ALL completed batches, then branch based on update_odoo flag
completed_batches = history_service.get_completed_batches()  # no filter

for batch in completed_batches:
    if update_odoo_flag:  # If already synced
        # just archive
    else:  # If not synced
        # sync to Odoo
```

**New Logic (CORRECT):**
```python
# Get ONLY completed batches not yet synced
stmt = select(TableSmoBatch).where(
    and_(
        TableSmoBatch.status_manufacturing.is_(True),     # ← Completed by PLC
        TableSmoBatch.update_odoo.is_(False)              # ← Not yet synced to Odoo
    )
)
completed_batches = db.execute(stmt).scalars().all()

for batch in completed_batches:
    # Sync to Odoo
    if result.get("success"):
        batch.update_odoo = True        # ← Mark as synced
        archive_and_delete()
    else:
        # Keep in queue with update_odoo=False for retry
```

**Changes Made:**
- ✓ Added proper WHERE clause: `status_manufacturing=1 AND update_odoo=False`
- ✓ Removed branching for update_odoo=True (batches with flag=True are not queried)
- ✓ Simplified loop to process only pending Odoo syncs
- ✓ Added update_odoo=True assignment AFTER successful Odoo sync
- ✓ Updated docstring to reflect new logic

**Why?** Prevents processing already-synced batches and clearly separates concern to Task 3

---

## Key Concept: update_odoo Flag

**Type:** Boolean (True/False), NOT integer

**Semantics:**
- `update_odoo=False` → Batch completed by PLC, waiting for Odoo sync (Task 3 processes THIS)
- `update_odoo=True` → Batch successfully synced to Odoo, can be archived (Task 3 skips THIS)

**Set By:** Task 3 ONLY, AFTER successful Odoo sync

**Safety Mechanism:**
- Failed Odoo sync keeps batch in queue with flag=False
- Next Task 3 cycle will retry
- Prevents duplicate Odoo syncs (flag prevents reprocessing)

---

## Expected Behavior Flow

### Happy Path
```
Task 1: Fetch MO → Write PLC → mo_batch has data (update_odoo=False)
   ↓
Task 2: Read PLC → Update mo_batch with consumption
   ↓
PLC executes batch → Sets status_manufacturing=1
   ↓
Task 3: Query (status=1 AND update_odoo=False) → Sync Odoo
   ↓
If Odoo success: Set update_odoo=True → Archive → Delete from queue
   ↓
Queue empty → Task 1 can fetch next MO
```

### Error Recovery
```
Task 3: Sync Odoo → FAIL
   ↓
keep batch in queue with:
  - status_manufacturing=1 (PLC completed)
  - update_odoo=False (still needs Odoo sync)
   ↓
Next Task 3 cycle → Query same batch again (status=1 AND update_odoo=False)
   ↓
Retry Odoo sync (automatic retry)
```

---

## Code Quality Improvements

### Task 2
- Simplified from ~130 lines to ~65 lines
- Removed branching logic
- Clear, single responsibility: READ PLC → UPDATE DB
- Better logging for debugging

### Task 3
- Simplified from ~150 lines to ~95 lines
- Removed unnecessary branching for update_odoo=True
- Query filter prevents processing already-synced batches
- Clearer error handling and retry logic
- Added to docstring explaining filter condition

---

## Testing

### Test Script Location
`test_task2_task3_with_real_data.py` (created in previous session)

### Manual Verification Steps
1. Create test MO in Odoo OR use internal test MO
2. Run Task 1 manually → verify mo_batch populated
3. Run Task 2 manually → verify mo_batch updated with PLC data
4. Simulate PLC completion → set status_manufacturing=1
5. Run Task 3 manually → verify Odoo sync and batch deletion

### Expected Logs
```
[TASK 2] ✓ Updated mo_batch for MO: TEST/MO/001 from PLC data
[TASK 3] Found 1 completed batch(es) waiting for Odoo sync
[TASK 3] ✓ Odoo sync successful for batch #1
[TASK 3] ✓ Set update_odoo=True for batch #1
[TASK 3] ✓✓✓ COMPLETE: Batch #1 (MO: TEST/MO/001) synced & archived
```

---

## Files Modified

1. **app/core/scheduler.py**
   - Lines 107-168: Task 2 simplified
   - Lines 169-260+: Task 3 logic updated with new query filter

---

## Validation Status

- ✓ No new syntax errors introduced
- ✓ Task 1: Correct (verified)
- ✓ Task 2: Corrected and clean
- ✓ Task 3: Corrected with proper filtering
- ⏳ End-to-end testing: Pending with real Odoo data

---

## Next Steps

1. Run `test_task2_task3_with_real_data.py` with real Odoo MO data
2. Monitor logs for errors
3. If successful, deploy to production
4. Monitor Task 3 retry mechanism for failed Odoo syncs

---

**Session Date:** Latest  
**Changes Made By:** GitHub Copilot  
**Status:** Ready for testing
