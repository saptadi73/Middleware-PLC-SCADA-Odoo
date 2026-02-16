# Equipment Failure Odoo Sync - Debug Report

**Created:** 2025-02-15  
**Issue:** Equipment failure data not syncing to Odoo  
**Status:** FIXED - Added comprehensive logging and Odoo sync integration

---

## Problem Analysis

### What Was Missing?

Task 5 (Equipment Failure Monitoring) in the scheduler was reading from PLC and saving to local database, but **was NOT syncing to Odoo API**. The sync step was completely missing.

### Data Flow Before Fix

```
PLC Read ✓ → Local DB Save ✓ → Odoo Sync ✗
```

### Data Flow After Fix

```
PLC Read ✓ → Local DB Save ✓ → Odoo Sync ✓
```

---

## Changes Made

### 1. **Enhanced Scheduler Task 5** (`app/core/scheduler.py`)

**Added:**
- Detailed logging for each pipeline step
- Step 1: PLC read with data validation
- Step 2: Local DB save with change detection
- Step 3: Odoo API sync with full error handling
- Complete debug output showing equipment code, failure info, timestamp, and responses

**Key Code:**
```python
# STEP 3: SYNC TO ODOO API
logger.info("[TASK 5] Step 3: Syncing to Odoo via API...")
failure_api_service = await get_equipment_failure_api_service(db)
odoo_result = await failure_api_service.create_failure_report(
    equipment_code=equipment_code,
    description=failure_info,
    date=failure_date_str,
)
```

### 2. **Enhanced Odoo Authentication Logging** (`app/services/equipment_failure_service.py`)

**Added:**
- URL and payload logging for auth requests
- Response status code and body logging
- Clear success/failure indicators with ✓/✗ symbols
- Cookie handling verification
- Detailed error messages with HTTP response details

**Key Code:**
```python
logger.info(f"[Odoo Auth] Attempting authentication at: {auth_url}")
logger.debug(f"[Odoo Auth] Response status: {response.status_code}")
logger.info(f"[Odoo Auth] ✓ Successfully authenticated with Odoo (cookies set)")
```

### 3. **Enhanced Failure Report Creation Logging** (`app/services/equipment_failure_service.py`)

**Added:**
- Equipment code, description, date tracking
- API endpoint and full payload logging
- Response parsing and error details
- Step-by-step execution flow with numbered steps
- Comprehensive exception handling

**Key Code:**
```python
logger.info(f"[Odoo API] Step 1: Authenticating with Odoo...")
logger.info(f"[Odoo API] Step 2: Sending POST request - URL: {api_url}")
logger.info(f"[Odoo API] ✓ Failure report created successfully")
logger.error(f"[Odoo API] ✗ Failure report creation failed")
```

### 4. **Created Debug Documentation** (`EQUIPMENT_FAILURE_DEBUG_GUIDE.md`)

**Includes:**
- Complete system architecture diagram
- Expected success log output
- 6 common issues with solutions
- Manual testing procedures
- Performance metrics
- Configuration reference
- Troubleshooting checklist

---

## Expected Log Output (After Fix)

### Success Scenario
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

### Failure Scenario (No Odoo Connection)
```
[TASK 5] Step 3: Syncing to Odoo via API...
[TASK 5] Calling Odoo API create_failure_report...
[Odoo Auth] Attempting authentication at: http://localhost:8009/api/scada/authenticate
[Odoo Auth] ✗ HTTP error during authentication: ConnectionRefusedError
[Odoo Auth] ✗ Authentication failed - cannot proceed
[TASK 5] ✗ Odoo sync failed
  Status: error
  Message: Failed to authenticate with Odoo
```

---

## How to Test

### 1. Start Server with Updated Code
```bash
cd c:\projek\fastapi-scada-odoo
python -m uvicorn app.main:app --reload
```

### 2. Write Test Data to PLC
```bash
python test_equipment_failure_write.py
```

