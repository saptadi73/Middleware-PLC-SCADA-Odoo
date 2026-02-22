# Handshake Implementation Summary - status_read_data

**Date:** February 21, 2026  
**Feature:** PLC â†” Middleware Handshaking via status_read_data flags

---

## Overview

Implemented bidirectional handshaking mechanism between Middleware and PLC to prevent data overwrites and ensure proper data flow synchronization. Uses dedicated status_read_data boolean flags in three memory areas.

---

## Memory Addresses

### 1. READ Area (D6001-D6077)
- **Data Range:** per-batch READ payload (e.g. BATCH_READ_01: D6000-D6075) (batch consumption data)
- **Status Flag:** **D6076/D6176/.../D6976** (status_read_data per-batch)
- **Protocol:**
  - PLC writes production data â†’ per-batch READ payload (e.g. BATCH_READ_01: D6000-D6075)
  - Middleware reads data â†’ sets status_read_data per-batch = 1
  - PLC sees status_read_data per-batch=1 â†’ knows Middleware processed data
  - PLC resets status_read_data per-batch=0 when ready with next cycle

### 2. WRITE/BATCH Area (D7000-D7976)
- **Data Range:** D7000-D7075 (batch recipe for manufacturing)
- **Status Flag:** **D7076** (status_read_data)
- **Protocol:**
  - Middleware checks D7076 before writing
  - If D7076=0: PLC hasn't read yet â†’ **SKIP WRITE** (prevent overwrite)
  - If D7076=1: PLC has read â†’ safe to write
  - After writing, Middleware sets D7076=0
  - PLC reads batch data â†’ sets D7076=1 when done

### 3. Equipment Failure Area (D8000-D8022)
- **Data Range:** D8000-D8021 (failure details + timestamp)
- **Status Flag:** **D8022** (status_read_data)
- **Protocol:**
  - PLC writes failure data â†’ D8000-D8021
  - Middleware reads failure â†’ sets D8022 = 1
  - PLC sees D8022=1 â†’ knows failure was logged
  - PLC resets D8022=0 when ready with next failure

---

## Files Changed

### 1. Reference Files Fixed âœ…

**READ_DATA_PLC_MAPPING.json:**
- Fixed LQ115 entry numbers (31â†’33, 32â†’34)
- Fixed LQ115 ID memory (D6069 â†’ D6070)
- Fixed LQ115 ID value (114 â†’ 115)
- Fixed LQ115 Consumption memory (D6069-6070 â†’ D6071-6072)
- Added status_read_data entries per-batch (No 39: D6076, D6176, ..., D6976)

**EQUIPMENT_FAILURE_REFERENCE.json:**
- Added status_read_data entry (No 9, D8022)
- Fixed metadata format (length field)

**read_data_plc_input.csv:**
- Added line 38: status_read_data at D6077 with default value 0

**equipment_failure_input.csv:**
- Added line 9: status_read_data at D8022 with default value 0

### 2. New Service Created âœ…

**app/services/plc_handshake_service.py** (NEW FILE - 300+ lines)

**Key Methods:**
```python
# READ Area (per-batch status_read_data)
check_read_area_status() -> bool           # Check if Middleware has read
mark_read_area_as_read() -> bool           # Set status_read_data per-batch = 1 after reading
reset_read_area_status() -> bool           # Set status_read_data per-batch = 0 (testing/PLC simulation)

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

### 3. Service Updates âœ…

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
  - **AFTER SUCCESSFUL SYNC:** Calls `mark_read_area_as_read()` (sets status_read_data per-batch=1)
  - Marks data as read even if no changes detected (processed it anyway)

**app/services/plc_equipment_failure_service.py:**
- Added import: `from app.services.plc_handshake_service import get_handshake_service`
- Updated `read_equipment_failure_data()` method:
  - **AFTER SUCCESSFUL READ:** Calls `mark_equipment_failure_as_read()` (sets D8022=1)

### 4. Test Script Created âœ…

**test_handshake.py** (NEW FILE - 240+ lines)

**Test Coverage:**
1. **READ Area Test (per-batch status_read_data):**
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

### 5. Documentation Updated âœ…

**TEST_SCRIPTS_REVIEW.md:**
- Updated memory address ranges
- Added handshake logic section
- Updated summary table

---

## Handshake Flow Diagrams

### READ Area Flow (Production Data)
```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                           â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚     PLC     â”‚                           â”‚ Middleware  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                           â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
      â”‚                                          â”‚
      â”‚ 1. Write production data (per-batch READ payload (e.g. BATCH_READ_01: D6000-D6075))  â”‚
      â”‚â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€>â”‚
      â”‚                                          â”‚
      â”‚ 2. Set status_read_data per-batch = 0 (ready for Middleware) â”‚
      â”‚                                          â”‚
      â”‚                        3. Read data      â”‚
      â”‚<â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
      â”‚                                          â”‚
      â”‚                   4. Set status_read_data per-batch = 1       â”‚
      â”‚<â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
      â”‚                                          â”‚
      â”‚ 5. See status_read_data per-batch=1 (Middleware processed)    â”‚
      â”‚                                          â”‚
      â”‚ 6. Prepare next cycle, reset status_read_data per-batch = 0  â”‚
      â”‚                                          â”‚
      â–¼                                          â–¼
