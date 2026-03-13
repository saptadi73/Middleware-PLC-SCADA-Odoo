# Auto-Sync Scheduler - Manufacturing Order Batch System

## Overview

Sistem auto-sync berkala untuk fetch Manufacturing Order (MO) dari Odoo ke table `mo_batch` dengan mekanisme smart-wait: hanya fetch jika table kosong (PLC sudah selesai proses semua batch).

## Configuration (.env)

```env
# Auto-sync settings
ENABLE_AUTO_SYNC=true              # true/false untuk aktifkan/nonaktifkan
SYNC_INTERVAL_MINUTES=5            # Interval sync dalam menit
SYNC_BATCH_LIMIT=10                # Jumlah batch yang di-fetch per sync
```

## How It Works

### Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Scheduler Timer (Every 5 minutes)                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │ Check mo_batch      │
         │ COUNT(*) = ?        │
         └──────┬──────────────┘
                │
       ┌────────┴────────┐
       │                 │
   COUNT > 0         COUNT = 0
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────────┐
│ SKIP SYNC    │  │ FETCH from Odoo  │
│ (PLC masih   │  │ (10 batches)     │
│  proses)     │  │                  │
└──────────────┘  └────────┬─────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ INSERT to mo_batch │
                  │ (batch_no 1..10)   │
                  └────────┬───────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ PLC Reads & Process│
                  │ Each Batch         │
                  └────────┬───────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ After All Done:    │
                  │ Clear Table        │
                  │ (Manual/API)       │
                  └────────┬───────────┘
                           │
                           ▼
                  Next sync cycle...
```

### Logic Detail

1. **Timer Trigger**: Scheduler runs every `SYNC_INTERVAL_MINUTES`
2. **Table Check**: 
   ```sql
   SELECT COUNT(*) FROM mo_batch
   ```
   - If `COUNT > 0`: Skip sync (PLC sedang proses batch)
   - If `COUNT = 0`: Proceed to fetch
3. **Fetch from Odoo**: 
   - Endpoint: `POST /api/scada/mo-list-detailed`
   - Limit: `SYNC_BATCH_LIMIT` batches
4. **Insert to Database**: Sync data ke table `mo_batch`
5. **PLC Processing**: PLC membaca batch dari table
6. **Clear Table**: Setelah PLC selesai, clear table (manual atau via API)
7. **Repeat**: Scheduler detect table kosong → fetch batch berikutnya

### Data Protection During PLC Read

**IMPORTANT: Completed Manufacturing Order Protection**

Saat PLC membaca data dan update database, sistem melindungi data yang sudah selesai:

- ✅ **Update allowed**: `status_manufacturing = 0` (False) - Manufacturing in progress
- ❌ **Update blocked**: `status_manufacturing = 1` (True) - Manufacturing already completed

**Implementation** (`plc_sync_service.py`):
```python
def _update_batch_if_changed(...):
    # Check if manufacturing already completed
    if batch.status_manufacturing:
        logger.info(f"Skip update for MO {batch.mo_id}: status_manufacturing already completed (1)")
        return False
    
    # Proceed with update only if still in progress
    # Update actual_consumption_silo_* fields
    # Update status fields if changed
```

**Why this matters:**
- PLC read cycles continue even after MO is marked done
- Protection prevents overwriting final consumption data
- Maintains data integrity for completed/historical records
- Ensures audit trail remains accurate

**Workflow with Protection:**
```
PLC Read Cycle → Check status_manufacturing
                        ↓
              ┌─────────┴─────────┐
              │                   │
          = 0 (False)          = 1 (True)
              │                   │
              ▼                   ▼
       Update Database      Skip Update
       (In Progress)        (Completed)
              │                   │
              └─────────┬─────────┘
                        ↓
                  Continue Cycle
