# 🚀 RUN WITH DEBUGGING - Quick Start Guide

## Enable Debug Logging & Test Odoo Sync

### **Method 1: Run with DEBUG Environment (Recommended)**

```bash
# Step 1: Set LOG_LEVEL to DEBUG
export LOG_LEVEL=DEBUG
export SQLALCHEMY_ECHO=true

# Step 2: Start FastAPI server
python -m uvicorn app.main:app --reload --log-level debug

# Step 3: In another terminal, monitor Task 3 (Odoo sync)
tail -f uvicorn.log | grep -E "\[TASK [123]\]"

# Step 4: Run test script
python test_task2_task3_with_real_data.py

# Step 5: Wait 3-5 minutes for scheduler Task 3 to run
#        Look for: [TASK 3] ✓✓✓ COMPLETE: Batch synced & archived
```

---

## Method 2: Docker with Debug Enabled

```bash
# Edit .env file
cat > .env << EOF
LOG_LEVEL=DEBUG
SQLALCHEMY_ECHO=true
DATABASE_URL=postgresql://user:pass@db:5432/scada
ODOO_URL=http://odoo:8069
EOF

# Run container
docker-compose up -d

# Monitor logs
docker-compose logs -f app | grep "\[TASK"
```

---

## Method 3: Python Script with Debug

```python
# test_with_debug.py
import logging
import os
from app.core.scheduler import auto_sync_mo_task, plc_read_sync_task, process_completed_batches_task

# Enable DEBUG logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

# Run tasks
import asyncio
async def test():
    print("=" * 80)
    print("TASK 1: Fetch MO from Odoo")
    print("=" * 80)
    await auto_sync_mo_task()
    
    await asyncio.sleep(2)
    
    print("\n" + "=" * 80)
    print("TASK 2: Read PLC")
    print("=" * 80)
    await plc_read_sync_task()
    
    await asyncio.sleep(2)
    
    print("\n" + "=" * 80)
    print("TASK 3: Odoo Sync (This is what we're debugging!)")
    print("=" * 80)
    await process_completed_batches_task()

asyncio.run(test())
```

**Run it:**
```bash
python test_with_debug.py 2>&1 | tee debug_output.log
```

---

## 📊 Debug Output Examples

### Healthy Run (All Tasks Success)

```
================================================================================
[TASK 1] Auto-sync MO task running at: 2026-02-15 10:30:00.123456
================================================================================
[TASK 1] ✓ Found 2 MO(s) from Odoo
[TASK 1-DEBUG-7] Syncing to mo_batch database...
[TASK 1] ✓ Database sync completed: 2 MO batches
[TASK 1] ✓ PLC write completed: 2 batches written to PLC
[TASK 1] ✓ Auto-sync completed: 2 MO batches synced & written to PLC


================================================================================
[TASK 2] PLC read sync task running at: 2026-02-15 10:35:00.234567
================================================================================
[TASK 2] Found 2 active batch(es) in queue
[TASK 2-DEBUG-6] PLC sync result: {'success': True, 'mo_id': '123001', 'updated': True}
[TASK 2] ✓ Updated mo_batch for MO: 123001 from PLC data


================================================================================
[TASK 3] Process completed batches task running at: 2026-02-15 10:40:00.345678
================================================================================
[TASK 3] Found 2 completed batch(es) waiting for Odoo sync
[TASK 3] Processing batch #1 (MO: 123001)...
[TASK 3-DEBUG-10] Complete batch payload: {'status_manufacturing': 1, 'actual_weight_quantity_finished_goods': 87.5}
[TASK 3] ➜ Sending Odoo sync request for batch #1...
[TASK 3-DEBUG-13] Odoo response: {'success': True, 'message': 'Manufacturing Order updated'}
[TASK 3] ✓ Odoo sync SUCCESS for batch #1 (MO: 123001)
[TASK 3] ✓ Set update_odoo=True for batch #1
[TASK 3] ✓✓✓ COMPLETE: Batch #1 (MO: 123001) synced & archived
[TASK 3] Cycle complete: ✓ 2 archived, ⚠ 0 failed, total 2 batches
[TASK 3] ✓ All batches processed successfully!
```

### Odoo Sync Failure (With Debug)

```
[TASK 3] Processing batch #2 (MO: 123002)...
[TASK 3-DEBUG-10] Complete batch payload: {'status_manufacturing': 1, 'actual_weight_quantity_finished_goods': 75.3}
[TASK 3] ➜ Sending Odoo sync request for batch #2...
[TASK 3-DEBUG-13] Odoo response: {'success': False, 'error': 'Connection timeout to Odoo server'}
[TASK 3] ⚠ Odoo sync FAILED for batch #2 (MO: 123002): Connection timeout to Odoo server
[TASK 3-DEBUG-ERROR-4] Batch will remain in queue with update_odoo=False for retry
[TASK 3] Cycle complete: ✓ 1 archived, ⚠ 1 failed, total 2 batches
✓ GOOD NEWS: Batch will retry automatically in next cycle (3 minutes)
```

---

## 🔍 Log Analysis Commands

After running with debug enabled, use these to analyze:

### Find the Odoo Response (Most Important!)
```bash
grep "\[TASK 3-DEBUG-13\]" debug_output.log
```

### Count Results
```bash
echo "SUCCESS:" && grep -c "✓ Odoo sync SUCCESS" debug_output.log
echo "FAILURES:" && grep -c "⚠ Odoo sync FAILED" debug_output.log
echo "COMPLETE:" && grep -c "✓✓✓ COMPLETE" debug_output.log
```

