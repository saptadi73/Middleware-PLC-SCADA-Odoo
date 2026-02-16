# Equipment Failure Odoo Sync - Complete Documentation Index

**Status:** ✓ FIXED - Debug logging and Odoo sync integration complete  
**Last Updated:** February 15, 2025

---

## 📋 Documentation Files

### 1. **START HERE** - Executive Summary
**File:** `EQUIPMENT_FAILURE_FIX_SUMMARY.md`

Quick overview of:
- What was wrong (equipment failure not syncing to Odoo)
- What was fixed (added Odoo sync in Task 5 + logging)
- How to verify the fix (5-minute test)
- Expected log output
- Configuration needed

**Read this first to understand the issue and solution.**

---

### 2. Quick Diagnosis & Commands
**File:** `EQUIPMENT_FAILURE_QUICK_DEBUG.md`

Copy-paste commands for:
- Checking if server is running
- Testing PLC connection
- Querying databases
- Monitoring logs in real-time
- Common quick fixes

**Read this when you need immediate troubleshooting.**

---

### 3. Complete Troubleshooting Guide
**File:** `EQUIPMENT_FAILURE_DEBUG_GUIDE.md`

Comprehensive guide with:
- System architecture diagram
- Expected success log output
- 6 common issues with detailed solutions
- Manual testing procedures
- Performance metrics
- Configuration reference
- Troubleshooting checklist

**Read this for detailed problem analysis.**

---

### 4. Technical Implementation Details
**File:** `EQUIPMENT_FAILURE_ODOO_SYNC_REPORT.md`

Details about:
- Problem analysis
- Changes made to each file
- Expected log output (success/failure)
- How to test
- Verification checklist
- Debug points in code

**Read this for technical implementation details.**

---

### 5. Code Changes (Before/After)
**File:** `EQUIPMENT_FAILURE_CODE_CHANGES.md`

Side-by-side comparison of:
- What was removed (missing Odoo sync)
- What was added (Odoo sync + logging)
- Exact line numbers and file paths
- Added imports and helper functions

**Read this to see exactly what changed in the code.**

---

## 🔍 Problem Overview

### Issue
Equipment failure data was successfully read from PLC and saved to local database, but was **NOT syncing to Odoo API**.

### Root Cause
Scheduler Task 5 was reading from PLC and saving to local DB, but was missing the step to call Odoo API to sync the data.

### Solution
Added 3-step pipeline with comprehensive logging:
1. **Step 1:** Read from PLC ✓ (was already working)
2. **Step 2:** Save to local DB ✓ (was already working)
3. **Step 3:** Sync to Odoo API ✗→✓ (FIXED - was missing)

---

## ✅ How to Verify the Fix

### Quick Test (5 minutes)
```bash
# Terminal 1: Start server
cd c:\projek\fastapi-scada-odoo
python -m uvicorn app.main:app --reload

# Terminal 2: Write test data to PLC
python test_equipment_failure_write.py

# Watch console output for:
# [TASK 5] ========== START Equipment Failure Monitoring Task ==========
# [TASK 5] ✓ Equipment Failure Detected from PLC
# [TASK 5] ✓ Equipment failure saved to DB
# [TASK 5] ✓ Odoo sync successful
# [TASK 5] ========== END Equipment Failure Monitoring Task ==========

# If you see those messages, the fix is working!
```

### Full Verification
1. Check logs show all 3 steps
2. Query local database: records saved? ✓
3. Query Odoo database: records synced? ✓

See `EQUIPMENT_FAILURE_QUICK_DEBUG.md` for detailed commands.

---