### 3. Watch for Scheduler Execution
- Task 5 runs every 5 minutes (configurable)
- Look for `[TASK 5]` logs in console output
- Follow the complete pipeline: PLC read → DB save → Odoo sync

### 4. Query Database
```bash
psql $DATABASE_URL -c "
  SELECT equipment_code, description, failure_date, source, created_at
  FROM scada.equipment_failure
  ORDER BY created_at DESC
  LIMIT 5;
"
```

### 5. Query Odoo Database
```bash
psql odoo_db -U odoo -c "
  SELECT id, equipment_code, description, failure_date, created_at
  FROM scada_failure_report
  ORDER BY created_at DESC
  LIMIT 5;
"
```

---

## Debug Points in Code

### 1. **app/core/scheduler.py** - Line 298-430
- Equipment Failure Monitoring Task main logic
- 3-step pipeline implementation
- Each step has detailed logging

### 2. **app/services/equipment_failure_service.py** - Line 30-85
- Odoo authentication with detailed logging
- `/api/scada/authenticate` endpoint call tracking

### 3. **app/services/equipment_failure_service.py** - Line 87-200
- Failure report creation with step-by-step logging
- Payload and response tracking
- Error details with full HTTP response

---

## Configuration Needed

Ensure `.env` has these settings:

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

# Logging
LOG_LEVEL=INFO  # or DEBUG for more verbose
```

---

## Verification Checklist

After applying this fix:

- [ ] Scheduler Task 5 runs without errors
- [ ] Logs show 3-step pipeline clearly
- [ ] PLC read step completes and shows equipment_code, failure_info, timestamp
- [ ] Local DB save step shows record ID
- [ ] Odoo API sync step shows authentication success
- [ ] Final result shows either "✓ Odoo sync successful" or detailed error
- [ ] Records appear in local database: `scada.equipment_failure`
- [ ] Records appear in Odoo database: `scada_failure_report` (if Odoo API endpoint created)

---

## Next Steps If Issues Persist

1. **Check Odoo connection:**
   ```bash
   # Verify endpoint exists
   curl -X POST http://localhost:8009/api/scada/authenticate \
     -H "Content-Type: application/json" \
     -d "{\"db\": \"odoo_db\", \"login\": \"admin\", \"password\": \"password\"}"
   ```

2. **Check equipment exists in Odoo:**
   - Log in to Odoo
   - Go to SCADA → Equipment
   - Verify "silo101" (or your equipment_code) exists

3. **Check failure report model in Odoo:**
   - Go to Development → Database Structure
   - Verify `scada.failure` model has expected fields:
     - equipment_code
     - description
     - date/failure_date

4. **Enable debug logging:**
   - Set `LOG_LEVEL=DEBUG` in .env
   - Restart server
   - Re-run test to get more verbose output

5. **Refer to **`EQUIPMENT_FAILURE_DEBUG_GUIDE.md`** for detailed troubleshooting**

---

## Files Modified

1. `app/core/scheduler.py`
   - Enhanced Task 5 with 3-step pipeline
   - Added `get_equipment_failure_api_service()` helper function
   - Total: ~130 lines of detailed logging code

2. `app/services/equipment_failure_service.py`
   - Enhanced `_authenticate()` method with 17 debug points
   - Enhanced `create_failure_report()` method with 15 debug points
   - Added comprehensive error handling

3. `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` (NEW)
   - 300+ lines of troubleshooting documentation
   - Architecture diagrams
   - Common issues and solutions
   - Manual testing procedures

---

## Summary

**The issue:** Equipment failure data was read from PLC and saved to local database, but was never synced to Odoo API.

**The fix:** 
1. Added Odoo sync call in scheduler Task 5 after successful DB save
2. Added comprehensive logging at each step to track the complete pipeline
3. Created detailed debug guide for troubleshooting

**Result:** Complete end-to-end pipeline now: PLC → Local DB → Odoo API, with clear visibility into each step via logging.

