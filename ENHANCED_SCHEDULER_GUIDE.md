# Enhanced Scheduler & MO History Implementation Guide

## Overview

Implementasi lengkap dari konsep SCADA-PLC-Odoo integration dengan enhanced scheduler yang menjalankan multiple tasks secara periodik.

## Important: Naming Convention

**Field Naming Consistency:**

| Context | Field Name | Example |
|---------|-----------|---------|
| **Database** (mo_batch table) | `actual_consumption_silo_{letter}` | `actual_consumption_silo_a` |
| **API Payload** (process_batch_consumption) | `consumption_silo_{letter}` | `consumption_silo_a` |

**Why the difference?**
- Database uses `actual_consumption_*` to clearly indicate this is **actual data from PLC** (vs planned consumption)
- API payload uses `consumption_*` for **generic/reusable contract** that works with both actual and planned data
- Task 3 and manual retry endpoints automatically **map between these naming conventions**

**Mapping Example:**
```python
# From database (actual from PLC)
batch.actual_consumption_silo_a = 825.5

# To API payload (for Odoo)
batch_data = {
    "consumption_silo_a": 825.5  # mapped from actual_consumption_silo_a
}
```

## Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    ENHANCED SCHEDULER                            â”‚
â”‚                  (4 Periodic Background Tasks)                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚              â”‚              â”‚              â”‚
         â–¼              â–¼              â–¼              â–¼
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”
    â”‚ TASK 1 â”‚    â”‚ TASK 2 â”‚    â”‚ TASK 3 â”‚    â”‚ TASK 4 â”‚
    â”‚        â”‚    â”‚        â”‚    â”‚        â”‚    â”‚        â”‚
    â”‚ Sync   â”‚    â”‚ Read   â”‚    â”‚Process â”‚    â”‚Monitor â”‚
    â”‚ MO     â”‚    â”‚ PLC    â”‚    â”‚Complet.â”‚    â”‚ Health â”‚
    â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## Task Details

### Task 1: Auto-Sync MO dari Odoo (60 minutes interval)

**Purpose**: Fetch Manufacturing Orders dari Odoo dan populate mo_batch table

**Logic**:
1. Check if mo_batch table is empty
2. If empty: Fetch MO list from Odoo (max 10 batches by default)
3. If not empty: Skip (wait for PLC to complete processing)
4. Insert fetched MOs to mo_batch table

**Configuration**: Interval controlled by `SYNC_INTERVAL_MINUTES` in .env

**When it runs**: 
- Startup + every 60 minutes (default)
- Can be triggered manually via `/admin/trigger-sync`

---

### Task 2: PLC Read Sync (5 minutes interval)

**Purpose**: Read actual data from PLC memory and update mo_batch

**Logic (Optimized)**:
1. Check if there are any active batches (status_manufacturing = 0)
2. Read PLC memory **once per cycle** (PLC memory contains only one active MO at a time)
3. Update the corresponding mo_batch record with:
   - actual_consumption_silo_* fields
   - status_manufacturing and status_operation
   - actual_weight_quantity_finished_goods
   - last_read_from_plc timestamp
4. **Protection**: Skip update if status_manufacturing already = 1 (handled internally by sync_from_plc)

**Key Optimization**: 
- No need to loop per batch because PLC only processes one MO at a time
- Only one PLC read per cycle (efficient!)
- Automatically matches the MO_ID from PLC to the batch in database

**Configuration**: Fixed 5 minutes interval

**When it runs**:
- Every 5 minutes
- Can be triggered manually via `/admin/manual/trigger-plc-sync`

**Data Protection**:
- âœ… Update only if `status_manufacturing = 0` (in progress)
- âŒ Skip if `status_manufacturing = 1` (completed)
- Prevents overwriting final data

---

### Task 3: Process Completed Batches (3 minutes interval)

**Purpose**: Process batches yang sudah selesai dan update ke Odoo

**Logic**:
1. Find all completed batches (status_manufacturing = 1)
2. For each completed batch:
   - Prepare consumption data dari actual_consumption_silo_* fields
   - **Map field names**: `actual_consumption_silo_{letter}` (DB) â†’ `consumption_silo_{letter}` (API)
   - Update consumption to Odoo via `/api/scada/mo/update-with-consumptions`
   - Mark MO as done in Odoo
   - Move batch data to mo_histories table
   - Delete from mo_batch table
3. Log success/failure for each batch