## 📁 Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `app/core/scheduler.py` | Task 5 enhanced with Odoo sync | +130 |
| `app/services/equipment_failure_service.py` | Logging enhanced | +50 |
| **NEW:** `EQUIPMENT_FAILURE_FIX_SUMMARY.md` | Executive summary | 250+ |
| **NEW:** `EQUIPMENT_FAILURE_QUICK_DEBUG.md` | Quick commands | 150+ |
| **NEW:** `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` | Complete guide | 350+ |
| **NEW:** `EQUIPMENT_FAILURE_ODOO_SYNC_REPORT.md` | Technical details | 200+ |
| **NEW:** `EQUIPMENT_FAILURE_CODE_CHANGES.md` | Before/after code | 300+ |
| **NEW:** `EQUIPMENT_FAILURE_DOCUMENTATION_INDEX.md` | This file | - |

---

## 🔧 Configuration Checklist

Before testing, ensure `.env` has:

```
ENABLE_TASK_5_EQUIPMENT_FAILURE=true
EQUIPMENT_FAILURE_INTERVAL_MINUTES=5

# Odoo (for sync)
ODOO_BASE_URL=http://localhost:8009
ODOO_DB=odoo_dev
ODOO_USERNAME=admin
ODOO_PASSWORD=password

# PLC (for read)
PLC_IP=192.168.1.100
PLC_PORT=44818
PLC_TIMEOUT_SEC=5

# Optional (for debug)
LOG_LEVEL=INFO
```

---

## 🎯 Documentation Navigation Guide

**I want to...**

| Goal | Start Here | Then Read |
|------|-----------|-----------|
| Understand the fix | `EQUIPMENT_FAILURE_FIX_SUMMARY.md` | `EQUIPMENT_FAILURE_CODE_CHANGES.md` |
| Test the fix | `EQUIPMENT_FAILURE_QUICK_DEBUG.md` | `EQUIPMENT_FAILURE_FIX_SUMMARY.md` #How to Verify |
| Debug if failing | `EQUIPMENT_FAILURE_QUICK_DEBUG.md` | `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` |
| See expected logs | `EQUIPMENT_FAILURE_ODOO_SYNC_REPORT.md` | `EQUIPMENT_FAILURE_FIX_SUMMARY.md` #Expected Log Output |
| See code changes | `EQUIPMENT_FAILURE_CODE_CHANGES.md` | `EQUIPMENT_FAILURE_ODOO_SYNC_REPORT.md` |
| Understand architecture | `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` | System Architecture Diagram section |
| Troubleshoot specific issue | `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` | 6 common issues section |
| Learn configuration | `EQUIPMENT_FAILURE_QUICK_DEBUG.md` | Environment Variables section |

---

## 🚀 Deployment Steps

1. **Deploy Code**
   - Pull latest changes: `git pull origin main`
   - Start server: `python -m uvicorn app.main:app --reload`

2. **Verify Functionality**
   - Scheduler logs show all 3 steps (see `EQUIPMENT_FAILURE_QUICK_DEBUG.md`)
   - Test with dummy data: `python test_equipment_failure_write.py`

3. **Verify Data Flow**
   - Local DB has records: `psql $DATABASE_URL -c "SELECT * FROM scada.equipment_failure LIMIT 5;"`
   - Odoo DB has records: `psql odoo_db -c "SELECT * FROM scada_failure_report LIMIT 5;"`

4. **Monitor**
   - Watch logs for `[TASK 5]` entries every 5 minutes
   - Check for errors in `[Odoo Auth]` or `[Odoo API]` prefixed logs

---

## 🐛 Common Issues & Quick Solutions

| Issue | Command | Doc Link |
|-------|---------|----------|
| Task 5 not visible in logs | `grep "ENABLE_TASK_5" .env` | Quick Debug |
| No PLC data | `python test_equipment_failure_read.py` | Quick Debug |
| No local DB records | `psql $DATABASE_URL -c "SELECT * FROM scada.equipment_failure"` | Quick Debug |
| Odoo not responding | `curl http://localhost:8009/` | Debug Guide |
| Equipment not found in Odoo | Check Odoo master data | Debug Guide Issue #5 |
| Duplicate detection | `DELETE FROM scada.equipment_failure WHERE equipment_code='silo101'` | Quick Debug |

---

## 📊 Pipeline Flow

