# Handshake Implementation Summary - status_read_data

**Date:** February 21, 2026  
**Feature:** PLC ↔ Middleware Handshaking via status_read_data flags

---

## Overview

Implemented bidirectional handshaking mechanism between Middleware and PLC to prevent data overwrites and ensure proper data flow synchronization. Uses dedicated status_read_data boolean flags in three memory areas.

---

## Memory Addresses

### 1. READ Area (D6001-D6077)
- **Data Range:** D6001-D6074 (batch consumption data)
- **Status Flag:** **D6075** (status_read_data)
- **Protocol:**
  - PLC writes production data → D6001-D6074
  - Middleware reads data → sets D6075 = 1
  - PLC sees D6075=1 → knows Middleware processed data
  - PLC resets D6075=0 when ready with next cycle

### 2. WRITE/BATCH Area (D7000-D7076)
- **Data Range:** D7000-D7075 (batch recipe for manufacturing)
- **Status Flag:** **D7076** (status_read_data)
- **Protocol:**
  - Middleware checks D7076 before writing
  - If D7076=0: PLC hasn't read yet → **SKIP WRITE** (prevent overwrite)
  - If D7076=1: PLC has read → safe to write
  - After writing, Middleware sets D7076=0
  - PLC reads batch data → sets D7076=1 when done

### 3. Equipment Failure Area (D8000-D8022)
- **Data Range:** D8000-D8021 (failure details + timestamp)
- **Status Flag:** **D8022** (status_read_data)
- **Protocol:**
  - PLC writes failure data → D8000-D8021
  - Middleware reads failure → sets D8022 = 1
  - PLC sees D8022=1 → knows failure was logged
  - PLC resets D8022=0 when ready with next failure

---

## Files Changed

### 1. Reference Files Fixed ✅

**READ_DATA_PLC_MAPPING.json:**
- Fixed LQ115 entry numbers (31→33, 32→34)
- Fixed LQ115 ID memory (D6069 → D6070)
- Fixed LQ115 ID value (114 → 115)
- Fixed LQ115 Consumption memory (D6069-6070 → D6071-6072)
- Added status_read_data entry (No 38, D6075)

**EQUIPMENT_FAILURE_REFERENCE.json:**
- Added status_read_data entry (No 9, D8022)
- Fixed metadata format (length field)

**read_data_plc_input.csv:**
- Added line 38: status_read_data at D6077 with default value 0

**equipment_failure_input.csv:**
- Added line 9: status_read_data at D8022 with default value 0

### 2. New Service Created ✅

**app/services/plc_handshake_service.py** (NEW FILE - 300+ lines)

**Key Methods:**
```python
# READ Area (D6075)
check_read_area_status() -> bool           # Check if Middleware has read
mark_read_area_as_read() -> bool           # Set D6075 = 1 after reading
reset_read_area_status() -> bool           # Set D6075 = 0 (testing/PLC simulation)

# WRITE Area (D7076)
check_write_area_status() -> bool          # Check if PLC has read (safe to write?)
reset_write_area_status() -> bool          # Set D7076 = 0 after writing

# Equipment Failure (D8022)
check_equipment_failure_status() -> bool   # Check if Middleware has read
mark_equipment_failure_as_read() -> bool   # Set D8022 = 1 after reading
reset_equipment_failure_status() -> bool   # Set D8022 = 0 (testing)
```

**Singleton Pattern:**
```python
from app.services.plc_handshake_service import get_handshake_service

handshake = get_handshake_service()
```

### 3. Service Updates ✅

**app/services/plc_write_service.py:**
- Added import: `from app.services.plc_handshake_service import get_handshake_service`
- Updated `write_batch()` method:
  - New parameter: `skip_handshake_check: bool = False`
  - **BEFORE WRITE:** Checks D7076 status
  - If D7076=0: Raises `RuntimeError` and skips write
  - If D7076=1: Proceeds with write
  - **AFTER WRITE:** Resets D7076 = 0
- Exception raised if PLC not ready prevents data overwrite

