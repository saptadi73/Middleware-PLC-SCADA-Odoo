# Handshake Quick Reference

## Memory Addresses

| Area | Data Range | Status Flag | Default | Purpose |
|------|-----------|-------------|---------|---------|
| **READ** | D6001-D6074 | **D6075** | 0 | Middleware marks after reading production data |
| **WRITE** | D7000-D7075 | **D7076** | 0 | PLC marks after reading batch recipe |
| **FAILURE** | D8000-D8021 | **D8022** | 0 | Middleware marks after reading equipment failure |

## Protocol Rules

### READ Area (Production Data)
```
PLC: Writes D6001-D6074 → Sets D6075=0
Middleware: Reads data → Sets D6075=1
PLC: Sees D6075=1 → Resets D6075=0 (next cycle)
```

### WRITE Area (Batch Recipe)
```
Middleware: Checks D7076
  - If D7076=0: SKIP WRITE (PLC busy)
  - If D7076=1: WRITE D7000-D7075 → Set D7076=0
PLC: Reads batch → Sets D7076=1 (ready for next)
```

### Equipment Failure
```
PLC: Writes D8000-D8021 → Sets D8022=0
Middleware: Reads failure → Sets D8022=1
PLC: Sees D8022=1 → Resets D8022=0 (next failure)
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
handshake.mark_read_area_as_read()  # D6075=1

# After reading equipment failure
handshake.mark_equipment_failure_as_read()  # D8022=1
```

### Testing/Reset
```python
# Reset flags for testing
handshake.reset_read_area_status()       # D6075=0
handshake.reset_write_area_status()      # D7076=0
handshake.reset_equipment_failure_status()  # D8022=0
```

## Service Integration

**Auto-Enabled:**
- `plc_sync_service.py` → marks D6075=1 after sync
- `plc_equipment_failure_service.py` → marks D8022=1 after read
- `plc_write_service.py` → checks D7076 before write, resets after

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

⚠️ **Important:** Set D7076=1 initially to allow first batch write:
```python
from app.services.plc_handshake_service import PLCHandshakeService
service = PLCHandshakeService()
service._write_status_flag(7076, 1)
```