```

## API Endpoints

### 1. Check Batch Status

```http
GET /api/admin/batch-status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_batches": 7,
    "is_empty": false,
    "batches": [
      {
        "batch_no": 1,
        "mo_id": "WH/MO/00002",
        "equipment": "PLC01",
        "consumption": 2500.0
      }
    ]
  }
}
```

### 2. Prepare TASK1 Fresh Start

```http
POST /api/admin/reset-task1-start
```

**Use Case**: Dipakai saat sistem benar-benar ingin mulai dari awal dan PLC WRITE area masih menahan handshake `status_read_data=0` di `D7076`, `D7176`, `D7276`, dan seterusnya.

**Behavior**:
- Set semua flag WRITE `status_read_data` menjadi `1` berdasarkan mapping di `MASTER_BATCH_REFERENCE.json`
- Hapus semua data di table `mo_batch`
- Setelah itu TASK1 bisa menulis batch baru lagi

**Response:**
```json
{
  "status": "success",
  "message": "TASK 1 initial state prepared successfully",
  "data": {
    "write_ready_addresses": [
      "D7076",
      "D7176",
      "D7276",
      "D7376"
    ],
    "write_ready_count": 10,
    "deleted_mo_batch_count": 7
  }
}
```

**Frontend Example (fetch):**
```javascript
async function resetTask1Start() {
  const response = await fetch('/api/admin/reset-task1-start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  const result = await response.json();

  if (!response.ok || result.status !== 'success') {
    throw new Error(result.detail || result.message || 'Failed to reset TASK1');
  }

  return result;
}
```

**Frontend Example (axios):**
```javascript
import axios from 'axios';

async function resetTask1Start() {
  const { data } = await axios.post('/api/admin/reset-task1-start');
  return data;
}
```

### 3. Clear mo_batch Table

```http
POST /api/admin/clear-mo-batch
```

**Use Case**: Setelah PLC selesai proses semua batch, clear table untuk trigger fetch berikutnya.

**Response:**
```json
{
  "status": "success",
  "message": "mo_batch table cleared successfully",
  "deleted_count": 7
}
```

### 4. Manual Trigger Sync

```http
POST /api/admin/trigger-sync
```

**Use Case**: Force sync tanpa tunggu interval scheduler.

**Response:**
```json
{
  "status": "success",
  "message": "Manual sync completed successfully"
}
```

### 5. Monitor TASK Scheduler per Task

```http
GET /api/admin/task-monitor/summary
GET /api/admin/task-monitor/errors
GET /api/admin/task-monitor/errors/flat
GET /api/admin/task-monitor/{task_name}
```

**Use Case**: Dipakai frontend untuk menampilkan monitoring TASK demi TASK seperti yang terlihat di terminal scheduler.

**Task name yang valid**:
- `task1`
- `task2`
- `task3`
- `task4`

**Query parameters**:
- `since_minutes=180` untuk jendela log terbaru
- `limit=50` dan `skip=0` untuk pagination detail
- `level=ERROR` bila frontend ingin menampilkan error saja
- `limit_per_task=5` dan `include_warning=true` untuk endpoint alert agregat
- `skip=0` dan `limit=100` untuk endpoint alert flat agar bisa pagination/infinite scroll

**Summary Response:**
```json
{
  "status": "success",
  "data": {
    "since_minutes": 180,
    "tasks": [
      {
        "task": "task1",
        "label": "TASK 1",
        "status": "success",
        "latest_level": "INFO",
        "last_run_at": "2026-03-13T08:21:10.123456+00:00",
        "latest_message": "[TASK 1] Auto-sync committed successfully: staged=4, written=4"
      }
    ]
  }
}
```

**Detail Response:**
```json
{
  "status": "success",
  "data": {
    "summary": {
      "task": "task2",
      "label": "TASK 2",
      "status": "running"
    },
    "logs": [
      {
        "timestamp": "2026-03-13T08:25:10.123456+00:00",
        "level": "INFO",
        "module": "app.core.scheduler",
        "message": "[TASK 2] Updated 3 batch(es) from PLC (processed=3, failed=0)"
      }
    ],
    "meta": {
      "total": 25,
      "has_next": false
    }
  }
}
```

**Alert Aggregate Response (`/errors`):**
```json
{
  "status": "success",
  "data": {
    "since_minutes": 180,
    "levels": ["ERROR", "CRITICAL", "WARNING"],
    "limit_per_task": 5,
    "total_alerts": 2,
    "tasks": {
      "task1": [{ "level": "ERROR", "message": "[TASK 1] ERROR ..." }],
      "task2": [],
      "task3": [{ "level": "WARNING", "message": "[TASK 3] ..." }],
      "task4": []
    }
  }
}
```

**Frontend Example (fetch):**
```javascript
async function loadTaskMonitor(taskName) {
  const response = await fetch(`/api/admin/task-monitor/${taskName}?limit=50&since_minutes=180`);
  const result = await response.json();

  if (!response.ok || result.status !== 'success') {
    throw new Error(result.detail || result.message || 'Failed to load task monitor');
  }

  return result.data;
}
```

### 6. View Table `mo_batch` & `mo_histories` (Pagination)

```http
GET /api/admin/table/mo-batch
GET /api/admin/table/mo-histories
```

**Use Case**: Dipakai frontend untuk halaman tabel active batch (`mo_batch`) dan riwayat besar (`mo_histories`) dengan pagination/filter.

**Query parameters `mo_histories`**:
- `limit` (default: 50)
- `offset` (default: 0)
- `status` (opsional)
- `mo_id` (opsional, partial match)

**Contoh**:
- `/api/admin/table/mo-histories?limit=50&offset=0`
- `/api/admin/table/mo-histories?limit=50&offset=0&status=completed`
- `/api/admin/table/mo-histories?limit=50&offset=0&status=completed&mo_id=WH/MO/00`

**Response ringkas**:
```json
{
  "status": "success",
  "data": {
    "rows": [],
    "pagination": {
      "limit": 50,
      "offset": 0,
      "total": 1200,
      "has_next": true
    }
  }
}
```

## Testing Scenarios

### Scenario 1: Normal Operation

```bash
# 1. Check current status
curl http://localhost:8000/api/admin/batch-status

# 2. Reset TASK1 from clean state
curl -X POST http://localhost:8000/api/admin/reset-task1-start

# 3. Trigger manual sync (or wait 5 minutes)
curl -X POST http://localhost:8000/api/admin/trigger-sync

# 4. Check TASK summary like scheduler terminal
curl http://localhost:8000/api/admin/task-monitor/summary

# 5. Inspect TASK 2 recent logs
curl "http://localhost:8000/api/admin/task-monitor/task2?limit=20&since_minutes=180"

# 6. Get aggregated task alerts
curl "http://localhost:8000/api/admin/task-monitor/errors?since_minutes=180&limit_per_task=5&include_warning=true"

# 7. Get flat alert feed
curl "http://localhost:8000/api/admin/task-monitor/errors/flat?since_minutes=180&skip=0&limit=100&include_warning=true"

# 8. View mo_batch table
curl http://localhost:8000/api/admin/table/mo-batch

# 9. View mo_histories table with filter
curl "http://localhost:8000/api/admin/table/mo-histories?limit=50&offset=0&status=completed&mo_id=WH/MO/00"

# 4. Verify data inserted
curl http://localhost:8000/api/admin/batch-status
```

### Scenario 1B: Frontend Flow

```javascript
async function startTask1FromBeginning() {
  await fetch('/api/admin/reset-task1-start', { method: 'POST' });
  await fetch('/api/admin/trigger-sync', { method: 'POST' });
  return fetch('/api/admin/batch-status');
}
```

### Scenario 2: Test Scheduler Skip Logic

```bash
# 1. Ensure table has data
curl http://localhost:8000/api/admin/batch-status

# 2. Trigger sync (should skip)
curl -X POST http://localhost:8000/api/admin/trigger-sync

# Check logs: "Table mo_batch has 7 records. Skipping sync..."
```

### Scenario 3: Disable Auto-Sync

```env
# In .env
ENABLE_AUTO_SYNC=false
```

Restart uvicorn. Scheduler tidak akan start.

## Logs Monitoring

Scheduler logs akan muncul di console:

```
INFO:     ✓ Auto-sync scheduler STARTED: interval=5 minutes, batch_limit=10
INFO:     Auto-sync task running...
INFO:     Table mo_batch has 7 records. Skipping sync - waiting for PLC...
```

Or when fetching:

```
INFO:     Auto-sync task running...
INFO:     Table mo_batch is empty. Fetching new batches from Odoo...
INFO:     ✓ Auto-sync completed: 10 MO batches synced
```

## Database Schema

Table `mo_batch` structure:
- **batch_no**: Sequential number (1, 2, 3, ...)
- **mo_id**: Manufacturing Order ID dari Odoo
- **consumption**: Total quantity untuk MO
- **equipment_id_batch**: Equipment code (PLC01)
- **component_silo_a_name** to **component_silo_m_name**: Component names
- **consumption_silo_a** to **consumption_silo_m**: Consumption per silo

## Troubleshooting

### Issue: Scheduler tidak running

**Check:**
1. `.env` → `ENABLE_AUTO_SYNC=true`
2. Restart uvicorn
3. Check logs for: "Auto-sync scheduler STARTED"

### Issue: Data tidak fetch meskipun table kosong

**Check:**
1. Odoo endpoint accessible: `curl http://localhost:8070/api/scada/mo-list-detailed`
2. Credentials di `.env` valid
3. Check error logs

### Issue: Data fetch tapi tidak masuk database

**Check:**
1. Database connection: `DATABASE_URL` di `.env`
2. Table exists: `SELECT * FROM mo_batch LIMIT 1`
3. Check error logs untuk SQL errors

## Production Considerations

1. **Interval Setting**: 
   - Development: 5 minutes untuk testing cepat
   - Production: 15-30 minutes (tergantung cycle time PLC)

2. **Batch Limit**:
   - Default: 10 batches
   - Adjust sesuai kapasitas PLC dan storage

3. **Monitoring**:
   - Setup log aggregation (ELK, Grafana Loki)
   - Alert jika sync gagal > 3 kali berturut-turut
   - Monitor table growth dan clear frequency

4. **Security**:
   - Protect admin endpoints dengan authentication
   - Use environment variables untuk credentials
   - Tidak expose admin endpoints ke public internet