**app/services/plc_sync_service.py:**
- Added import: `from app.services.plc_handshake_service import get_handshake_service`
- Updated `sync_from_plc()` method:
  - **AFTER SUCCESSFUL SYNC:** Calls `mark_read_area_as_read()` (sets D6075=1)
  - Marks data as read even if no changes detected (processed it anyway)

**app/services/plc_equipment_failure_service.py:**
- Added import: `from app.services.plc_handshake_service import get_handshake_service`
- Updated `read_equipment_failure_data()` method:
  - **AFTER SUCCESSFUL READ:** Calls `mark_equipment_failure_as_read()` (sets D8022=1)

### 4. Test Script Created ✅

**test_handshake.py** (NEW FILE - 240+ lines)

**Test Coverage:**
1. **READ Area Test (D6075):**
   - Check initial status
   - Reset to 0 (simulate PLC ready)
   - Mark as read (simulate Middleware read)
   - Verify flag changed to 1

2. **WRITE Area Test (D7076):**
   - Check initial status
   - Set to 1 (simulate PLC finished reading)
   - Verify safe to write
   - Reset to 0 (simulate Middleware write)
   - Verify flag changed to 0

3. **Equipment Failure Test (D8022):**
   - Reset to 0 (simulate PLC ready)
   - Mark as read (simulate Middleware read)
   - Verify flag changed to 1

**Usage:**
```bash
python test_handshake.py
```

### 5. Documentation Updated ✅

**TEST_SCRIPTS_REVIEW.md:**
- Updated memory address ranges
- Added handshake logic section
- Updated summary table

---

## Handshake Flow Diagrams

### READ Area Flow (Production Data)
```
┌─────────────┐                           ┌─────────────┐
│     PLC     │                           │ Middleware  │
└─────────────┘                           └─────────────┘
      │                                          │
      │ 1. Write production data (D6001-D6074)  │
      │─────────────────────────────────────────>│
      │                                          │
      │ 2. Set D6075 = 0 (ready for Middleware) │
      │                                          │
      │                        3. Read data      │
      │<─────────────────────────────────────────│
      │                                          │
      │                   4. Set D6075 = 1       │
      │<─────────────────────────────────────────│
      │                                          │
      │ 5. See D6075=1 (Middleware processed)    │
      │                                          │
      │ 6. Prepare next cycle, reset D6075 = 0  │
      │                                          │
      ▼                                          ▼
```

### WRITE Area Flow (Batch Recipe)
```
┌─────────────┐                           ┌─────────────┐
│     PLC     │                           │ Middleware  │
└─────────────┘                           └─────────────┘
      │                                          │
      │              1. Check D7076 status      │
      │<─────────────────────────────────────────│
      │                                          │
      │              2. D7076 = 0?               │
      │              (PLC not ready)             │
      │─────────────────────────────────────────>│
      │                                          │
      │          3. SKIP WRITE, wait for PLC     │
      │                                          │
      │ 4. Finish reading batch                  │
      │    Set D7076 = 1 (ready)                 │
      │                                          │
      │              5. Check D7076 again        │
      │<─────────────────────────────────────────│
      │                                          │
      │              6. D7076 = 1?               │
      │              (PLC ready!)                │
      │─────────────────────────────────────────>│
      │                                          │
      │       7. Write new batch (D7000-D7075)   │
      │<─────────────────────────────────────────│
      │                                          │
      │              8. Set D7076 = 0            │
      │<─────────────────────────────────────────│
      │                                          │
      │ 9. Read batch data...                    │
      │                                          │
      ▼                                          ▼
```

---

## API Usage Examples

### Example 1: Write Batch with Handshake Check

```python
from app.services.plc_write_service import PLCWriteService

service = PLCWriteService()

try:
    # Handshake check automatically performed
    service.write_batch("BATCH01", {
        "BATCH": 1,
        "NO-MO": "WH/MO/00010",
        "finished_goods": "Product ABC",
        "Quantity Goods_id": 5000,
        # ... other fields
    })
    print("✓ Batch written successfully")
    
except RuntimeError as e:
    # PLC hasn't read previous batch yet (D7076=0)
    print(f"⚠ Cannot write: {e}")
    print("Wait for PLC to finish reading previous batch")
```

