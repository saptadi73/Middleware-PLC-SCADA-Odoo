# Equipment Failure Odoo Sync - Troubleshooting Guide

## 🔴 Issue Found: Odoo Not Reachable

**Status:** Equipment failure data sudah masuk ke local DB ✓  
**Problem:** Odoo tidak bisa diakses via `http://localhost:8009` ✗

---

## Diagnosis

### Current Status
```
Database:           ✓ Equipment failure stored in local PostgreSQL
PLC Read:           ✓ Data successfully read from PLC
Local DB Save:      ✓ Data saved with change detection
Odoo Connection:    ✗ FAILED - Connection refused
```

---

## Solutions

### 1️⃣ Check if Odoo is Running

```bash
# Test connection to Odoo
curl http://localhost:8009/

# If you get "Connection refused", Odoo is not running
```

### 2️⃣ Start Odoo Service

Depending on your setup:

**If using Docker:**
```bash
docker-compose up -d  # Start Odoo container
docker ps  # Verify it's running
```

**If using systemd:**
```bash
sudo systemctl start odoo  # Start Odoo service
sudo systemctl status odoo  # Check status
```

**If running standalone:**
```bash
# Navigate to Odoo directory
cd /path/to/odoo
python -m odoo.bin.server -c /path/to/config.ini
```

### 3️⃣ Verify Configuration

Check your `.env` file:

```bash
cat .env | grep ODOO

# Should show:
# ODOO_BASE_URL=http://localhost:8009
# ODOO_DB=odoo_dev
# ODOO_USERNAME=admin
# ODOO_PASSWORD=admin
```

**If port is different:**
- Update `.env` with correct Odoo URL
- Example: `ODOO_BASE_URL=http://localhost:8069` (if running on port 8069)

### 4️⃣ Verify Odoo API Endpoints Exist

Once Odoo is running, check if endpoints exist:

```bash
# 1. Check if /api/scada/authenticate works
curl -X POST http://localhost:8009/api/scada/authenticate \
  -H "Content-Type: application/json" \
  -d '{
    "db": "odoo_dev",
    "login": "admin",
    "password": "admin"
  }'

# 2. If that works, check /api/scada/equipment-failure endpoint
# (You should authenticate first, then create a failure report)
```

---

## Data Recovery Plan

### When Odoo is back UP:

1. **Scheduler will auto-retry:**
   - Task 5 runs every 5 minutes
   - Will automatically attempt to sync equipment failures to Odoo
   - Check logs for sync status

2. **Manual trigger (if needed):**
   ```bash
   # Run test to verify Odoo sync works
   python test_equipment_failure_odoo_sync.py
   ```

3. **Verify data synced:**
   ```bash
   # Check local DB (should have failures)
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM equipment_failure;"
   
   # Check Odoo DB (should match local DB once sync works)
   psql odoo_dev << EOF
   SELECT COUNT(*) FROM scada_failure_report;
   EOF
   ```

---

## Troubleshooting Checklist

- [ ] Odoo service is running
- [ ] Odoo is accessible on configured port
- [ ] `/api/scada/authenticate` endpoint works
- [ ] `/api/scada/equipment-failure` endpoint exists
- [ ] Equipment master data exists in Odoo (code: PLC01, silo101, etc.)
- [ ] Odoo user has permission to create failure reports
- [ ] Database connection is working (`DATABASE_URL` in .env)

---

## What's Already Working

✓ **PLC Communication:** Data successfully read from PLC
✓ **Local Database:** Equipment failure records stored in PostgreSQL
✓ **Scheduler:** Task 5 runs every 5 minutes and attempts Odoo sync
✓ **Error Handling:** Detailed logging shows what's happening at each step

---

## Expected Behavior Once Odoo is UP

When Odoo service is running and accessible:

### Current Flow:
```
PLC Read (5 min) → Local DB Save → Odoo API Call (automatic)
                                          ↓
                                    ✓ Data synced to Odoo
```

### Logs will show:
```
[TASK 5] Step 1: Reading equipment failure from PLC...
[TASK 5] ✓ Equipment Failure Detected from PLC

[TASK 5] Step 2: Saving to local database
[TASK 5] ✓ Equipment failure saved to DB

[TASK 5] Step 3: Syncing to Odoo via API...
[Odoo Auth] ✓ Successfully authenticated with Odoo
[Odoo API] ✓ Failure report created successfully
[TASK 5] ✓ Odoo sync successful
```

---

## Debug Commands

### Verify Odoo Connection
```bash
# Check if port 8009 is listening
netstat -an | findstr 8009  # Windows
netstat -an | grep 8009      # Linux/Mac

# Test HTTP connectivity
curl -I http://localhost:8009
```

### Check Equipment Failures in Local DB
```bash
psql $DATABASE_URL << EOF
SELECT equipment_code, description, failure_date, source, created_at
FROM scada.equipment_failure
ORDER BY created_at DESC
LIMIT 10;
EOF
```

### Run Debug Test
```bash
python test_equipment_failure_odoo_sync.py
```

The test will show:
- [Test 1] Odoo connection status
- [Test 2] Authentication success/failure
- [Test 3] Equipment master data availability
- [Test 4] Equipment failure API functionality

---

## Next Steps

1. **Start Odoo service** (see Solutions section)
2. **Verify connectivity:**
   ```bash
   curl http://localhost:8009/
   ```
3. **Run debug test:**
   ```bash
   python test_equipment_failure_odoo_sync.py
   ```
4. **Wait for scheduler** (max 5 minutes for Task 5 to retry)
5. **Verify data synced:**
   ```bash
   # Local DB
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM scada.equipment_failure;"
   
   # Odoo DB
   psql odoo_dev -c "SELECT COUNT(*) FROM scada_failure_report;"
   ```

---

## Additional Resources

- Scheduler documentation: `SCHEDULER_CONTROL_GUIDE.md`
- Equipment failure debug guide: `EQUIPMENT_FAILURE_DEBUG_GUIDE.md`
- Full implementation: `EQUIPMENT_FAILURE_FIX_SUMMARY.md`

---

## Summary

| Component | Status | Action |
|-----------|--------|--------|
| PLC Communication | ✓ Working | No action needed |
| Local Database | ✓ Working | No action needed |
| Scheduler Task 5 | ✓ Working | No action needed |
| **Odoo Service** | ✗ **NOT RUNNING** | **Start Odoo** |
| Odoo Endpoints | ⚠️ Unknown | Test after Odoo starts |
| Data Sync | ⏸️ Paused | Will resume when Odoo is up |

**Action Required:** Start Odoo service and verify it's accessible on port 8009.

