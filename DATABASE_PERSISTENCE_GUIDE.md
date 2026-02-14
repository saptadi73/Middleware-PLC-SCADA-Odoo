# Database Persistence for Odoo Consumption Updates

## Overview

All consumption and mark-done updates to Odoo are now **automatically persisted to the local database** after receiving a successful response from Odoo.

**Key Principle**: 
> Database is only updated AFTER Odoo confirms success. This ensures the local database is always in sync with Odoo state.

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Receive Request (Consumption Data)                        │
│    - MO ID, Equipment, Consumption Values                    │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Send to Odoo API                                           │
│    - /api/scada/mo/update-with-consumptions                 │
│    - or /api/scada/material-consumption (manual)            │
└────────────────┬────────────────────────────────────────────┘
                 ↓
         ┌─────────────┐
         │ Odoo Update │
         └──────┬──────┘
                ↓
      ┌─────────────────────┐
      │ Success Response?   │
      └──┬──────────────┬───┘
         │ Yes          │ No
         ↓              ↓
    ┌────────────┐  ┌──────────────┐
    │ Save to DB │  │ Return Error │
    │ ✓ UPDATE   │  │ (Skip DB)    │
    └────────────┘  └──────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Database Updated                                          │
│    - mo_batch table fields set                              │
│    - last_read_from_plc timestamp updated                   │
│    - Timestamps: ISO format with timezone                   │
└─────────────────────────────────────────────────────────────┘
```

## Updates by Endpoint

### 1. Consumption Update (`/consumption/update`)

**When Odoo responds successfully:**
- **Fields Updated**:
  - `actual_consumption_silo_a` through `actual_consumption_silo_m`
  - `last_read_from_plc` (current timestamp with timezone)

- **SQL** (example):
```sql
UPDATE mo_batch
SET 
  actual_consumption_silo_a = 825.5,
  actual_consumption_silo_b = 600.3,
  last_read_from_plc = NOW() AT TIME ZONE 'UTC'
WHERE mo_id = 'WH/MO/00001';
```

**Response includes**: `"db_saved": true/false`

---

### 2. Mark Done (`/consumption/mark-done`)

**When Odoo responds successfully:**
- **Fields Updated**:
  - `status_manufacturing = true`
  - `actual_weight_quantity_finished_goods = finished_qty`
  - `last_read_from_plc` (current timestamp)

- **SQL** (example):
```sql
UPDATE mo_batch
SET 
  status_manufacturing = true,
  actual_weight_quantity_finished_goods = 950.0,
  last_read_from_plc = NOW() AT TIME ZONE 'UTC'
WHERE mo_id = 'WH/MO/00001';
```

**Response includes**: `"db_saved": true/false`

---

### 3. Batch Process (`/consumption/batch-process`)

**This endpoint performs both updates:**

1. **Consumption Update** (if consumption data > 0):
   - Updates `actual_consumption_silo_*` fields
   - Only if Odoo succeeds

2. **Mark Done** (if status_manufacturing = 1):
   - Updates `status_manufacturing` and `actual_weight_quantity_finished_goods`
   - Only if Odoo succeeds

**Response includes**:
```json
{
  "success": true,
  "consumption": {
    "consumption_updated": true,
    "consumption_details": {
      "db_saved": true
    }
  },
  "mark_done": {
    "mo_marked_done": true,
    "mark_done_details": {
      "db_saved": true
    }
  }
}
```

---

## Implementation Details

### Service Layer

**File**: `app/services/odoo_consumption_service.py`

#### Database Session Support

- Constructor accepts optional `db: Session` parameter:
```python
service = OdooConsumptionService(db=db_session)
```

- If no DB session provided, persistence is skipped (soft-fail)

#### Data Protection Logic

**IMPORTANT: Manufacturing Completed Protection**

Database updates are **protected from overwriting completed manufacturing orders**:

- ✅ **Update allowed**: `status_manufacturing = 0` (False) - Manufacturing in progress
- ❌ **Update blocked**: `status_manufacturing = 1` (True) - Manufacturing already completed

**Why this matters:**
- Prevents PLC read cycles from overwriting final/completed data
- Protects historical records after manufacturing is done
- Ensures data integrity for completed orders

**Implementation in both services:**
- `odoo_consumption_service.py::_save_consumption_to_db()`
- `plc_sync_service.py::_update_batch_if_changed()`

```python
# Check if already completed
current_status_mfg: bool = mo_batch.status_manufacturing
if current_status_mfg:
    logger.info(f"Skip update for MO {mo_id}: status_manufacturing already completed (1)")
    return False

