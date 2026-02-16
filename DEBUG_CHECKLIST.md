# 🔧 PRACTICAL DEBUG CHECKLIST - Odoo Update Troubleshooting

## Quick Diagnosis Flowchart

```
Is Odoo update NOT happening?
│
├─→ YES: START HERE
│        └─ Go to "Diagnosis Checklist" below
│
└─→ NO: Good! Check logs with "Verify Success" section
```

---

## 🩺 DIAGNOSIS CHECKLIST (When Odoo Update NOT Happening)

### ✅ STEP 1: Is Task 3 Running?

**Command:**
```bash
grep "[TASK 3] Process completed batches task running" app.log
```

**If NOT found:**
- ❌ Task scheduler not started
- **Fix:** 
  ```bash
  # Check if FastAPI app is running
  curl http://localhost:8000/health
  
  # Check scheduler logs
  grep "scheduler" app.log | head -10
  ```

**If found (with timestamp):**
- ✅ Task 3 is running
- →  **Go to STEP 2**

---

### ✅ STEP 2: Are There Completed Batches?

**Command:**
```bash
grep "[TASK 3-DEBUG-3] Query result count:" app.log | tail -1
```

**Expected Output:**
```
[TASK 3-DEBUG-3] Query result count: 1
```

**If count = 0:**
- ❌ No completed batches to process
- **Reason:** PLC hasn't marked batch as complete
- **Fix:** 
  ```bash
  # Check Task 2 is updating status_manufacturing
  grep "[TASK 2] ✓ Updated mo_batch" app.log
  
  # Check database directly
  psql -U user -d scada -c "SELECT mo_id, status_manufacturing FROM mo_batch LIMIT 5;"
  ```

**If count > 0:**
- ✅ Batches to process
- →  **Go to STEP 3**

---

### ✅ STEP 3: Is Payload Complete?

**Command:**
```bash
grep "[TASK 3-DEBUG-10] Complete batch payload:" app.log | tail -1 | head -c 200
```

**Example Good Payload:**
```json
{'status_manufacturing': 1, 'actual_weight_quantity_finished_goods': 87.5, 'consumption_silo_a': 12.5, 'consumption_silo_b': 15.3}
```

**If payload is empty or missing silos:**
- ❌ No consumption data
- **Fix:** Check Task 2 read from PLC
  ```bash
  grep "[TASK 2] ✓ Updated mo_batch" app.log | head -3
  ```

**If payload looks complete:**
- ✅ Good data
- →  **Go to STEP 4** ⚠️ (MOST CRITICAL)

---

### ✅ STEP 4: What's Odoo Response? 🚨 **CRITICAL**

**Command:**
```bash
grep "[TASK 3-DEBUG-13] Odoo response:" app.log | tail -3
```

**Case A: success=True**
```
[TASK 3-DEBUG-13] Odoo response: {'success': True, 'message': 'Manufacturing Order updated successfully'}
```
- ✅ **ODOO ACCEPTED THE UPDATE!**
- → Go to STEP 5 to verify batch cleanup

**Case B: success=False - Connection Error**
```
[TASK 3-DEBUG-13] Odoo response: {'success': False, 'error': 'Connection refused'}
```
- ❌ **Can't reach Odoo server**
- **Fix:**
  ```bash
  # Check Odoo is running
  ping odoo-server.com
  curl -I http://odoo.local:8069
  
  # Check network from container
  docker exec <container> ping odoo-server
  ```

**Case C: success=False - MO Not Found**
```
[TASK 3-DEBUG-13] Odoo response: {'success': False, 'error': 'Manufacturing Order TEST/MO/001 not found'}
```
- ❌ **Wrong MO ID or MO doesn't exist**
- **Fix:**
  ```bash
  # Verify MO exists in Odoo
  # Login to Odoo → Manufacturing → Check MO details
  # Or via API:
  curl -X GET "http://odoo.local:8069/api/scada/mo?id=TEST%2FMO%2F001"
  ```

**Case D: success=False - Wrong Endpoint**
```
[TASK 3-DEBUG-13] Odoo response: {'success': False, 'error': '404 Not Found'}
```
- ❌ **Wrong API endpoint**
- **Fix:**
  ```bash
  # Verify endpoint in consumption_service.py
  # Should be: /api/scada/mo/update-with-consumptions
  cat app/services/odoo_consumption_service.py | grep "endpoint\|url"
  ```

**If response shows success=True:**
- ✅ Odoo accepted the update
- →  **Go to STEP 5**

---

### ✅ STEP 5: Did Batch Get Deleted?

**Command:**
```bash
grep "[TASK 3] ✓✓✓ COMPLETE" app.log | tail -1
```

**Expected Output:**
```
[TASK 3] ✓✓✓ COMPLETE: Batch #1 (MO: TEST/MO/001) synced & archived
```

**If NOT found after Odoo success:**
- ❌ Batch not deleted from mo_batch
- **Likely cause:** Archive or delete operation failed
- **Debug:**
  ```bash
  # Check archive error
  grep "[TASK 3-DEBUG-ERROR" app.log | tail -5
  
  # Check database for orphaned batch
  psql -U user -d scada -c "SELECT * FROM mo_batch WHERE update_odoo=true;"
  ```