```
SCHEDULER TASK 5 (every 5 minutes)
│
├─ Step 1: Read Equipment Failure from PLC ┬─ Success? → Continue
│                                           └─ Fail? → Log error, exit
│
├─ Step 2: Save to Local Database         ┬─ Success? → Continue
│  (with change detection)                └─ Duplicate? → Skip Step 3, exit
│
└─ Step 3: Sync to Odoo API (NEW!) ──────┬─ Success? → Complete ✓
                                         └─ Fail? → Log error, exit
```

---

## 📝 Log Markers

**Look for these prefixes in logs:**

- `[TASK 5]` - Scheduler Task 5 execution steps
- `[Odoo Auth]` - Odoo authentication attempts
- `[Odoo API]` - Odoo API call details

**Success indicators:**
- `✓` - Operation successful
- `[TASK 5] ✓ Odoo sync successful` - Complete success!

**Error indicators:**
- `✗` - Operation failed
- `[Odoo Auth] ✗` - Authentication error
- `[Odoo API] ✗` - API call error

---

## 🔐 Configuration Requirements

### Mandatory
- `ENABLE_TASK_5_EQUIPMENT_FAILURE=true`
- `ODOO_BASE_URL` (Odoo server URL)
- `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`
- `PLC_IP`, `PLC_PORT`

### Optional
- `EQUIPMENT_FAILURE_INTERVAL_MINUTES=5` (default)
- `LOG_LEVEL=INFO` (default, set to DEBUG for verbose)

---

## 📚 Related Documentation

See also:
- `DOCUMENTATION_INDEX.md` - General project documentation
- `TASK_1_QUICK_REFERENCE.txt` - MO sync reference
- `SCHEDULER_CONTROL_GUIDE.md` - Scheduler control guide
- `README.md` - General setup instructions

---

## 🎓 Learning Path

**New to this system?** Follow this order:

1. Read `EQUIPMENT_FAILURE_FIX_SUMMARY.md` - Understand the issue
2. Read Architecture section in `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` - See data flow
3. Run `EQUIPMENT_FAILURE_QUICK_DEBUG.md` commands - Test it yourself
4. Read `EQUIPMENT_FAILURE_CODE_CHANGES.md` - Understand the fix
5. Read `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` common issues - Know how to debug

---

## ❓ FAQ

**Q: Where is equipment failure data read from?**
A: From PLC memory addresses D7710-D7732 via FINS protocol, defined in `EQUIPMENT_FAILURE_REFERENCE.json`

**Q: How often does Task 5 run?**
A: Every 5 minutes by default (configurable via `EQUIPMENT_FAILURE_INTERVAL_MINUTES`)

**Q: What stops duplicate failures from being synced to Odoo?**
A: `save_if_changed()` in `EquipmentFailureDbService` with unique constraint on (equipment_code, failure_date, description)

**Q: Can I see the logs right now?**
A: Yes, start server with `python -m uvicorn app.main:app --reload` and search console for `[TASK 5]`

**Q: What if Odoo is not running?**
A: Logs will show `[Odoo Auth] ✗ HTTP error during authentication`. Local DB still saves, just not synced to Odoo.

**Q: How do I test locally without Odoo?**
A: Equipment failure will still be read from PLC and saved to local DB. Set `ODOO_BASE_URL` to invalid URL to test for proper error handling.

---

## 📞 Support

For issues:
1. Check `EQUIPMENT_FAILURE_QUICK_DEBUG.md` for common quick fixes
2. Review `EQUIPMENT_FAILURE_DEBUG_GUIDE.md` for detailed troubleshooting
3. Search logs for `[TASK 5]`, `[Odoo Auth]`, `[Odoo API]` markers
4. Verify configuration in `.env` file

---

## ✨ Summary

✓ Equipment failure data now flows: **PLC → Local DB → Odoo API**
✓ Complete logging visibility at every step
✓ Comprehensive documentation for all scenarios
✓ No performance impact or breaking changes
✓ Ready for production use

**Status:** Implementation Complete ✓

