# Handshake Quick Reference

## Memory Addresses

| Area | Data Range | Status Flag | Default | Purpose |
|------|-----------|-------------|---------|---------|
| **READ** | per-batch READ payload (e.g. BATCH_READ_01: D6000-D6075) | **D6076/D6176/.../D6976** | 0 | Middleware marks after reading production data |
| **WRITE** | D7000-D7075 | **D7076** | 0 | PLC marks after reading batch recipe |
| **FAILURE** | D8000-D8021 | **D8022** | 0 | Middleware marks after reading equipment failure |

## Protocol Rules

### READ Area (Production Data)
```
PLC: Writes per-batch READ payload (e.g. BATCH_READ_01: D6000-D6075) â†’ Sets status_read_data per-batch=0
Middleware: Reads data â†’ Sets status_read_data per-batch=1
PLC: Sees status_read_data per-batch=1 â†’ Resets status_read_data per-batch=0 (next cycle)
```

### WRITE Area (Batch Recipe)
```
Middleware: Checks D7076
  - If D7076=0: SKIP WRITE (PLC busy)
  - If D7076=1: WRITE D7000-D7075 â†’ Set D7076=0
PLC: Reads batch â†’ Sets D7076=1 (ready for next)
```

### Equipment Failure
```
PLC: Writes D8000-D8021 â†’ Sets D8022=0
Middleware: Reads failure â†’ Sets D8022=1
PLC: Sees D8022=1 â†’ Resets D8022=0 (next failure)
```

## Code Examples

### Import
```python
from app.services.plc_handshake_service import get_handshake_service
handshake = get_handshake_service()
```

### Check Before Write
```python
if handshake.check_write_area_status():
    # D7076=1, safe to write
    service.write_batch("BATCH01", data)
else:
    # D7076=0, PLC busy
    print("Wait for PLC")
```

### Mark After Read
```python
# After reading production data
handshake.mark_read_area_as_read()  # status_read_data per-batch=1

# After reading equipment failure
handshake.mark_equipment_failure_as_read()  # D8022=1
```

### Testing/Reset
```python
# Reset flags for testing
handshake.reset_read_area_status()       # status_read_data per-batch=0
handshake.reset_write_area_status()      # D7076=0
handshake.reset_equipment_failure_status()  # D8022=0
```

## Service Integration

**Auto-Enabled:**
- `plc_sync_service.py` â†’ marks status_read_data per-batch=1 after sync
- `plc_equipment_failure_service.py` â†’ marks D8022=1 after read
- `plc_write_service.py` â†’ checks D7076 before write, resets after

**Manual Override:**
```python
# Skip handshake check (testing only)
write_service.write_batch("BATCH01", data, skip_handshake_check=True)
```

## Test
```bash
python test_handshake.py
```

## First Deployment

âš ï¸ **Important:** Set D7076=1 initially to allow first batch write:
```python
from app.services.plc_handshake_service import PLCHandshakeService
service = PLCHandshakeService()
service._write_status_flag(7076, 1)
```


