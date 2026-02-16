# Equipment Failure Sync - Quick Debug Commands

## Quick Diagnosis

### 1. Check Server is Running with Task 5
```bash
# Terminal 1
cd c:\projek\fastapi-scada-odoo
python -m uvicorn app.main:app --reload
```

Look for in output:
```
[TASK 5] Equipment failure monitoring task running...
```

If NOT appearing every 5 minutes, check:
```bash
cat .env | grep TASK_5
# Should show: ENABLE_TASK_5_EQUIPMENT_FAILURE=true
```

---

### 2. Write Test Data to PLC
```bash
python test_equipment_failure_write.py
```

Expected: ✓ All data written

---

### 3. Read Test Data from PLC
```bash
python test_equipment_failure_read.py
```

Expected output:
```
✓ Equipment Code: silo101
✓ Failure Info: START_FAILURE
✓ Timestamp: 2026-02-23 20:22:35
```

If FAIL → PLC not accessible, check PLC_IP in .env

---

### 4. Check Local Database
```bash
psql $DATABASE_URL -c "
  SELECT equipment_code, description, failure_date, source
  FROM scada.equipment_failure
  ORDER BY created_at DESC LIMIT 5;
"
```

If NO RECORDS → DB save not working (check Step 2 logs)

---

### 5. Check Odoo Connection
```bash
# Test authentication only
curl -X POST http://localhost:8009/api/scada/authenticate \
  -H "Content-Type: application/json" \
  -d '{
    "db": "odoo_dev",
    "login": "admin",
    "password": "password"
  }' | python -m json.tool
```

Expected response:
```json
{
  "status": "success",
  "message": "Authentication successful"
}
```

If ERROR → Check ODOO_BASE_URL, ODOO_DB, credentials in .env

---

### 6. Check Equipment Exists in Odoo
```bash
# In Odoo, query directly:
psql odoo_db << EOF
SELECT id, code, name FROM scada_equipment WHERE code = 'silo101';
EOF
```

If NO RECORDS → Create equipment master in Odoo first

---

### 7. Monitor Logs in Real-Time
```bash
# Terminal 2 - Watch Task 5 only
cd c:\projek\fastapi-scada-odoo
python -m uvicorn app.main:app --reload 2>&1 | grep "TASK 5"
```

OR for complete flow:
```bash
python -m uvicorn app.main:app --reload 2>&1 | grep -E "TASK 5|Odoo Auth|Odoo API"
```

---

## Debug Checklist

```
STEP 1: PLC Read
- [ ] See "[TASK 5] ✓ Equipment Failure Detected from PLC:"
- [ ] equipment_code displays correctly
- [ ] failure_info displays correctly  
- [ ] timestamp displays correctly

STEP 2: Local DB Save
- [ ] See "[TASK 5] ✓ Equipment failure saved to DB"
- [ ] Record ID shows in logs
- [ ] Query database confirms record saved

STEP 3: Odoo Sync
- [ ] See "[Odoo Auth] ✓ Successfully authenticated"
- [ ] See "[Odoo API] Step 2: Sending POST request"
- [ ] See "[Odoo API] Response status code: 200"
- [ ] See "[Odoo API] ✓ Failure report created successfully"
- [ ] Query Odoo database confirms record created
```

---

## Common Quick Fixes

### Fix 1: Task 5 Not Running
```bash
# Check if enabled
grep ENABLE_TASK_5 .env

# If not found, add to .env:
ENABLE_TASK_5_EQUIPMENT_FAILURE=true
EQUIPMENT_FAILURE_INTERVAL_MINUTES=5
```

### Fix 2: No Connection to Odoo
```bash
# Test URL
curl http://localhost:8009/

# If fail, start Odoo service:
# (depends on your setup - could be Docker container, systemd service, etc.)
```

### Fix 3: Equipment Not Found in Odoo
```bash
# In Odoo, create test equipment:
psql odoo_dev << EOF
INSERT INTO scada_equipment (code, name) 
VALUES ('silo101', 'Test Silo 101');
EOF
```

### Fix 4: No Records in Local Database
```bash
# Check table exists
psql $DATABASE_URL -c "\d scada.equipment_failure"

# If not, run migrations:
alembic upgrade head
```

### Fix 5: Duplicate Detection Preventing Test
```bash
# Clear test data and retry
psql $DATABASE_URL -c "DELETE FROM scada.equipment_failure WHERE equipment_code='silo101';"

# Re-write test data to PLC
python test_equipment_failure_write.py

# Wait for next scheduler execution (5 minutes max)
```

---

## Log Search Patterns

**Find all Task 5 entries:**
```bash
# In running server, copy log line starting with [TASK 5]
```

**Find authentication errors:**
```bash
# Look for: [Odoo Auth] ✗
```

**Find API errors:**
```bash
# Look for: [Odoo API] ✗ or [Odoo API] Response status code: >= 400
```

**Find successful syncs:**
```bash
# Look for: [TASK 5] ✓ Odoo sync successful
```

---

## Performance Notes

- **PLC Read:** ~500ms
- **DB Save:** ~100ms  
- **Odoo Auth + Sync:** ~1-2s
- **Total:** ~2.5s per execution
- **Frequency:** Every 5 minutes (default)

---

## Environment Variables

Quick reference for `.env`:

```bash
# Must have for Odoo sync:
ODOO_BASE_URL=http://localhost:8009
ODOO_DB=odoo_dev
ODOO_USERNAME=admin
ODOO_PASSWORD=password

# Must have for PLC read:
PLC_IP=192.168.1.100
PLC_PORT=44818

# Control Task 5:
ENABLE_TASK_5_EQUIPMENT_FAILURE=true
EQUIPMENT_FAILURE_INTERVAL_MINUTES=5

# For debug output:
LOG_LEVEL=INFO  # Set to DEBUG for more verbose
```

---

## Files to Check

If issues persist, review these files in order:

1. `.env` - Configuration
2. `app/reference/EQUIPMENT_FAILURE_REFERENCE.json` - PLC mapping
3. `app/core/scheduler.py` line 298+ - Task 5 logic
4. `app/services/equipment_failure_service.py` - Odoo API calls
5. `app/services/equipment_failure_db_service.py` - Database save logic

---

## Support Documentation

For detailed troubleshooting, see:
- `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` - Complete troubleshooting guide
- `EQUIPMENT_FAILURE_ODOO_SYNC_REPORT.md` - What was fixed and why

