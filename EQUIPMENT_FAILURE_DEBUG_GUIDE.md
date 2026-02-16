# Equipment Failure Odoo Sync Debug Guide

## Overview
Panduan lengkap untuk debug alur equipment failure dari PLC → Local DB → Odoo API.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SCHEDULER TASK 5: Equipment Failure Monitoring                │
│  (Runs every 5 minutes or EQUIPMENT_FAILURE_INTERVAL_MINUTES)   │
└────────────────┬────────────────────────────────────────────────┘
                 │
    ┌────────────┴───────────────────────┐
    │                                    │
    ▼                                    ▼
┌──────────────────────┐        ┌──────────────────────┐
│ Step 1: Read from    │        │ Step 2: Save to      │
│ PLC (FINS Protocol)  │        │ Local DB             │
│                      │        │ (change detection)   │
│ Data Sources:        │        │                      │
│ - D7710-D7717: ASCII │        │ Table:               │
│   equipment_code     │        │ scada.equipment_     │
│ - D7718-D7725: ASCII │        │ failure              │
│   failure_info       │        │                      │
│ - D7726-D7732: BCD   │        │ Unique Constraint:   │
│   timestamp (YMDHS)  │        │ (equipment_code,     │
└──────────────────────┘        │  failure_date,       │
    │                           │  description)        │
    │ Data Parsed               │                      │
    │ equipment_code: silo101   │                      │
    │ failure_info: START_FAIL  │                      │
    │ failure_timestamp:        │                      │
    │ 2026-02-23 20:22:35       │                      │
    │                           └──────────────────────┘
    │                                    │
    │ Success: {"saved": true,           │
    │           "record_id": "uuid-xxx"} │
    │                                    │
    └────────────────┬───────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ Step 3: Sync to      │
          │ Odoo API             │
          │                      │
          │ 3a. Authenticate     │
          │  POST /api/scada/    │
          │      authenticate    │
          │                      │
          │ 3b. Create Report    │
          │  POST /api/scada/    │
          │      failure-report  │
          │                      │
          │ Payload:             │
          │ {                    │
          │   "equipment_code":  │
          │   "silo101",         │
          │   "description":     │
          │   "START_FAILURE",   │
          │   "date": "2026-0... │
          │ }                    │
          └──────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ Odoo Response         │
          │ {                     │
          │  "status": "success", │
          │  "data": {...}        │
          │ }                     │
          └──────────────────────┘
```

## Debug Logging Output

### Expected Success Flow

```
[TASK 5] ========== START Equipment Failure Monitoring Task ==========
[TASK 5] Step 1: Reading equipment failure from PLC...
[TASK 5] ✓ Equipment Failure Detected from PLC:
  Equipment Code: silo101 (type: str)
  Failure Type: START_FAILURE (type: str)
  Timestamp: 2026-02-23 20:22:35 (type: str)
[TASK 5] ✓ Parsed failure_date: 2026-02-23 20:22:35
[TASK 5] Step 2: Saving to local database with change detection...
[TASK 5] ✓ Equipment failure saved to DB
  Record ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Equipment: silo101
  Description: START_FAILURE
[TASK 5] Step 3: Syncing to Odoo via API...
[TASK 5] Calling Odoo API create_failure_report:
  URL: http://localhost:8009/api/scada/failure-report
  Equipment: silo101
  Description: START_FAILURE
  Date: 2026-02-23 20:22:35
[Odoo Auth] Attempting authentication at: http://localhost:8009/api/scada/authenticate
[Odoo Auth] ✓ Successfully authenticated with Odoo (cookies set)
[Odoo API] Starting create_failure_report: equipment=silo101, description=START_FAILURE
[Odoo API] Step 1: Authenticating with Odoo...
[Odoo API] Step 2: Sending POST request
  URL: http://localhost:8009/api/scada/failure-report
  Payload: {'equipment_code': 'silo101', 'description': 'START_FAILURE', 'date': '2026-02-23 20:22:35'}
