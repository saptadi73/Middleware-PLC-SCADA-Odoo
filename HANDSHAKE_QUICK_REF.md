# Handshake Quick Reference

## Memory Addresses

| Area | Data Range | Status Flag | Default | Purpose |
|------|-----------|-------------|---------|---------|
| READ | per-batch READ payload (BATCH_READ_01..10) | D6076/D6176/.../D6976 | 0 | Middleware marks only for completed read batches (status_manufacturing=1) |
| WRITE | D7000-D7075 | D7076 | 0 | PLC readiness flag before middleware writes next batch |
| FAILURE | D8000-D8021 | D8022 | 0 | Middleware marks equipment failure data as read |
| MANUAL WEIGHING | D9000-D9012 | D9013 | 0 | Middleware marks manual weighing data as read |

## Protocol Rules

### READ Area (Production Feedback)
- PLC writes per-batch data and keeps per-batch status_read_data at 0 while pending.
- Middleware reads per-batch data.
- Middleware sets per-batch status_read_data = 1 **only if** status_manufacturing=1 for that batch read.
- PLC resets per-batch status_read_data to 0 when next cycle is ready.

### WRITE Area (Batch Command)
- Middleware checks D7076 before writing.
- If D7076=0: skip write (PLC not ready).
- If D7076=1: write batch command and reset D7076=0.
- PLC sets D7076=1 after reading current command batch.

### Equipment Failure
- PLC writes D8000-D8021, keeps D8022=0 until read.
- Middleware reads and sets D8022=1.
- PLC resets D8022=0 for next event.

### Manual Weighing
- PLC writes D9000-D9012, keeps D9013=0 until read.
- Middleware reads and sets D9013=1 after successful processing.
- PLC resets D9013=0 for next entry.

## Code Usage

```python
from app.services.plc_handshake_service import get_handshake_service
handshake = get_handshake_service()

# WRITE readiness
if handshake.check_write_area_status():
    # safe to write
    ...

# READ completed batch acknowledgement (status_manufacturing=1)
handshake.mark_read_area_as_read(batch_no=1)

# Manual weighing acknowledgement
handshake.mark_manual_weighing_as_read()
```