**If found:**
- ✅ **COMPLETE SUCCESS! Odoo update is working!**

---

## 📋 STEP-BY-STEP COMMANDS (Copy & Paste)

### **Quick Test (1 minute)**
```bash
# Terminal 1: Watch Task 3 logs
tail -f /path/to/app.log | grep "\[TASK 3\]"

# Terminal 2: Run test (in another terminal)
python test_task2_task3_with_real_data.py

# Wait 3-5 minutes for Task 3 to run
# Look for: "[TASK 3] ✓✓✓ COMPLETE"
```

### **Full Debug Capture (collect for analysis)**
```bash
# Capture last 100 lines mentioning Task 3
tail -100 /path/to/app.log | grep -E "\[TASK [  123]\]" > /tmp/task_debug.log

# Capture all Odoo responses
grep "\[TASK 3-DEBUG-13\]" /path/to/app.log > /tmp/odoo_responses.log

# Show summary
echo "=== Task 3 Runs ===" && \
grep "\[TASK 3\] Process completed batches task running" /path/to/app.log | wc -l && \
echo "=== Success Count ===" && \
grep "\[TASK 3\] ✓ Odoo sync SUCCESS" /path/to/app.log | wc -l && \
echo "=== Failure Count ===" && \
grep "\[TASK 3\] ⚠ Odoo sync FAILED" /path/to/app.log | wc -l
```

---

## 🎯 VERIFICATION - Odoo Update IS Working

### Check These Lines in Log (SUCCESS PATTERN)

```
✓ Line 1: Task 3 running
[TASK 3] Process completed batches task running at: 2026-02-15 10:40:45

✓ Line 2: Found batches
[TASK 3] Found 1 completed batch(es) waiting for Odoo sync

✓ Line 3: Odoo response SUCCESS
[TASK 3-DEBUG-13] Odoo response: {'success': True, ...}

✓ Line 4: Batch completely processed
[TASK 3] ✓✓✓ COMPLETE: Batch #1 (MO: XXX) synced & archived

✓ Line 5: Summary
[TASK 3] Cycle complete: ✓ 1 archived, ⚠ 0 failed, total 1 batches
```

**If you see all 5 lines → Odoo update is working! ✅**

---

## 🚨 COMMON PROBLEMS & QUICK FIXES

| Problem | Debug Command | Fix |
|---------|---------------|-----|
| Odoo timeout | `grep "Connection timeout" app.log` | Check Odoo server, network |
| MO not found | `grep "not found" app.log` | Verify MO exists in Odoo |
| No batches | `grep "Query result count: 0" app.log` | Check PLC completes batch |
| Batch not deleted | `grep "delete_from_batch.*False" app.log` | Check DB constraints |
| Task not running | `grep "TASK 3.*running" app.log` | Check scheduler started |

---

## 📊 QUICK STATUS COMMAND

**One command to see everything:**
```bash
echo "=== TASK 3 STATUS ===" && \
echo "Last run:" && \
grep "\[TASK 3\] Process completed batches task running" app.log | tail -1 && \
echo "" && \
echo "Last Odoo response:" && \
grep "\[TASK 3-DEBUG-13\]" app.log | tail -1 && \
echo "" && \
echo "Stats:" && \
echo "  Total runs: $(grep -c '\[TASK 3\] Process completed batches' app.log)" && \
echo "  Successes: $(grep -c '\[TASK 3\] ✓✓✓ COMPLETE' app.log)" && \
echo "  Failures: $(grep -c '\[TASK 3\] ⚠ Odoo sync FAILED' app.log)"
```

---

## 📞 IF STILL NOT WORKING

1. **Collect these logs:**
   ```bash
   grep "\[TASK [123]\]" app.log > task_debug.log
   grep "\[TASK 3-DEBUG" app.log > task3_full_debug.log
   ```

2. **Check these files:**
   - [TASK 3-DEBUG-13] response in logs
   - Database: `mo_batch` and `mo_histories` tables
   - Odoo API endpoint: `/api/scada/mo/update-with-consumptions`

3. **Enable extra debugging:**
   ```bash
   export LOG_LEVEL=DEBUG
   export SQLALCHEMY_ECHO=true
   # Restart app
   ```

4. **Share with team:**
   - `task3_full_debug.log`
   - Error message from [TASK 3-DEBUG-13]
   - Odoo API response

---

## ✅ SUCCESS CHECKLIST

After implementing debugging:

- ✓ All 3 tasks have debug output
- ✓ Task 3 Odoo sync has detailed logging
- ✓ Failures are logged with reason
- ✓ Retry mechanism is visible in logs
- ✓ Can trace complete batch lifecycle
- ✓ Can identify where update fails

---

**Print this checklist and keep nearby while testing! 📋**

**File:** DEBUG_CHECKLIST.md
**Status:** ✅ Ready to use
**Last Updated:** 2026-02-15