### Example 2: Skip Handshake Check (Testing Only)

```python
# For testing purposes, bypass handshake check
service.write_batch("BATCH01", batch_data, skip_handshake_check=True)
```

### Example 3: Manual Handshake Control

```python
from app.services.plc_handshake_service import get_handshake_service

handshake = get_handshake_service()

# Check if PLC is ready for new batch
if handshake.check_write_area_status():
    print("✓ PLC ready, safe to write")
    # Write batch...
    # After write, reset flag
    handshake.reset_write_area_status()
else:
    print("⚠ PLC busy, wait...")
```

### Example 4: Sync with Auto-Handshake

```python
from app.services.plc_sync_service import PLCSyncService

service = PLCSyncService()

# Sync automatically marks READ area as read
result = await service.sync_from_plc()

if result['success'] and result['updated']:
    print(f"✓ Synced MO {result['mo_id']}")
    # D6075 automatically set to 1
```

---

## Testing Checklist

Before deployment, verify:

- [ ] **Reference Files:**
  - [ ] READ_DATA_PLC_MAPPING.json has status_read_data at D6075
  - [ ] EQUIPMENT_FAILURE_REFERENCE.json has status_read_data at D8022
  - [ ] MASTER_BATCH_REFERENCE.json has status_read_data at D7076 (all 10 batches)
  - [ ] CSV files updated with status_read_data entries

- [ ] **Service Tests:**
  - [ ] Run `python test_handshake.py` - all tests pass
  - [ ] Verify WRITE service rejects write when D7076=0
  - [ ] Verify WRITE service proceeds when D7076=1
  - [ ] Verify SYNC service marks D6075=1 after read
  - [ ] Verify Equipment Failure service marks D8022=1 after read

- [ ] **Integration Tests:**
  - [ ] Test complete write → read → sync cycle
  - [ ] Test batch write rejection when PLC busy
  - [ ] Test equipment failure read and handshake

- [ ] **Database:**
  - [ ] All migrations applied (`alembic upgrade head`)
  - [ ] Tables have LQ114/LQ115 columns

---

## Default Values

All status_read_data flags **default to 0** (not read):
- D6075 = 0 (Middleware hasn't read yet)
- D7076 = 0 (PLC hasn't read yet - **Middleware cannot write**)
- D8022 = 0 (Middleware hasn't read equipment failure yet)

**Important:** On first deployment, D7076 should be manually set to 1 by PLC or test script to allow first batch write.

---

## Troubleshooting

### Issue: "Cannot write BATCH: PLC handshake not ready (D7076=0)"

**Cause:** PLC busy reading previous batch

**Solution:**
1. Wait for PLC to finish reading
2. PLC will set D7076=1 when ready
3. Or manually set D7076=1 for testing:
   ```python
   from app.services.plc_handshake_service import PLCHandshakeService
   service = PLCHandshakeService()
   service._write_status_flag(7076, 1)
   ```

### Issue: Constant re-reading of same data

**Cause:** D6075 not being reset by PLC

**Solution:**
- Verify PLC logic resets D6075=0 after seeing it as 1
- For testing, manually reset:
  ```python
  handshake.reset_read_area_status()
  ```

### Issue: Status flags not changing

**Cause:** PLC connection issues or wrong memory addresses

**Solution:**
1. Verify PLC IP/Port in settings
2. Check memory addresses match reference files
3. Test with `test_handshake.py`

---

## Summary

✅ **Implemented:**
- Handshake service with 3 memory areas
- Write protection logic (prevents overwrite)
- Auto-marking after read operations
- Comprehensive test script
- Fixed all typos in reference files
- Updated all CSV input files

✅ **Ready for Testing:**
- Run `python test_handshake.py`
- Integration testing with PLC simulator
- End-to-end workflow validation

✅ **Benefits:**
- No data overwrites
- Proper synchronization
- Clear PLC ↔ Middleware communication
- Easier debugging with status flags
