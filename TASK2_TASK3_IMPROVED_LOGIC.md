# Task 2 & Task 3 - Improved Odoo Sync Logic

## Problem yang Diperbaiki

**Sebelumnya:**
- Task 2 dan Task 3 sync ke Odoo tanpa detail logging
- Jika Odoo API gagal, state batch tidak clear
- Error message tidak jelas sebab masalahnya apa
- Sulit tracking mana yang udah synced, mana yang belum

**Sekarang (Fixed):**
- Detailed logging untuk setiap step
- Clear distinction antara berbagai error types
- Batch state properly tracked (update_odoo flag)
- Queue status jelas (stuck batches clearly identified)

---

## Task 2 - PLC Read + Odoo Sync (ENHANCED)

### Flow

```
┌─────────────────────────────────────────────────────────┐
│ TASK 2: Read PLC + Sync to Odoo                        │
│ Interval: 5 menit (configurable)                        │
└─────────────────────────────────────────────────────────┘
     ↓
[1] Check: Ada active batches? (status_manufacturing=0)
     ├─ YES → continue
     └─ NO  → skip
     ↓
[2] Read PLC memory (single read per cycle)
     ├─ Get MO ID, consumption data, status flags
     ├─ Check if changed from last_read
     └─ If changed: update mo_batch table
     ↓
[3] IMMEDIATE: Sync updated consumption to Odoo
     ├─ Prepare batch_data with actual values
     ├─ Call: process_batch_consumption(mo_id, equipment_id, batch_data)
     ├─ If SUCCESS:
     │  ├─ Set: batch.update_odoo = True
     │  ├─ Commit DB
     │  └─ Log: ✓✓ Odoo sync SUCCESS
     └─ If FAILED:
        ├─ Log: ⚠ Odoo sync FAILED (with error reason)
        ├─ Do NOT set update_odoo flag
        └─ Batch remains in queue for retry
     ↓
[4] Return
```

### Key Improvements

**1. Sync Immediately (not wait for completion)**
- Consumption data sent to Odoo right after PLC update
- Not waiting for status_manufacturing=1
- Real-time consumption tracking

**2. Better Error Logging**
- Shows MO ID, equipment, silos, weight
- Shows error message if sync fails
- Shows clear action: "will retry next cycle"

**3. update_odoo Flag Logic**
- Set to TRUE only if Odoo API returns success
- If sync fails: flag remains FALSE (batch stays in queue)
- Task 3 will process only after flag=TRUE

---

## Task 3 - Process Completed + Archive (ENHANCED)

### Flow

```
┌─────────────────────────────────────────────────────────┐
│ TASK 3: Archive Completed Batches                      │
│ Interval: 3 menit (faster than Task 1)                 │
└─────────────────────────────────────────────────────────┘
     ↓
[1] Get all completed batches (status_manufacturing=1)
     ├─ Count: N batches
     └─ Continue if N > 0, else skip
     ↓
[2] For each completed batch:
     ├─ Check: update_odoo flag already true?
     │  ├─ YES → skip Odoo sync, direct to archive
     │  └─ NO  → proceed to step 3
     ├─
     │ [3] Sync to Odoo (if not already synced)
     │     ├─ Send: status=1, actual_weight, consumption
     │     ├─ If SUCCESS:
     │     │  └─ Mark update_odoo=True
     │     └─ If FAILED:
     │        ├─ Keep batch in mo_batch (safety!)
     │        ├─ Will retry next cycle
     │        └─ Log: ⚠ Odoo sync FAILED
     │
     └─ [4] If Odoo sync success: Archive
        ├─ Move to mo_histories table
        ├─ Delete from mo_batch
        ├─ Log: ✓✓✓ COMPLETE (batch removed from queue)
        └─ NOW TASK 1 CAN RUN AGAIN!
     ↓
[5] Summary Log
     └─ Show: X archived, Y failed, total Z
```

### Key Improvements

**1. Two-Path Processing**
- Path A (already synced): archive immediately
- Path B (not synced yet): sync first, then archive
- Handles both fresh completions and retries

**2. Safety-First Design**
- Batch only deleted if Odoo sync succeeds
- If Odoo API fails: batch stays in queue
- Prevents data loss from failed API calls

**3. Clear Status Tracking**
- update_odoo=TRUE means "ready for archival"
- update_odoo=FALSE means "waiting for Odoo sync"
- Task 3 won't delete unless synced

**4. Queue Clearance**
- Only successful completions clear the queue
- Failed syncs keep batch in queue
- Task 1 can't run if queue has stuck batches

---

## Complete End-to-End Flow