**Field Name Mapping**:
- Database field: `actual_consumption_silo_a` (actual data from PLC)
- API payload field: `consumption_silo_a` (contract for process_batch_consumption)
- This ensures consistent naming convention across the system

**Configuration**: Fixed 3 minutes interval

**When it runs**:
- Every 3 minutes
- Can be triggered manually via `/admin/manual/trigger-process-completed`

**Error Handling**:
- If Odoo update fails: Keep batch in mo_batch table
- Batch can be retried manually via `/admin/manual/retry-push-odoo/{mo_id}`

---

### Task 4: Batch Health Monitoring (10 minutes interval)

**Purpose**: Monitor batch health dan detect anomalies

**Logic** (placeholder for custom monitoring):
1. Get all active batches
2. Check for stuck batches (long time without PLC read updates)
3. Check for unusual consumption patterns
4. Log warnings for operator attention

**Configuration**: Fixed 10 minutes interval

**When it runs**: Every 10 minutes

**Extensibility**: Can be extended to:
- Send email notifications
- Trigger alerts to external systems
- Track performance metrics

---

## New Services

### 1. MOHistoryService

**File**: `app/services/mo_history_service.py`

**Purpose**: Manage mo_histories table and batch lifecycle

**Methods**:

#### `move_to_history(mo_batch, status, notes)`
Move batch dari mo_batch ke mo_histories
- Copy all fields from batch to history
- Set status (completed/failed)
- Add optional notes
- Return history record

#### `delete_from_batch(mo_batch)`
Delete record dari mo_batch table after successful archive

#### `get_completed_batches()`
Get all batches dengan status_manufacturing = 1

#### `get_history(limit, offset, status)`
Get history records dengan pagination

#### `get_history_by_mo_id(mo_id)`
Get history for specific MO

**Usage**:
```python
from app.services.mo_history_service import get_mo_history_service

history_service = get_mo_history_service(db)

# Move to history
history = history_service.move_to_history(batch, status="completed")

# Delete from batch
history_service.delete_from_batch(batch)

# Get history
histories = history_service.get_history(limit=100)
```

---

## New API Endpoints

### Monitoring Endpoints

#### `GET /api/admin/batch-status`
Get current status of all batches in mo_batch table

**Response**:
```json
{
  "status": "success",
  "data": {
    "total_batches": 10,
    "active_batches": 8,
    "completed_batches": 2,
    "is_empty": false,
    "batches": [
      {
        "batch_no": 1,
        "mo_id": "WH/MO/00001",
        "equipment": "PLC01",
        "consumption": 1000.0,
        "status_manufacturing": false,
        "status_operation": true,
        "actual_finished_goods": 950.0,
        "last_read_from_plc": "2026-02-14T10:30:00+00:00"
      }
    ]
  }
}
```

#### `GET /api/admin/monitor/real-time`
Real-time monitoring dashboard dengan categorized batches

**Response**:
```json
{
  "status": "success",
  "data": {
    "summary": {
      "total": 10,
      "in_progress": 8,
      "completed": 2
    },
    "in_progress": [...],
    "completed": [...]
  }
}
```

#### `GET /api/admin/history?limit=100&offset=0`
Get history of processed batches dengan pagination

**Response**:
```json
{
  "status": "success",
  "data": {
    "total": 50,
    "limit": 100,
    "offset": 0,
    "histories": [
      {
        "id": "uuid",
        "batch_no": 1,
        "mo_id": "WH/MO/00001",
        "finished_goods": "Product A",
        "actual_weight": 950.0,
        "actual_consumptions": {
          "silo_a": 825.5,
          "silo_b": 600.3
        }
      }
    ]
  }
}
```

#### `GET /api/admin/history/{mo_id}`
Get history for specific MO ID

#### `GET /api/admin/failed-to-push`
List batches yang completed tapi gagal push ke Odoo

**Response**:
```json
{
  "status": "success",
  "data": {
    "total": 2,
    "message": "These batches are completed but not yet pushed to Odoo",
    "batches": [...]
  }
}
```

---

### Manual Control Endpoints

#### `POST /api/admin/manual/retry-push-odoo/{mo_id}`
Manual retry untuk push completed batch ke Odoo

**Use Case**: Batch completed tapi gagal update ke Odoo (network issue, Odoo down, etc.)

**Process**:
1. Find batch by mo_id
2. Verify status_manufacturing = 1
3. Push to Odoo
4. Move to history
5. Delete from mo_batch

**Response**:
```json
{
  "status": "success",
  "message": "Successfully pushed MO WH/MO/00001 to Odoo and archived",
  "data": {...}
}
```

