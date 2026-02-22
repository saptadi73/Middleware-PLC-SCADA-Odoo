# TASK 5: Manual Material Weighing - Implementation Guide

**Date Created**: 2025-02-22  
**Status**: Ready for Implementation  
**Version**: 1.0

## Overview

TASK 5 is a new scheduler task designed to read manual material weighing data from the PLC and automatically sync consumption data to Odoo in real-time. This enables operators at weigh scale stations to manually enter material consumption data, which is then reflected in Odoo manufacturing orders without requiring manual Odoo entries.

**Key Purpose:**
- Enable manual weighing station operators to input consumption data via PLC HMI
- Automatically sync consumption to Odoo material consumption API
- Real-time material tracking with handshake synchronization

## Memory Architecture

### Memory Allocation (D9000-D9011)

TASK 5 uses a **dedicated memory area separate from Equipment Failure monitoring** to avoid conflicts.

```
Memory Area: D9000-D9011 (12 words total)
───────────────────────────────────────────
D9000       : BATCH (REAL, scale=1)
D9001-D9008 : NO-MO (ASCII, 8 chars, 4 words)
D9009       : NO-Product (REAL, scale=1)
D9010       : Consumption (REAL, scale=100)
D9011       : status_manual_weigh_read (BOOLEAN handshake flag)
───────────────────────────────────────────
```

### Why Separate Memory Area?

Previously, ADDITIONAL_EQUIPMENT_REFERENCE.json proposed using D8000-D8010, which **conflicts** with the existing EQUIPMENT_FAILURE_REFERENCE.json that uses D8000-D8022 for equipment failure monitoring.

Since these serve completely different purposes:
- **Equipment Failure (D8000-D8022)**: Equipment breakdown/error monitoring
- **Manual Weighing (D9000-D9011)**: Operator-entered consumption data

They require separate memory areas and operate independently with their own handshake flags.

## Field Descriptions

| Field | Address | Data Type | Scale | Description | Example |
|-------|---------|-----------|-------|-------------|---------|
| BATCH | D9000 | REAL | 1 | Batch/lot number | 10 |
| NO-MO | D9001-D9008 | ASCII | - | Manufacturing Order ID (8 chars, big-endian) | "WH/MO/00002" |
| NO-Product | D9009 | REAL | 1 | Product Template ID in Odoo | 23 |
| Consumption | D9010 | REAL | 100 | Material consumption quantity (scaled) | 82500 → 825 kg |
| Handshake | D9011 | BOOLEAN | - | Read status flag (0=new, 1=read) | 0 or 1 |

### Scale Factor Details

**Consumption (D9010)** uses scale factor of 100:
- PLC storage: 82500 (integer)
- Actual value: 82500 / 100 = 825 kg
- Reason: PLC stores only integers; scale factor provides decimal precision

## Data Flow

```
┌──────────────────────────────────────┐
│   Weigh Scale Station (HMI Input)    │
│   by Factory Operator                │
└──────────────────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│   PLC Memory Area (D9000-D9010)      │
│   - BATCH (lot number)               │
│   - NO-MO (MO ID)                    │
│   - NO-Product (product ID)          │
│   - Consumption (qty * 100)          │
│   - Operator confirms entry          │
└──────────────────────────────────────┘
            ↓
    TASK 5 Scheduler (2-min interval)
            ↓
┌──────────────────────────────────────┐
│   Step 1: READ from PLC              │
│   - Read D9000-D9010 (12 words)      │
│   - Check D9011 (handshake flag)     │
│   - Skip if D9011=1 (already read)   │
└──────────────────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│   Step 2: VALIDATE Data              │
│   - MO ID not empty                  │
│   - Product ID > 0                   │
│   - Consumption qty > 0              │
│   - MO exists in Odoo                │
│   - Product exists in Odoo           │
└──────────────────────────────────────┘
            ↓
    Validation Passed?
    ├─ NO  → Log error, keep D9011=0 (retry next cycle)
    └─ YES → Continue to Step 3
            ↓
┌──────────────────────────────────────┐
│   Step 3: SYNC to Odoo               │
│   POST /api/scada/material-consumption
│   {                                  │
│     "mo_id": "WH/MO/00002",          │
│     "product_tmpl_id": 23,           │
│     "quantity": 825,  (825 kg)       │
│     "equipment_id": "WEIGH_SCALE_01",│
│     "timestamp": "ISO-8601"          │
│   }                                  │
└──────────────────────────────────────┘
            ↓
    Odoo Sync Success?
    ├─ NO  → Log error, keep D9011=0 (retry next cycle)
    └─ YES → Continue to Step 4
            ↓
┌──────────────────────────────────────┐
│   Step 4: MARK HANDSHAKE             │
│   - Set D9011 = 1 (mark as read)     │
│   - PLC receives signal at next read │
│   - PLC resets D9011 = 0 on new msg  │
└──────────────────────────────────────┘
            ↓
┌──────────────────────────────────────┐
│   Odoo Material Consumption Updated   │
│   Real-time in BoM Line qty_done     │
└──────────────────────────────────────┘
```