```

### WRITE Area Flow (Batch Recipe)
```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                           â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚     PLC     â”‚                           â”‚ Middleware  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                           â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
      â”‚                                          â”‚
      â”‚              1. Check D7076 status      â”‚
      â”‚<â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
      â”‚                                          â”‚
      â”‚              2. D7076 = 0?               â”‚
      â”‚              (PLC not ready)             â”‚
      â”‚â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€>â”‚
      â”‚                                          â”‚
      â”‚          3. SKIP WRITE, wait for PLC     â”‚
      â”‚                                          â”‚
      â”‚ 4. Finish reading batch                  â”‚
      â”‚    Set D7076 = 1 (ready)                 â”‚
      â”‚                                          â”‚
      â”‚              5. Check D7076 again        â”‚
      â”‚<â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
      â”‚                                          â”‚
      â”‚              6. D7076 = 1?               â”‚
      â”‚              (PLC ready!)                â”‚
      â”‚â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€>â”‚
      â”‚                                          â”‚
      â”‚       7. Write new batch (D7000-D7075)   â”‚
      â”‚<â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
      â”‚                                          â”‚
      â”‚              8. Set D7076 = 0            â”‚
      â”‚<â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
      â”‚                                          â”‚
      â”‚ 9. Read batch data...                    â”‚
      â”‚                                          â”‚
      â–¼                                          â–¼
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
    print("âœ“ Batch written successfully")
    
except RuntimeError as e:
    # PLC hasn't read previous batch yet (D7076=0)
    print(f"âš  Cannot write: {e}")
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
    print("âœ“ PLC ready, safe to write")
    # Write batch...
    # After write, reset flag
    handshake.reset_write_area_status()
else:
    print("âš  PLC busy, wait...")
```

### Example 4: Sync with Auto-Handshake

```python
from app.services.plc_sync_service import PLCSyncService

service = PLCSyncService()

# Sync automatically marks READ area as read
result = await service.sync_from_plc()

if result['success'] and result['updated']:
    print(f"âœ“ Synced MO {result['mo_id']}")
    # status_read_data per-batch automatically set to 1
```

---

## Testing Checklist

Before deployment, verify:

- [ ] **Reference Files:**
  - [ ] READ_DATA_PLC_MAPPING.json has status_read_data per-batch (D6076, D6176, ..., D6976)
  - [ ] EQUIPMENT_FAILURE_REFERENCE.json has status_read_data at D8022
  - [ ] MASTER_BATCH_REFERENCE.json has status_read_data at D7076 (all 10 batches)
  - [ ] CSV files updated with status_read_data entries

- [ ] **Service Tests:**
  - [ ] Run `python test_handshake.py` - all tests pass
  - [ ] Verify WRITE service rejects write when D7076=0
  - [ ] Verify WRITE service proceeds when D7076=1
  - [ ] Verify SYNC service marks status_read_data per-batch=1 after read
  - [ ] Verify Equipment Failure service marks D8022=1 after read

- [ ] **Integration Tests:**
  - [ ] Test complete write â†’ read â†’ sync cycle
  - [ ] Test batch write rejection when PLC busy
  - [ ] Test equipment failure read and handshake

- [ ] **Database:**
  - [ ] All migrations applied (`alembic upgrade head`)
  - [ ] Tables have LQ114/LQ115 columns

---

## Default Values

All status_read_data flags **default to 0** (not read):
- status_read_data per-batch = 0 (Middleware hasn't read yet)
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

**Cause:** status_read_data per-batch not being reset by PLC

**Solution:**
- Verify PLC logic resets status_read_data per-batch=0 after seeing it as 1
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

âœ… **Implemented:**
- Handshake service with 3 memory areas
- Write protection logic (prevents overwrite)
- Auto-marking after read operations
- Comprehensive test script
- Fixed all typos in reference files
- Updated all CSV input files

âœ… **Ready for Testing:**
- Run `python test_handshake.py`
- Integration testing with PLC simulator
- End-to-end workflow validation

âœ… **Benefits:**
- No data overwrites
- Proper synchronization
- Clear PLC â†” Middleware communication
- Easier debugging with status flags