#### `POST /api/admin/manual/reset-batch/{mo_id}`
Manual reset batch status untuk reprocess

**Use Case**: Batch perlu diproses ulang di PLC (error, incorrect data, etc.)

**Process**:
1. Find batch by mo_id
2. Reset status_manufacturing = 0
3. Reset status_operation = 0
4. Optionally reset actual values

**Response**:
```json
{
  "status": "success",
  "message": "Successfully reset status for MO WH/MO/00001",
  "data": {
    "mo_id": "WH/MO/00001",
    "status_manufacturing": false,
    "status_operation": false
  }
}
```

#### `POST /api/admin/manual/cancel-batch/{batch_no}`
Cancel batch dan pindahkan ke history dengan status 'cancelled'

**Use Case**: Batch yang gagal atau tidak jadi diproses dan tidak perlu diulang (quality issue, data error, operational decision)

**Parameters**:
- `batch_no` (path): Nomor batch yang akan di-cancel
- `notes` (body, optional): Alasan cancellation

**Process**:
1. Find batch by batch_no
2. Move to mo_histories dengan status='cancelled'
3. Set notes untuk audit trail
4. Delete from mo_batch

**Request Example**:
```bash
curl -X POST "http://localhost:8000/admin/manual/cancel-batch/12345" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Material quality issue - cancelled by QC"}'
```

**Response**:
```json
{
  "success": true,
  "message": "Batch 12345 cancelled successfully",
  "batch_no": 12345,
  "mo_id": "MO/00123",
  "status": "cancelled"
}
```

**See**: [CANCEL_BATCH_GUIDE.md](CANCEL_BATCH_GUIDE.md) for complete documentation

#### `POST /api/admin/manual/trigger-plc-sync`
Manually trigger PLC read sync task

**Use Case**: Force immediate PLC read tanpa tunggu interval

#### `POST /api/admin/manual/trigger-process-completed`
Manually trigger process completed batches task

**Use Case**: Force immediate processing completed batches

---

## Configuration

### Environment Variables (.env)

```env
# Scheduler Configuration
ENABLE_AUTO_SYNC=true              # Enable/disable scheduler
SYNC_INTERVAL_MINUTES=60           # Task 1 interval (default: 60)
SYNC_BATCH_LIMIT=10                # Max batches per sync

# PLC Configuration
PLC_IP=192.168.1.2
PLC_PORT=9600
PLC_PROTOCOL=udp
PLC_TIMEOUT_SEC=2

# Odoo Configuration
ODOO_URL=http://localhost:8070
ODOO_DATABASE=odoo14
ODOO_USERNAME=admin
ODOO_PASSWORD=yourpassword

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/plc
```

### Task Intervals (Hardcoded)

| Task | Interval | Configurable? |
|------|----------|---------------|
| Task 1: Auto-sync MO | 60 min (default) | âœ… Via SYNC_INTERVAL_MINUTES |
| Task 2: PLC Read Sync | 5 min | âŒ Fixed |
| Task 3: Process Completed | 3 min | âŒ Fixed |
| Task 4: Health Monitoring | 10 min | âŒ Fixed |

**Recommendation**: Keep these intervals as-is for optimal performance. Adjust only if:
- PLC cycle time is significantly different
- Network latency is high
- Database performance issues

---

## Workflow Diagram

### Complete Workflow

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ 1. ODOO: Confirmed MOs waiting to be processed                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ 2. TASK 1: Fetch MO list from Odoo (every 60 min)               â”‚
â”‚    - Check if mo_batch is empty                                  â”‚
â”‚    - If empty: Fetch 10 MOs                                      â”‚
â”‚    - Insert to mo_batch table                                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ 3. PLC: Write MO data to PLC memory (D7000-D7976)               â”‚
â”‚    - Manual or via /plc/write-mo-batch/{mo_id}                  â”‚
â”‚    - Handshake: Check D7076=1 before write (PLC ready)          â”‚
â”‚    - PLC receives and starts processing                          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ 4. TASK 2: Read PLC memory (every 5 min)                        â”‚
â”‚    - Read area D6001-D6077 (includes LQ114, LQ115 tanks)        â”‚
â”‚    - Update mo_batch with actual consumption                     â”‚
â”‚    - Update status_manufacturing, status_operation               â”‚
â”‚    - Handshake: Mark status_read_data per-batch=1 after reading (data read)          â”‚
â”‚    - Skip if status_manufacturing already = 1                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â–¼
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â”‚ PLC: Batch processing         â”‚
         â”‚ - Sets status_manufacturing=1 â”‚
         â”‚   when batch is done          â”‚
         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                     â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ 5. TASK 3: Process completed batches (every 3 min)              â”‚