[Odoo API] Response status code: 200
[Odoo API] ✓ Failure report created successfully
  Equipment: silo101
  Description: START_FAILURE
  ID: a1b2c3d4-e5f6-7890-1234-567890abcdef
  Message: Failure report created successfully
[TASK 5] ✓ Odoo sync successful
  Status: success
  Message: Failure report created successfully
  Data: {'id': 'a1b2c3d4-e5f6-7890-1234-567890abcdef', ...}
[TASK 5] ========== END Equipment Failure Monitoring Task ==========
```

## Common Issues & Solutions

### Issue 1: Equipment Failure Not Detected from PLC

**Log Pattern:**
```
[TASK 5] No equipment failure detected or read failed
```

**Troubleshooting Steps:**
1. Check PLC connection:
   ```bash
   ping <PLC_IP>
   # Verify from .env: PLC_IP, PLC_PORT, PLC_TIMEOUT_SEC
   ```

2. Verify EQUIPMENT_FAILURE_REFERENCE.json mapping:
   ```bash
   cat app/reference/EQUIPMENT_FAILURE_REFERENCE.json
   ```

3. Test direct PLC read:
   ```bash
   python test_equipment_failure_read.py
   ```

4. Check memory addresses in PLC:
   - D7710-D7717: equipment_code (ASCII, 16 bytes)
   - D7718-D7725: failure_info (ASCII, 16 bytes)
   - D7726-D7732: Timestamp BCD (Year/Month/Day/Hour/Min/Sec)

**Solution:**
- Ensure test data is written to PLC memory
- Check FinsUdpClient connection settings
- Verify memory read frame is built correctly

---

### Issue 2: Data Parsed but Not Saved to DB

**Log Pattern:**
```
[TASK 5] ⚠ Missing data for DB save:
  equipment_code=silo101
  failure_info=START_FAILURE
  failure_date=None
```

**Root Causes:**
- Timestamp parsing failed
- Invalid date format

**Troubleshooting:**
1. Check timestamp format in logs:
   ```
   [TASK 5] ✓ Parsed failure_date: <should show datetime object>
   ```

2. If you see:
   ```
   [TASK 5] ⚠ Invalid timestamp format: <value> - <error>
   ```
   - Verify PLC timestamp is in correct BCD format
   - Check EQUIPMENT_FAILURE_REFERENCE.json BCD field mappings

**Solution:**
- Re-write test data to PLC with correct timestamp
- Verify BCD conversion in plc_equipment_failure_service.py

---

### Issue 3: Data Saved to DB but Not Syncing to Odoo

**Log Pattern:**
```
[TASK 5] ✓ Equipment failure saved to DB
  Record ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Equipment: silo101
  Description: START_FAILURE
[TASK 5] Step 3: Syncing to Odoo via API...
[TASK 5] Calling Odoo API create_failure_report...
[Odoo Auth] ✗ Authentication failed
```

**Root Causes:**
- Odoo not running or unreachable
- Invalid credentials in .env
- Odoo API endpoint not implemented

**Troubleshooting:**
1. Check Odoo connectivity:
   ```bash
   curl -X POST http://<ODOO_URL>/api/scada/authenticate \
     -H "Content-Type: application/json" \
     -d '{
       "db": "odoo_db",
       "login": "admin",
       "password": "password"
     }'
   ```

2. Verify .env settings:
   ```bash
   cat .env | grep ODOO
   # Check: ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
   ```

3. Check if Odoo is running:
   ```bash
   curl http://<ODOO_URL>/
   ```

**Solution:**
- Start/restart Odoo service
- Verify credentials in .env
- Ensure /api/scada/authenticate endpoint exists in Odoo
- Ensure /api/scada/failure-report endpoint exists in Odoo

---

### Issue 4: Duplicate Detection Preventing DB Save

**Log Pattern:**
```
[TASK 5] ⊘ Skipped DB save (duplicate detection)
  Reason: Last recorded equipment_code=silo101 with same failure_info and timestamp
  Equipment: silo101