# Proceed with update only if manufacturing is still in progress
```

#### Helper Methods

1. **`_save_consumption_to_db()`**
   - Called after successful consumption update to Odoo
   - **Checks `status_manufacturing` first** - skips if already completed
   - Converts Odoo codes back to SCADA tags
   - Updates `actual_consumption_*` fields
   - Atomic transaction with rollback on error

2. **`_save_mark_done_to_db()`**
   - Called after successful mark-done to Odoo
   - Updates status and finished qty fields
   - Sets `status_manufacturing = True` (locks further updates)
   - Atomic transaction with rollback on error

### API Routes

**File**: `app/api/routes/scada.py`

All three endpoints now:
1. Accept `db: Session = Depends(get_db)` parameter
2. Pass DB session to service: `service = get_consumption_service(db=db)`
3. Include DB save status in response

#### Endpoint Changes

| Endpoint | DB Persistence | Fields Updated |
|----------|--------|---------|
| `/consumption/update` | ✓ After Odoo success | `actual_consumption_silo_*` |
| `/consumption/mark-done` | ✓ After Odoo success | `status_manufacturing`, `actual_weight_quantity_*` |
| `/consumption/batch-process` | ✓ After each Odoo success | Both sets of fields |

---

## Getter Function

**Function**: `get_consumption_service(db: Optional[Session] = None)`

```python
# Without DB (singleton, no persistence)
service = get_consumption_service()

# With DB (new instance, with persistence)
service = get_consumption_service(db=db_session)
```

---

## Error Handling

### Scenario 1: Odoo Fails
```
Odoo Response: Error
↓
Return Error to Client
↓
Database: NOT Updated (good!)
```

### Scenario 2: Odoo Succeeds, DB Fails
```
Odoo Response: Success
↓
Try to Save to DB: Error
↓
Rollback Transaction
↓
Response: db_saved = false (warning in logs)
↓
Data NOT in DB, but IS in Odoo (inconsistency!)
```

**Prevention**: Logging alerts on DB failures so they can be manually resolved.

### Scenario 3: Both Succeed (Normal)
```
Odoo Response: Success
↓
Save to DB: Success
↓
Response: db_saved = true
↓
Data in BOTH Odoo and DB ✓ (synchronized)
```

### Scenario 4: Manufacturing Already Completed (Protection)
```
PLC Read/Consumption Update Request
↓
Check Database: status_manufacturing = 1 (True)
↓
Skip Update (Protection Triggered)
↓
Log: "Skip update for MO {mo_id}: status_manufacturing already completed (1)"
↓
Return: db_saved = false (no changes made)
↓
Data Preserved ✓ (completed order protected)
```

**Why this scenario matters:**
- PLC may continue reading memory after MO is completed
- Scheduled sync jobs might attempt to update completed records
- Protection ensures final/historical data is never overwritten
- Maintains data integrity for reporting and audit trails

---

## Database Model Fields

### TableSmoBatch

**Consumption Fields** (per silo):
```python
actual_consumption_silo_a: float  # Updated by consumption endpoint
actual_consumption_silo_b: float
actual_consumption_silo_c: float
...
actual_consumption_silo_m: float
```

**Status Fields**:
```python
status_manufacturing: bool                           # Updated by mark-done
actual_weight_quantity_finished_goods: Numeric       # Updated by mark-done
```

**Tracking**:
```python
last_read_from_plc: DateTime(timezone=True)  # Updated by all endpoints
```

---

## Usage Examples

### Example 1: Manual Update per Component

**Request**:
```bash
curl -X POST http://localhost:8000/api/scada/consumption/update \
  -H "Content-Type: application/json" \
  -d '{
    "mo_id": "WH/MO/00001",
    "equipment_id": "PLC01",
    "consumption_data": {
      "silo_a": 825.5,
      "silo_b": 600.3
    }
  }'
```

**Response (Success)**:
```json
{
  "status": "success",
  "message": "Consumption updated successfully",
  "data": {
    "success": true,
    "mo_id": "WH/MO/00001",
    "db_saved": true,           ← Database was updated
    "consumed_items": ["silo_a", "silo_b"],
    ...
  }
}
```

**Database State After**:
```sql
mo_batch WHERE mo_id = 'WH/MO/00001':
- actual_consumption_silo_a = 825.5
- actual_consumption_silo_b = 600.3
- last_read_from_plc = 2026-02-13 14:30:45.123456+00:00
```

---

### Example 2: Batch Process with Auto Mark-Done

**Request**:
```bash
curl -X POST http://localhost:8000/api/scada/consumption/batch-process \
  -H "Content-Type: application/json" \
  -d '{
    "mo_id": "WH/MO/00001",
    "equipment_id": "PLC01",
    "batch_data": {
      "consumption_silo_a": 825.5,
      "consumption_silo_b": 600.3,
      "status_manufacturing": 1,
      "actual_weight_quantity_finished_goods": 1000
    }
  }'