## Implementation Status

### ✅ Completed (2025-02-22)

- [x] Create ADDITIONAL_EQUIPMENT_REFERENCE.json (updated with D9000-D9011, not D8000)
- [x] Update konsep_task.txt with TASK 5 definition
- [x] Add D9000-D9011 to MEMORY ARCHITECTURE section
- [x] Document TASK 5 workflow and alur
- [x] Create plc_manual_weighing_service.py
  - [x] read_manual_weighing_data() method
  - [x] validate_weighing_data() method
  - [x] sync_to_odoo() method
  - [x] mark_handshake() method
  - [x] read_and_sync() main workflow
- [x] Update plc_handshake_service.py with D9011 support
  - [x] Add MANUAL_WEIGHING_STATUS_ADDRESS = 9011
  - [x] Add mark_manual_weighing_as_read() method
  - [x] Add check_manual_weighing_status() method
  - [x] Add reset_manual_weighing_status() method

### ⏳ Pending Implementation

- [ ] Add TASK 5 to app/core/scheduler.py
  - [ ] Create read_manual_weighing_task() function
  - [ ] Register with APScheduler (interval: 2 minutes)
  - [ ] Add .env configuration for interval
- [ ] Create database migration for scada_equipment_material (audit log table)
  - [ ] Columns: id, weigh_station_code, mo_id, product_id, consumption_qty, timestamp, sync_status, errors
- [ ] Create test script: test_manual_weighing.py
  - [ ] Test read functionality
  - [ ] Test validation
  - [ ] Test Odoo sync
  - [ ] Test handshake marking
- [ ] Update API documentation
- [ ] Add monitoring/health check for TASK 5
- [ ] Create admin UI for manual weighing audit log (optional)

## Configuration

### Environment Variables (.env)

```env
# TASK 5 - Manual Material Weighing
TASK_MANUAL_WEIGHING_INTERVAL_MINUTES=2
TASK_MANUAL_WEIGHING_ENABLED=true
TASK_MANUAL_WEIGHING_MAX_RETRIES=5
TASK_MANUAL_WEIGHING_RETRY_DELAY_SECONDS=30

# Equipment ID for manual weighing station
WEIGH_SCALE_EQUIPMENT_ID=WEIGH_SCALE_01
```

### Scheduler Configuration

In `scheduler.py`:

```python
# TASK 5: Manual Material Weighing (2-minute interval)
scheduler.add_job(
    func=read_manual_weighing_task,
    trigger="interval",
    minutes=int(getenv("TASK_MANUAL_WEIGHING_INTERVAL_MINUTES", 2)),
    id="task_manual_weighing",
    name="TASK 5: Read and Sync Manual Material Weighing",
    replace_existing=True,
    max_instances=1,
)
```

## API Integration

### Odoo Endpoint: POST /api/scada/material-consumption

```bash
curl -X POST http://localhost:8069/api/scada/material-consumption \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mo_id": "WH/MO/00002",
    "product_tmpl_id": 23,
    "quantity": 825,
    "equipment_id": "WEIGH_SCALE_01",
    "timestamp": "2025-02-22T10:30:00"
  }'
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Material consumption applied to MO moves",
  "mo_id": "WH/MO/00002",
  "applied_qty": 825,
  "move_ids": [456, 457]
}
```

**Response (Error):**
```json
{
  "status": "error",
  "message": "MO not found: WH/MO/00002"
}
```

## Service Architecture

### plc_manual_weighing_service.py

Location: `app/services/plc_manual_weighing_service.py`

**Main Methods:**

1. **read_manual_weighing_data() → Dict**
   - Reads D9000-D9011 from PLC
   - Parses BATCH, MO-ID, Product, Consumption
   - Checks D9011 handshake (skips if already read)
   - Returns dict or None

2. **validate_weighing_data(data) → Tuple[bool, str]**
   - Validates MO ID format
   - Validates product_tmpl_id > 0
   - Validates consumption > 0
   - Returns (is_valid, error_message)

3. **sync_to_odoo(data) → Tuple[bool, str]**
   - POSTs to /api/scada/material-consumption
   - Handles authentication and error responses
   - Returns (sync_success, error_message)

4. **mark_handshake() → bool**
   - Sets D9011 = 1 via handshake service
   - Returns success status

5. **read_and_sync() → bool**
   - Main workflow: Read → Validate → Sync → Mark Handshake
   - Called by scheduler every 2 minutes
   - Returns True on success, False on error

**Usage:**

```python
from app.services.plc_manual_weighing_service import get_manual_weighing_service

service = get_manual_weighing_service()
success = service.read_and_sync()
```

### plc_handshake_service.py Updates

Added methods for D9011 (manual weighing handshake):

1. **mark_manual_weighing_as_read() → bool**
   - Sets D9011 = 1

2. **check_manual_weighing_status() → bool**
   - Reads D9011 status