```

**Meaning:**
This is EXPECTED behavior. The system has a `save_if_changed()` method that only saves if the data is new.

**Check if this is OK:**
1. Query database:
   ```bash
   psql $DATABASE_URL -c "SELECT * FROM scada.equipment_failure ORDER BY created_at DESC LIMIT 5;"
   ```

2. If you see records within last 5 minutes with same equipment_code, failure_info, and timestamp, that's correct.

**If you want to force re-test:**
- Clear the database: `DELETE FROM scada.equipment_failure WHERE equipment_code='silo101';`
- Re-write test data to PLC (to trigger new failure detection)
- Watch scheduler logs for next execution (every 5 minutes)

---

### Issue 5: Odoo Auth Succeeds but Failure Report Creation Fails

**Log Pattern:**
```
[Odoo Auth] ✓ Successfully authenticated with Odoo (cookies set)
[Odoo API] ✓ Failure report created successfully... [NO - actually error]
[Odoo API] ✗ Failure report creation failed
  Status: error
  Message: <error message from Odoo>
  Full response: {...}
```

**Common Odoo Errors:**
1. **"scada.equipment not found with code silo101"**
   - Equipment master data not created in Odoo
   - Solution: Create equipment record in Odoo with code "silo101"

2. **"Invalid field description"**
   - Field name mismatch or validation issue
   - Solution: Check Odoo scada.failure model expected fields

3. **"Permission denied"**
   - User doesn't have permission to create failure reports
   - Solution: Grant user permission in Odoo

**Troubleshooting:**
1. Test equipment exists in Odoo:
   ```bash
   curl -X GET http://<ODOO_URL>/api/scada/equipment?code=silo101 \
     -H "Authorization: Bearer <token>"
   ```

2. Check Odoo failure report schema:
   - Log in to Odoo
   - Go to Development → Database Structure → scada.failure
   - Check required and expected fields

3. Test Odoo API directly:
   ```bash
   # First authenticate
   curl -c cookies.txt -X POST http://<ODOO_URL>/api/scada/authenticate \
     -H "Content-Type: application/json" \
     -d '{
       "db": "odoo_db",
       "login": "admin",
       "password": "password"
     }'
   
   # Then create failure report
   curl -b cookies.txt -X POST http://<ODOO_URL>/api/scada/failure-report \
     -H "Content-Type: application/json" \
     -d '{
       "equipment_code": "silo101",
       "description": "START_FAILURE",
       "date": "2026-02-23 20:22:35"
     }'
   ```

**Solution:**
- Verify equipment exists in Odoo
- Check Odoo API validation rules
- Verify user has correct permissions
- Check error message in Odoo logs

---

### Issue 6: Debug Info Not Appearing in Logs

**Troubleshooting:**
1. Check if logging is enabled:
   ```bash
   # In app/core/config.py or .env
   LOG_LEVEL=INFO  # or DEBUG for more verbose
   ```

2. Check logger output redirection:
   - Console: `python -m uvicorn app.main:app --reload`
   - File: Check configured log file path

3. Verify Task 5 is enabled:
   ```bash
   cat .env | grep TASK_5
   # Should show: ENABLE_TASK_5_EQUIPMENT_FAILURE=true
   ```

4. Check scheduler is running:
   ```bash
   # Should see in uvicorn output
   [TASK 1] Auto-sync MO task running...
   [TASK 2] Read PLC monitoring task running...
   [TASK 3] Process completed batches task running...
   [TASK 4] Monitor batch health task running...
   [TASK 5] Equipment failure monitoring task running...
   ```

---

## Manual Testing Steps

### 1. Write Test Data to PLC

```bash
python test_equipment_failure_write.py
```

Expected output:
```
Writing equipment failure data to PLC...
✓ Written equipment_code: silo101 to D7710-D7717
✓ Written failure_info: START_FAILURE to D7718-D7725
✓ Written timestamp: 2026-02-23 20:22:35 to D7726-D7732
All data written successfully!
```

### 2. Read Data from PLC

```bash
python test_equipment_failure_read.py
```

Expected output:
```
Reading equipment failure data from PLC...
✓ Equipment Code: silo101
✓ Failure Info: START_FAILURE
✓ Timestamp: 2026-02-23 20:22:35
All data read successfully!
```

### 3. Check Local Database

```bash
# Connect to PostgreSQL
psql $DATABASE_URL