```

**Response (Success)**:
```json
{
  "status": "success",
  "message": "Batch consumption processed successfully",
  "data": {
    "success": true,
    "mo_id": "WH/MO/00001",
    "consumption": {
      "consumption_updated": true,
      "consumption_details": {
        "success": true,
        "db_saved": true          ← Consumption saved to DB
      }
    },
    "mark_done": {
      "mo_marked_done": true,
      "mark_done_details": {
        "success": true,
        "db_saved": true          ← Mark-done saved to DB
      }
    }
  }
}
```

**Database State After**:
```sql
mo_batch WHERE mo_id = 'WH/MO/00001':
- actual_consumption_silo_a = 825.5
- actual_consumption_silo_b = 600.3
- status_manufacturing = true
- actual_weight_quantity_finished_goods = 1000
- last_read_from_plc = 2026-02-13 14:30:45.123456+00:00
```

---

## Logging

### Info Level (Success)
```
✓ Saved 2 consumption entries to DB for MO WH/MO/00001
✓ Saved mark-done to DB for MO WH/MO/00001 (finished_qty=1000)
```

### Warning Level (DB Not Available)
```
Database session not available, skipping DB save
MO batch WH/MO/00001 not found in database
```

### Error Level (DB Failure)
```
Error saving consumption to database for WH/MO/00001: [error details]
Error saving mark-done to database for WH/MO/00001: [error details]
```

---

## Testing

### Test without DB Persistence
```python
from app.services.odoo_consumption_service import get_consumption_service

# No DB → No persistence
service = get_consumption_service()
result = await service.update_consumption_with_odoo_codes(...)
# DB: NOT updated (soft-fail, no error)
```

### Test with DB Persistence
```python
from app.db.session import SessionLocal
from app.services.odoo_consumption_service import get_consumption_service

db = SessionLocal()
try:
    # With DB → Persistence enabled
    service = get_consumption_service(db=db)
    result = await service.update_consumption_with_odoo_codes(...)
    # DB: Updated (if Odoo succeeds)
finally:
    db.close()
```

---

## Rollout Checklist

- ✓ Database session support added to service constructor
- ✓ Consumption save method implemented (`_save_consumption_to_db`)
- ✓ Mark-done save method implemented (`_save_mark_done_to_db`)
- ✓ All three API endpoints updated to pass DB session
- ✓ Getter function updated to support optional DB session
- ✓ Response includes `db_saved` indicator
- ✓ Error handling with transaction rollback
- ✓ Timezone-aware timestamp updates
- ✓ Conversion from Odoo codes back to SCADA tags
- ✓ Logging for monitoring

---

## Verification

### Verify API is Working
```bash
# Check consumption was saved to DB
SELECT actual_consumption_silo_a, actual_consumption_silo_b, last_read_from_plc 
FROM mo_batch 
WHERE mo_id = 'WH/MO/00001';
```

### Expected Result
```
actual_consumption_silo_a | actual_consumption_silo_b | last_read_from_plc
───────────────────────────┼───────────────────────────┼────────────────────────────
825.5                      | 600.3                     | 2026-02-13 14:30:45.123456+00:00
```

### Check Mark-Done Status
```bash
SELECT status_manufacturing, actual_weight_quantity_finished_goods, last_read_from_plc
FROM mo_batch 
WHERE mo_id = 'WH/MO/00001' AND status_manufacturing = true;
```

---

## Summary

| Feature | Status |
|---------|--------|
| Database Persistence | ✓ Implemented |
| Atomic Transactions | ✓ Implemented |
| Soft-Fail without DB | ✓ Implemented |
| Response Indicator | ✓ `db_saved` flag |
| Timezone Aware | ✓ UTC with timezone |
| Error Rollback | ✓ On failure |
| Logging | ✓ Info/Warning/Error |
| Test Scripts | ✓ Use DB session |

---

## Next Steps

1. ✓ Database persistence implemented
2. ✓ All endpoints updated
3. Run test script to verify: `python test_plc_read_update_odoo.py`
4. Deploy to production with monitoring
5. Check logs for any DB failures

---

## References

- [Odoo Consumption Service](app/services/odoo_consumption_service.py)
- [SCADA API Routes](app/api/routes/scada.py)
- [Database Model](app/models/tablesmo_batch.py)
- [Test Guide](PLC_READ_TEST_GUIDE.md)
