# ✅ Status Manufacturing Logic - CLARIFIED

## User Clarification (Feb 15, 2026)

> "status_manufacturing=true memang diambil dari logic database artinya kalaupun dari read data plc finished sementara di database belum, tetapi lakukan update dulu ke odoo dan database. Ketika database berubah, nanti ketika update di cycle selanjutnya sudah tidak akan dilakukan karena di sisi database sudah berubah true"

**Translation:**
> Status manufacturing comes from database logic. Even if PLC read data says finished but database is still not finished, do the update first to Odoo and database. When the database changes, then on the next update cycle it will not be done because the database side has already changed to true.

---

## Correct Logic (As Implemented)

### 1. **Source of Truth: DATABASE**
```python
# app/services/plc_sync_service.py _update_batch_if_changed()

# STEP 1: Check CURRENT database value BEFORE updates
current_status_mfg: bool = batch.status_manufacturing  # ← DB value NOW

if current_status_mfg:  # If DB already true
    logger.info("Skip update for MO...")
    return False  # ← BLOCK - batch being processed for completion

# STEP 2: If DB is false, proceed with ALL updates
changed = False

# Update consumption from PLC
for letter in "abcdefghijklm":
    attr = f"actual_consumption_silo_{letter}"
    setattr(batch, attr, plc_data["silos"][letter]["consumption"])
    changed = True

# STEP 3: Update status_manufacturing from PLC (if provided)
new_status_mfg = status_obj.get("manufacturing")
if new_status_mfg is not None:
    status_bool = bool(new_status_mfg)
    if batch.status_manufacturing != status_bool:
        batch.status_manufacturing = status_bool
        changed = True

# Return True if any changes
return changed
```

---

## Two-Cycle Flow

### **CYCLE 1: DB status_manufacturing = FALSE**

```
PLC Read (status_manufacturing=1 from CSV)
    ↓
_update_batch_if_changed() called
    ↓
Check DB: batch.status_manufacturing=False
    ↓ PASS (false, so allow)
    ↓
Update consumption: actual_consumption_silo_a = 825.25
Update status: batch.status_manufacturing = True
Save to DB
    ↓
sync_consumption_to_odoo() → Updates Odoo
    ↓
Odoo receives: consumption + equipment_failure data
```

**Result:**
- ✅ Consumption updated in DB
- ✅ Consumption sent to Odoo
- ✅ DB status_manufacturing now TRUE


### **CYCLE 2: DB status_manufacturing = TRUE**

```
PLC Read (status_manufacturing=1 again)
    ↓
_update_batch_if_changed() called
    ↓
Check DB: batch.status_manufacturing=True
    ↓ FAIL (true, so skip)
    ↓
Early return False - NO UPDATES
    ↓
sync_consumption_to_odoo() is NOT called (because changed=False)
```

**Result:**
- ✅ Batch protected from re-processing
- ✅ No interference with Odoo completion workflow
- ✅ No race conditions


---

## Why This Works

### **Protection Mechanism**
1. **First cycle:** DB is false → Allow updates
2. **Status transitions:** DB becomes true
3. **Second cycle:** DB is true → Auto-block

### **No Race Condition**
- Check happens on **every cycle** at the DB value level
- Each scheduler task sees the current DB state
- Once marked, **never unblocks** for that batch


### **Two Separate Processes**
```
Task 1 (Auto Sync - reads PLC):        Task 3 (Process Completed - Odoo):
  - Reads PLC data                        - Gets batches with status=true
  - Updates consumption if DB=false       - Marks MO done in Odoo
  - Can set status=true from PLC data     - Moves batch to history
  - Blocked if DB=true                    - Deletes from mo_batch
```

---

## Key Differences from Previous Misunderstanding

| Aspect | ❌ Wrong Approach | ✅ Correct Approach |
|--------|-----------------|-------------------|
| **Status Source** | PLC only (external) | DB logic (system) |
| **Check Timing** | After updates | **Before updates** |
| **PLC Data** | Ignored completely | Used if DB allows |
| **First Cycle** | Would block forever | Allows all updates |
| **Cycle 2+** | Would keep updating | Automatically blocked |
| **Protection** | Manual validation | Automatic via DB check |

---

## Scheduler Integration

### **Task 1: Auto Sync from PLC**
```python
async def auto_sync_plc_to_db_task():
    for batch in db.query(TableSmoBatch).all():
        plc_data = read_from_plc(batch.batch_no)
        
        # This checks DB status BEFORE update
        changed = plc_sync_service._update_batch_if_changed(
            db, batch, plc_data
        )
        
        if changed and consumption_updated:
            # Send to Odoo only if actually changed
            sync_consumption_to_odoo(batch)
```

### **Task 3: Process Completed Batches**
```python
async def process_completed_batches_task():
    # Get only batches where DB status = true
    completed = db.query(TableSmoBatch).filter(
        TableSmoBatch.status_manufacturing == True  # ← DB logic
    ).all()
    
    for batch in completed:
        # Already marked complete - process for history
        mark_mo_done(batch)
        move_to_history(batch)
```

---

## CSV Test Data

**app/reference/read_data_plc_input.csv**
```csv
35,status manufaturing,boolean,1,"0=start,1=finished",,D6066,1
```

- Simulates PLC finishing the batch (1=finished)
- In Cycle 1: DB is false → **allows update**
- DB becomes true
- In Cycle 2: DB is true → **blocks update** ✓


---

## Example Execution Timeline

```
Time  | Event                                    | DB status | Result
------|------------------------------------------|-----------|--------
00:00 | PLC reads consumption data (825.25)     | false     | 
      | DB check: false → ALLOW               |           |
      | Update DB: consumption=825.25          | false → true (if PLC says finished)
      | Cycle 1 complete                       |           | ✅ Consumption updated
------|------------------------------------------|-----------|--------
00:05 | PLC reads again (same 825.25)          | true      |
      | DB check: true → BLOCK                |           |
      | No updates, return False               |           | ✅ Protected
------|------------------------------------------|-----------|--------  
00:10 | Odoo marks MO done (async)             | true      |
      | Task 3: Get batches with status=true  |           |
      | Move to history                        |           | ✅ Cleanup
```

---

## Code Files Modified

### **1. app/services/plc_sync_service.py (Lines 250-345)**
- ✅ Check DB status BEFORE update (line 259)
- ✅ Allow status_manufacturing update from PLC if DB is false (line 330-343)
- ✅ Consumption updates allowed when DB=false (line 280-305)
- ✅ Auto-block when DB=true (early return False)

### **2. app/reference/read_data_plc_input.csv (Line 35)**
- ✅ status_manufacturing=1 (finished) simulates PLC marking batch complete

### **3. Test Scripts**
- `test_two_cycle_status_flow.py` - Demonstrates two-cycle behavior
- `test_consumption_flow_fixed.py` - Verifies consumption updates

---

## Summary

The system now correctly implements **database-driven status management**:

1. **DATABASE is the source of truth** for `status_manufacturing`
2. **Check happens BEFORE updates** - prevents stale data issues
3. **First cycle allows updates** - consumption and status can be set
4. **Subsequent cycles are blocked** - automatic protection from re-processing
5. **No race conditions** - each cycle sees current DB state
6. **PLC data flows naturally** - no artificial restrictions

This is the correct implementation of the user's clarification!