â”‚    - Find batches with status_manufacturing = 1                  â”‚
â”‚    - Update consumption to Odoo                                  â”‚
â”‚    - Mark MO as done in Odoo                                     â”‚
â”‚    - Move to mo_histories table                                  â”‚
â”‚    - Delete from mo_batch                                        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ 6. MO Histories Table: Archived completed batches               â”‚
â”‚    - Can be viewed via /admin/history                            â”‚
â”‚    - Used for analytics and troubleshooting                      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Error Recovery Workflow

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Batch Completed in PLC (status_manufacturing = 1)               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ TASK 3: Try to push to Odoo                                     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â”‚
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â–¼                         â–¼
     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
     â”‚ SUCCESS      â”‚          â”‚ FAILURE      â”‚
     â”‚ - Move to    â”‚          â”‚ - Keep in    â”‚
     â”‚   history    â”‚          â”‚   mo_batch   â”‚
     â”‚ - Delete     â”‚          â”‚ - Log error  â”‚
     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜          â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                                      â”‚
                                      â–¼
                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                       â”‚ Operator Actions:            â”‚
                       â”‚                              â”‚
                       â”‚ 1. Check /admin/failed-to-pushâ”‚
                       â”‚ 2. Investigate error         â”‚
                       â”‚ 3. Fix issue (network, Odoo) â”‚
                       â”‚ 4. Manual retry:             â”‚
                       â”‚    /admin/manual/retry-push- â”‚
                       â”‚    odoo/{mo_id}              â”‚
                       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Logging

All tasks and services log with prefix untuk easy filtering:

- `[TASK 1]` - Auto-sync MO
- `[TASK 2]` - PLC read sync
- `[TASK 3]` - Process completed batches
- `[TASK 4]` - Health monitoring

**Example Logs**:
```
INFO: [TASK 1] Auto-sync MO task running...
INFO: [TASK 1] Table mo_batch is empty. Fetching new batches from Odoo...
INFO: [TASK 1] âœ“ Auto-sync completed: 10 MO batches synced

INFO: [TASK 2] PLC read sync task running...
INFO: [TASK 2] Found 10 active batches
INFO: [TASK 2] âœ“ Updated batch 1 (MO: WH/MO/00001)
INFO: [TASK 2] âœ“ PLC sync completed: 10/10 batches updated

INFO: [TASK 3] Process completed batches task running...
INFO: [TASK 3] Found 2 completed batches
INFO: [TASK 3] Processing completed batch 1 (MO: WH/MO/00001)
INFO: [TASK 3] âœ“ Processed and archived MO WH/MO/00001
INFO: [TASK 3] âœ“ Completed batches processing finished: 2/2 batches processed
```

---

## Testing

### 1. Start Application

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output**:
```
âœ“ Task 1: Auto-sync MO scheduler added (interval: 60 minutes)
âœ“ Task 2: PLC read sync scheduler added (interval: 5 minutes)
âœ“ Task 3: Process completed batches scheduler added (interval: 3 minutes)
âœ“ Task 4: Batch health monitoring scheduler added (interval: 10 minutes)
âœ“âœ“âœ“ Enhanced Scheduler STARTED with 4 tasks âœ“âœ“âœ“
```

### 2. Test Monitoring Endpoints

```bash
# Check batch status
curl http://localhost:8000/api/admin/batch-status

# Real-time monitoring
curl http://localhost:8000/api/admin/monitor/real-time

# View history
curl http://localhost:8000/api/admin/history?limit=10
```

### 3. Test Manual Controls

```bash
# Trigger MO sync manually
curl -X POST http://localhost:8000/api/admin/trigger-sync

# Trigger PLC sync manually
curl -X POST http://localhost:8000/api/admin/manual/trigger-plc-sync

# Retry push to Odoo
curl -X POST http://localhost:8000/api/admin/manual/retry-push-odoo/WH/MO/00001

# Reset batch status
curl -X POST http://localhost:8000/api/admin/manual/reset-batch/WH/MO/00001

# Check failed batches
curl http://localhost:8000/api/admin/failed-to-push
```

### 4. Simulated Workflow Test

**Scenario**: Complete workflow simulation