# View equipment failure table schema
\d scada.equipment_failure

# View recent failures
SELECT 
  id,
  equipment_code,
  description,
  failure_date,
  source,
  severity,
  created_at
FROM scada.equipment_failure
ORDER BY created_at DESC
LIMIT 10;

# Count by equipment
SELECT equipment_code, COUNT(*) as count
FROM scada.equipment_failure
GROUP BY equipment_code;
```

### 4. Check Odoo Database

```bash
# Connect to Odoo PostgreSQL
psql odoo_db -U odoo

# View failure reports created by SCADA
SELECT id, equipment_code, description, failure_date, created_at
FROM scada_failure_report
ORDER BY created_at DESC
LIMIT 10;

# Check if equipment exists
SELECT id, code, name
FROM scada_equipment
WHERE code = 'silo101';
```

### 5. Monitor Scheduler in Real-Time

```bash
# Start server with verbose logging
python -m uvicorn app.main:app --reload --log-level=DEBUG

# In another terminal, watch logs (if using file logging)
tail -f app.log

# Watch for Task 5 execution every 5 minutes:
grep "TASK 5" app.log
```

---

## Performance Metrics

### Task 5 Execution Time
- PLC read: ~500ms
- DB save: ~100ms
- Odoo auth + sync: ~1-2s
- **Total: ~2.5s per execution**

### Frequency
- Default: Every 5 minutes (EQUIPMENT_FAILURE_INTERVAL_MINUTES=5)
- Configurable via .env

### Duplicate Detection
- Uses unique constraint: (equipment_code, failure_date, description)
- Prevents re-syncing same failure to Odoo multiple times

---

## Configuration Reference

### .env Variables

```bash
# PLC Configuration
PLC_IP=192.168.1.100
PLC_PORT=44818
PLC_TIMEOUT_SEC=5

# Odoo Configuration
ODOO_BASE_URL=http://localhost:8009
ODOO_DB=odoo_dev
ODOO_USERNAME=admin
ODOO_PASSWORD=password

# Scheduler Configuration
ENABLE_TASK_5_EQUIPMENT_FAILURE=true
EQUIPMENT_FAILURE_INTERVAL_MINUTES=5

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/database

# Logging
LOG_LEVEL=INFO
```

### EQUIPMENT_FAILURE_REFERENCE.json

```json
{
  "fields": [
    {"field": "equipment_code", "type": "ASCII", "address": "D7710", "length": 16},
    {"field": "failure_info", "type": "ASCII", "address": "D7718", "length": 16},
    {"field": "year", "type": "BCD", "address": "D7726"},
    {"field": "month", "type": "BCD", "address": "D7727"},
    {"field": "day", "type": "BCD", "address": "D7728"},
    {"field": "hour", "type": "BCD", "address": "D7730"},
    {"field": "minute", "type": "BCD", "address": "D7731"},
    {"field": "second", "type": "BCD", "address": "D7732"}
  ]
}
```

---

## Summary Checklist

- [ ] PLC is running and accessible (ping test)
- [ ] Test data written to PLC memory
- [ ] Test data can be read from PLC
- [ ] Local database has equipment_failure records
- [ ] Odoo is running and accessible
- [ ] Odoo /api/scada/authenticate endpoint works
- [ ] Odoo /api/scada/failure-report endpoint works
- [ ] Equipment master data exists in Odoo for each equipment_code
- [ ] Scheduler logs show Task 5 executing every 5 minutes
- [ ] Logs show complete pipeline: PLC read → DB save → Odoo sync
- [ ] Odoo database shows failure records created from SCADA

---

## Getting Help

If issues persist:
1. Collect logs: `grep "TASK 5" app.log > task5_debug.log`
2. Check data flow at each step
3. Test components individually
4. Review Odoo API responses for specific error messages
5. Check database constraints and data validation