3. **reset_manual_weighing_status() → bool**
   - Resets D9011 = 0 (for testing)

## Error Handling

### Validation Errors

| Error | Action | Next Cycle |
|-------|--------|-----------|
| MO ID empty | Log error, don't sync | Retry (D9011 = 0) |
| Product not found | Log error, don't sync | Retry (D9011 = 0) |
| Consumption ≤ 0 | Log error, don't sync | Retry (D9011 = 0) |

### Sync Errors

| Error | Action | Next Cycle |
|-------|--------|-----------|
| Network timeout | Log error, don't mark | Retry (D9011 = 0) |
| MO not found in Odoo | Log error, don't mark | Retry (D9011 = 0) |
| Invalid product | Log error, don't mark | Retry (D9011 = 0) |
| Odoo error 500 | Log error, don't mark | Retry (D9011 = 0) |

### Retry Logic

- Keep D9011 = 0 on any failure
- Middleware retries on next 2-min cycle
- Auto-configurable MAX_RETRIES (default: 5)
- Log all errors for troubleshooting

## Testing

### Test Script: test_manual_weighing.py

```python
# 1. Test PLC Read
data = service.read_manual_weighing_data()
assert data["mo_id"] == "WH/MO/00002"
assert data["consumption"] == 825

# 2. Test Validation
valid, error = service.validate_weighing_data(data)
assert valid is True

# 3. Test Odoo Sync
sync_ok, error = service.sync_to_odoo(data)
assert sync_ok is True

# 4. Test Handshake
handshake_ok = service.mark_handshake()
assert handshake_ok is True

# 5. Full workflow
result = service.read_and_sync()
assert result is True
```

### Manual Testing

1. **Simulate PLC Input** (direct memory write or HMI):
   ```
   D9000 = 10 (batch)
   D9001-D9008 = "WH/MO/00001" (MO ID)
   D9009 = 45 (product ID)
   D9010 = 100000 (1000 kg * 100)
   D9011 = 0 (new data)
   ```

2. **Wait for TASK 5 cycle** (2 minutes or trigger manually)

3. **Verify in Odoo**:
   - Check MO material consumption entry created
   - Check quantity_done updated

4. **Verify handshake**:
   - Read D9011, should be 1 if sync successful
   - Next PLC cycle should reset D9011 = 0

## Monitoring & Logging

### Log Locations

- **Application logs**: `logs/app.log`
- **TASK 5 logs**: Search for "[TASK 5]" or "manual weighing"
- **PLC communication**: `logs/fins.log`
- **Odoo sync**: `logs/odoo_api.log`

### Key Log Messages

```
[INFO] Read manual weighing data: {'batch': 10, 'mo_id': 'WH/MO/00002', 'product_tmpl_id': 23, 'consumption': 825.0, ...}
[INFO] Successfully synced weighing data to Odoo for MO: WH/MO/00002
[INFO] Marked D9011 (manual weighing read) as read
[INFO] Manual weighing read and sync cycle completed successfully

[ERROR] Validation failed: NO-MO is empty
[ERROR] Sync failed: Odoo sync failed: MO not found: WH/MO/99999
[ERROR] Error reading manual weighing data from PLC: Connection timeout
```

### Troubleshooting

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| TASK 5 not running | Check scheduler logs | Restart application, check APScheduler config |
| PLC read timeout | Check PLC connection | Verify PLC IP/port, check FINS protocol |
| Odoo sync fails | Check API endpoint | Verify /api/scada/material-consumption exists, check auth |
| D9011 stuck at 1 | Handshake not resetting | Check PLC logic, manually reset via test script |

## Future Enhancements

1. **Multi-station support**: Support multiple weigh scale stations (D9000-D9100 for 10 stations)
2. **Batch import**: Receive multiple consumption entries in single PLC cycle
3. **UI dashboard**: Real-time weighing entry tracking and statistics
4. **Mobile app**: Operator can enter consumption via mobile, sync to PLC
5. **Analytics**: Historical consumption patterns and anomaly detection
6. **Integration**: Direct PLC scale integration (weight sensor automatic input)

## Changelog

### [2025-02-22] - TASK 5 Creation & Implementation Ready

- ✅ Defined TASK 5 for manual material weighing
- ✅ Allocated memory D9000-D9011 (separate from equipment failure D8000-D8022)
- ✅ Updated ADDITIONAL_EQUIPMENT_REFERENCE.json with correct memory addresses
- ✅ Created plc_manual_weighing_service.py with full workflow
- ✅ Updated plc_handshake_service.py with D9011 support
- ✅ Updated konsep_task.txt with TASK 5 documentation
- ✅ Ready for scheduler integration

---

**Next Steps for Implementation:**
1. Add TASK 5 to scheduler.py
2. Create database audit table (scada_equipment_material)
3. Create test script and validate end-to-end
4. Deploy to staging environment
5. Run acceptance testing with weigh scale operators
6. Deploy to production