1. **Clear mo_batch** (simulate PLC finished)
   ```bash
   curl -X POST http://localhost:8000/api/admin/clear-mo-batch
   ```

2. **Trigger MO sync** (fetch from Odoo)
   ```bash
   curl -X POST http://localhost:8000/api/admin/trigger-sync
   ```

3. **Check batch status** (verify MOs inserted)
   ```bash
   curl http://localhost:8000/api/admin/batch-status
   ```

4. **Simulate PLC completion** (manually set status)
   ```sql
   UPDATE mo_batch SET status_manufacturing = true WHERE mo_id = 'WH/MO/00001';
   ```

5. **Trigger process completed** (push to Odoo & archive)
   ```bash
   curl -X POST http://localhost:8000/api/admin/manual/trigger-process-completed
   ```

6. **Check history** (verify archived)
   ```bash
   curl http://localhost:8000/api/admin/history
   ```

---

## Troubleshooting

### Issue: Scheduler not starting

**Check**:
1. `.env` â†’ `ENABLE_AUTO_SYNC=true`
2. Restart application
3. Check logs for "Enhanced Scheduler STARTED"

### Issue: PLC sync not updating batches

**Check**:
1. PLC connectivity: `curl http://localhost:8000/api/plc/config`
2. PLC memory area readable
3. Check logs for `[TASK 2]` entries
4. Verify batches have `status_manufacturing = 0`

### Issue: Completed batches not pushed to Odoo

**Check**:
1. Check `/api/admin/failed-to-push` for stuck batches
2. Verify Odoo connectivity
3. Check logs for `[TASK 3]` errors
4. Manual retry: `/admin/manual/retry-push-odoo/{mo_id}`

### Issue: History not showing data

**Check**:
1. Verify mo_histories table exists: `SELECT * FROM mo_histories LIMIT 1`
2. Check if Task 3 ran successfully
3. Verify batches were moved from mo_batch to mo_histories

---

## Database Schema

### mo_batch (Active Batches)

Primary table for batches being processed by PLC.

**Key Fields**:
- `batch_no` - Sequential batch number
- `mo_id` - Manufacturing Order ID
- `status_manufacturing` - 0 (in progress), 1 (completed)
- `actual_consumption_silo_*` - Actual consumption from PLC
- `last_read_from_plc` - Timestamp of last PLC read

### mo_histories (Archived Batches)

Archive table for completed/failed batches.

**Same structure as mo_batch** with additional tracking:
- Immutable records (no updates after insert)
- Used for analytics and troubleshooting
- Can store notes about completion/failure

---

## Production Recommendations

1. **Monitoring**:
   - Setup log aggregation (ELK, Grafana Loki)
   - Alert on Task failures (consecutive failures > 3)
   - Monitor `/api/admin/failed-to-push` regularly

2. **Performance**:
   - Database indexes on `mo_id`, `batch_no`, `status_manufacturing`
   - Regular cleanup of old mo_histories records (>6 months)
   - Monitor scheduler task execution time

3. **Security**:
   - Protect admin endpoints with authentication
   - Rate limiting on manual trigger endpoints
   - Audit logging for manual interventions

4. **Backup**:
   - Daily backup of mo_histories table
   - Backup before clearing mo_batch table
   - Transaction logs for recovery

---

## Next Steps / Extensions

1. **Notification System**:
   - Email alerts for failed batches
   - Webhook integration for external systems
   - SMS/Telegram notifications for critical failures

2. **Advanced Monitoring**:
   - Grafana dashboard for real-time metrics
   - Performance analytics (cycle time, success rate)
   - Predictive alerts (stuck batches detection)

3. **Failed Batch Handling**:
   - Add `status_manufacturing = 2` for failed batches
   - Separate workflow for failed batch recovery
   - Manual investigation tools

4. **Audit Trail**:
   - Log all manual interventions
   - Track operator actions
   - Generate audit reports

---

## Summary

âœ… **Implemented**:
- Enhanced scheduler dengan 4 periodic tasks
- MO history service dan table
- Real-time monitoring endpoints
- Manual control endpoints
- Failed batch tracking
- Comprehensive logging
- Data protection untuk completed batches

âœ… **Key Features**:
- Automatic MO sync dari Odoo
- Periodic PLC read dan database update
- Automatic processing completed batches
- Manual retry untuk failed batches
- Real-time monitoring dashboard
- Complete history tracking

âœ… **Production Ready**:
- Error handling dan recovery
- Transaction safety
- Data protection
- Comprehensive logging
- Manual override capabilities