```
ODOO
  ↓ (Confirmed MO list)
  
TASK 1: Fetch MOs
├─ Check mo_batch empty?
├─ YES → Fetch from Odoo
├─ Save to mo_batch (status_manufacturing=0)
├─ WRITE to PLC memory (batch slots 1-N)
└─ Log: ✓ X batches synced
  ↓ (PLC now has batches to process)

PLC EXECUTION
  ├─ Reads batch data from memory slots
  ├─ Executes manufacturing process
  ├─ Updates consumption data in memory (READ area)
  ├─ When done: sets status_manufacturing=1
  └─ Results stay in PLC memory
  ↓ (every 5 minutes)

TASK 2: PLC Read + Odoo Sync
├─ Read PLC (single read)
├─ Update mo_batch with actual consumption
├─ IMMEDIATELY sync to Odoo (not waiting for completion!)
├─ If Odoo success: set update_odoo=TRUE
├─ If Odoo fails: retry next cycle
└─ Log: ✓ Odoo sync SUCCESS (or ⚠ FAILED)
  ↓ (every 3 minutes)

TASK 3: Archive Completed
├─ Find completed batches (status_manufacturing=1)
├─ If update_odoo=FALSE:
│  ├─ Sync to Odoo
│  └─ If success: set update_odoo=TRUE
├─ If update_odoo=TRUE:
│  ├─ Move to mo_histories
│  ├─ Delete from mo_batch
│  └─ Log: ✓✓✓ COMPLETE (queue cleared!)
└─ Else: Log ⚠ FAILED (stays in queue)
  ↓ (when mo_batch finally empty)

TASK 1 AGAIN: Fetch new MOs
└─ Check mo_batch empty? YES!
   ├─ Fetch NEW MOs from Odoo
   ├─ Save to mo_batch
   ├─ WRITE to PLC
   └─ Cycle repeats...

LOOP CONTINUES:
  Task 2 (every 5 min) ↔ Read PLC, Sync Odoo
  Task 3 (every 3 min) ↔ Archive, Clear Queue
  Task 1 (every 5 min) ↔ Fetch when queue empty
```

---

## Error Scenarios & Recovery

### Scenario 1: Odoo API Down (Network Error)

```
Task 2 → Call process_batch_consumption() → FAILED (timeout)
  ├─ Log: ⚠ Odoo sync FAILED: [Connection timeout]
  ├─ Don't set update_odoo=TRUE
  ├─ Batch stays in mo_batch
  └─ Next cycle (5 min later): Task 2 retries
     └─ If Odoo back up: succeeds and syncs
```

### Scenario 2: MO Not Found in Odoo

```
Task 3 → process_batch_consumption() → FAILED (MO not found 404)
  ├─ Log: ⚠ Odoo sync FAILED: Manufacturing Order not found
  ├─ Batch stays in mo_batch with status_manufacturing=1
  └─ Next cycle: Task 3 retries
     └─ If MO exists now: succeeds
     └─ If MO still missing: keeps failing (stuck batch)
```

### Scenario 3: Queue Stuck (No Archival)

```
mo_batch has completed batches but Task 3 can't archive:
  ├─ Queue can't be cleared
  ├─ Task 1 won't run (mo_batch not empty)
  ├─ No new MOs fetched from Odoo
  ├─ New MOs stay in Odoo (confirmed but not processed)
  └─ FIX: Manual retry via admin API
     - GET /api/admin/failed-to-push → show stuck batches
     - POST /api/admin/manual/retry-push-odoo/{mo_id}
```

---

## Key Points Summary

| Item | Before | After |
|------|--------|-------|
| Odoo Sync Timing | Wait for completion | Immediate (even if active) |
| Error Logging | Generic | Detailed (message, reason, action) |
| Queue State | Unclear | Clear (update_odoo flag tracked) |
| Stuck Batch Recovery | Manual | Auto-retry + manual endpoint |
| Data Safety | Risky (may delete if API fails) | Safe (only delete if synced) |

---

## Testing the Improved Logic

### Test Case 1: Normal Flow (Happy Path)

```bash
# 1. Fetch MO from Odoo via Task 1
# 2. Write to PLC via Task 1
# 3. Wait 5 min: Task 2 reads PLC, syncs to Odoo ✓
# 4. Wait 3 min: Task 3 archives ✓
# 5. Check: mo_batch empty, mo_histories has batch
Result: SUCCESS ✓
```

### Test Case 2: Odoo Timeout (Recoverable)

```bash
# 1. Simulate: Odoo API slow/down
# 2. Task 2 tries sync → FAILS (timeout)
# 3. Check logs: ⚠ Odoo sync FAILED
# 4. Check batch: update_odoo still FALSE, stays in mo_batch
# 5. Simulate: Odoo back up
# 6. Wait 5 min: Task 2 retries → SUCCESS ✓
# 7. Wait 3 min: Task 3 archives → SUCCESS ✓
Result: AUTO-RECOVERY WORKS ✓
```

### Test Case 3: MO Not in Odoo (Stuck Batch)

```bash
# 1. Create test batch with fictitious MO
# 2. Mark status_manufacturing=1
# 3. Run Task 3 → tries sync → FAILS (MO not found)
# 4. Check logs: ⚠ Odoo sync FAILED
# 5. Check batch: still in mo_batch
# 6. Use admin endpoint: GET /api/admin/failed-to-push
#    → shows stuck batch with reason
Result: STUCK BATCH VISIBLE & TRACEABLE ✓
```

---

## Next Steps

1. ✓ Task 2 logging improved
2. ✓ Task 3 logic enhanced  
3. ⏳ Test with real Odoo data (not test MO)
4. ⏳ Verify auto-retry mechanism
5. ⏳ Test manual recovery endpoints