### See Timeline
```bash
grep "\[TASK" debug_output.log | grep "running at\|Processing batch"
```

### Export for Analysis
```bash
# Save in readable format
cat debug_output.log | grep "\[TASK" > task_summary.log
cat debug_output.log | grep "\[TASK 3-DEBUG-13\]" > odoo_responses.log
```

---

## 🎯 What to Look For

### ✅ SUCCESS Signs
```
✓ [TASK 1] Auto-sync completed
✓ [TASK 2] ✓ Updated mo_batch
✓ [TASK 3] ✓ Odoo sync SUCCESS
✓ [TASK 3] ✓✓✓ COMPLETE
```

### ❌ FAILURE Signs
```
✗ [TASK 1] ✗ ERROR
✗ [TASK 2] PLC sync failed
✗ [TASK 3] ⚠ Odoo sync FAILED
✗ [TASK 3-DEBUG-ERROR]
```

---

## 🚨 If Odoo Update Still Fails

### **STEP 1: Check debug output**
```bash
tail -200 debug_output.log | grep "[TASK 3]"
```
Look for [TASK 3-DEBUG-13] - Odoo response

### **STEP 2: Check specific error**
```bash
# Pick the error type from response
# Then check fix below
```

| Error | What It Means | Fix |
|-------|--------------|-----|
| `Connection refused` | Odoo server not running | Start Odoo server |
| `Connection timeout` | Network issue | Check network/firewall |
| `Manufacturing Order not found` | Wrong MO ID | Check MO exists in Odoo |
| `Unauthorized` | Auth failed | Check Odoo credentials |
| `404 Not Found` | Wrong API endpoint | Check endpoint URL |

### **STEP 3: Try manual test**
```bash
# Test Odoo API directly
curl -X POST "http://odoo-server:8069/api/scada/mo/update-with-consumptions" \
  -H "Content-Type: application/json" \
  -d '{
    "mo_id": "TEST/MO/001",
    "equipment_id": "PLC01",
    "status_manufacturing": 1,
    "consumption_silo_a": 10.5
  }'
```

---

## 📈 Monitoring Dashboard

Create a simple monitoring script:

```bash
#!/bin/bash
# monitor.sh

while true; do
    clear
    echo "=== SCADA Debugging Dashboard ==="
    echo "Time: $(date)"
    echo ""
    
    echo "Task 1 (Last Sync):"
    tail -1 app.log | grep "[TASK 1]" || echo "  No recent activity"
    echo ""
    
    echo "Task 2 (Last Read):"
    tail -1 app.log | grep "[TASK 2]" || echo "  No recent activity"
    echo ""
    
    echo "Task 3 (Odoo Sync Stats):"
    echo "  Runs: $(grep -c '\[TASK 3\] Process completed batches' app.log)"
    echo "  Success: $(grep -c '✓✓✓ COMPLETE' app.log)"
    echo "  Failures: $(grep -c '⚠ Odoo sync FAILED' app.log)"
    echo ""
    
    echo "Last Odoo Response:"
    grep "\[TASK 3-DEBUG-13\]" app.log | tail -1 | sed 's/.*Odoo response: /  /'
    echo ""
    
    sleep 5
done
```

**Run it:**
```bash
chmod +x monitor.sh
./monitor.sh
```

---

## 🧪 Complete Testing Flow

```bash
# 1. Enable debug
export LOG_LEVEL=DEBUG

# 2. Start server
python -m uvicorn app.main:app --log-level debug > debug_output.log 2>&1 &
sleep 2

# 3. Monitor logs
tail -f debug_output.log | grep "\[TASK" &

# 4. Run test (creates batch data)
python test_task2_task3_with_real_data.py

# 5. Wait 5 minutes for scheduler to run
echo "Waiting for scheduler (3-5 minutes)..."
sleep 300

# 6. Analyze results
echo ""
echo "=== RESULTS ==="
grep "✓✓✓ COMPLETE" debug_output.log && echo "✅ Success!" || echo "❌ Check logs"

# 7. Show summary
echo ""
echo "=== SUMMARY ==="
echo "Total Task 3 runs: $(grep -c '[TASK 3] Process completed' debug_output.log)"
echo "Successful syncs: $(grep -c '✓✓✓ COMPLETE' debug_output.log)"
echo "Failed syncs: $(grep -c '⚠ Odoo sync FAILED' debug_output.log)"
```

---

## 📚 Documentation Index

After implementing debugging, review these docs in order:

1. **DEBUG_CHECKLIST.md** ← **START HERE** (Quick diagnosis)
2. **DEBUG_QUICK_REFERENCE.md** (Odoo sync specific)
3. **DEBUG_COMPREHENSIVE_GUIDE.md** (Full reference)
4. **DEBUG_IMPLEMENTATION_SUMMARY.md** (What was added)

---

## ✅ Next Steps

1. ✓ Enable debug (`export LOG_LEVEL=DEBUG`)
2. ✓ Start server with debug output
3. ✓ Run test script
4. ✓ Check for Odoo sync in logs
5. ✓ Use debug points to troubleshoot
6. ✓ Reference docs (see above)

---

**Status:** ✅ Ready to Debug

**Questions?** Check DEBUG_QUICK_REFERENCE.md or DEBUG_CHECKLIST.md

**Having issues?** Collect debug logs and share [TASK 3-DEBUG-13] output.
