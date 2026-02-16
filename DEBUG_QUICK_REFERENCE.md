# Debug Quick Reference - Odoo Sync Flow

## Task 3 Odoo Sync - Most Important Debug Points

### 🔍 Critical Debug Checkpoints (For Odoo Update Failures)

#### 1. Query Check
```
[TASK 3-DEBUG-2] Filter: status_manufacturing=1 AND update_odoo=False
[TASK 3-DEBUG-3] Query result count: <number>
```
❌ If count=0: No completed batches to process
✅ If count>0: Proceed to check payload

#### 2. Payload Check
```
[TASK 3-DEBUG-10] Complete batch payload: {...}
```
❌ If payload missing silo values: Check PLC read (Task 2)
✅ If payload has all required fields: Proceed to send

#### 3. Odoo Send Check
```
[TASK 3] ➜ Sending Odoo sync request for batch...
[TASK 3-DEBUG-13] Odoo response: {...}
```
❌ If "{'success': False, 'error': 'XXX'}": Odoo API error
✅ If "{'success': True, ...}": Proceed to flag update

#### 4. Flag Update Check
```
[TASK 3-DEBUG-15] Setting update_odoo=True for batch...
[TASK 3-DEBUG-16] Database commit successful
```
❌ If commit fails: Database connection issue
✅ If successful: Batch ready for archival

#### 5. Archive Check
```
[TASK 3-DEBUG-17] Moving batch to mo_histories...
[TASK 3-DEBUG-19] Deleting batch from mo_batch...
```
❌ If deletion fails: Orphaned batch in mo_batch
✅ If successful: Batch fully processed

---

## Common Odoo Sync Errors & Fixes

| Error | Debug Evidence | Solution |
|-------|--------|----------|
| No batches to process | [TASK 3-DEBUG-3] count=0 | Check PLC is completing batches (status=1) |
| Odoo connection timeout | [TASK 3-DEBUG-13] error=timeout | Check Odoo server, network connectivity |
| MO not found in Odoo | [TASK 3-DEBUG-13] error=not_found | Verify MO exists in Odoo with correct ID |
| Missing consumption data | [TASK 3-DEBUG-10] payload=empty | Check PLC read is working (Task 2) |
| update_odoo not set | [TASK 3-DEBUG-16] committed=false | Database transaction issue |
| Batch not deleted | [TASK 3-DEBUG-ERROR-1] or -2 | Check mo_histories table, cascade delete |

---

## One-Liner Command to Find Odoo Sync Issues

Monitor logs in real-time:
```bash
# On Linux/Mac
tail -f app.log | grep "\[TASK 3\]"

# On Windows PowerShell
Get-Content app.log -Wait | Select-String "\[TASK 3\]"
```

Filter only Odoo sync failures:
```bash
grep -E "\[TASK 3\].*FAILED" app.log
```

Filter complete successful syncs:
```bash
grep "\[TASK 3\].*✓✓✓ COMPLETE" app.log
```

---

## Debug Order for Troubleshooting

1. ✓ Check **[TASK 3-DEBUG-2]** Filter is correct
2. ✓ Check **[TASK 3-DEBUG-3]** Has batches to process
3. ✓ Check **[TASK 3-DEBUG-10]** Payload has consumption data
4. ✓ Check **[TASK 3-DEBUG-13]** Odoo response success=True
5. ✓ Check **[TASK 3-DEBUG-16]** Database commit success
6. ✓ Check **[TASK 3-DEBUG-20]** Batch deleted

---

## Expected Log Sequence (Happy Path)

```
[TASK 3] Found 1 completed batch(es) waiting for Odoo sync
[TASK 3] Processing batch #1 (MO: 123456)...
[TASK 3-DEBUG-10] Complete batch payload: {...}
[TASK 3] ➜ Sending Odoo sync request...
[TASK 3-DEBUG-13] Odoo response: {'success': True, ...}
[TASK 3] ✓ Odoo sync SUCCESS for batch #1
[TASK 3] ✓ Set update_odoo=True for batch #1
[TASK 3] ✓✓✓ COMPLETE: Batch #1 synced & archived
[TASK 3] Cycle complete: ✓ 1 archived, ⚠ 0 failed, total 1 batches
[TASK 3] ✓ All batches processed successfully!
```

---

## What To Do If Odoo Update Not Happening

### Step 1: Check Task 3 Run
```
Search logs for: "[TASK 3] Process completed batches task running"
```
- ❌ **NOT found**: Task scheduler not running, check APScheduler config
- ✅ **Found**: Continue to Step 2

###  Step 2: Check Batch Query
```
Search logs for: "[TASK 3-DEBUG-3] Query result count"
```
- ❌ **count=0**: No completed batches, check Task 2 is updating status_manufacturing=1
- ✅ **count>0**: Continue to Step 3

### Step 3: Check Odoo Response
```
Search logs for: "[TASK 3-DEBUG-13] Odoo response"
```
- ❌ **success: False**: Check Odoo error message and fix
- ✅ **success: True**: Continue to Step 4

### Step 4: Check update_odoo Flag
```
Search logs for: "[TASK 3] ✓ Set update_odoo=True"
```
- ❌ **NOT found**: Database commit failed, check DB logs
- ✅ **Found**: Odoo update is working!

---

## Configuration for Better Debugging

### In app/core/config.py
```python
# Add to get_settings()
LOG_LEVEL = env.str("LOG_LEVEL", default="DEBUG")  # Enable DEBUG
LOG_FORMAT = "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"

# Enable SQL logging to see database operations
SQLALCHEMY_ECHO = env.bool("SQLALCHEMY_ECHO", default=True)
```

### In .env
```env
LOG_LEVEL=DEBUG
SQLALCHEMY_ECHO=true
```

---

**Last Updated:** 2026-02-15
**For Questions:** Check DEBUG_COMPREHENSIVE_GUIDE.md
