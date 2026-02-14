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

### 2. Clear mo_batch Table

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

### 3. Manual Trigger Sync

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

## Testing Scenarios

### Scenario 1: Normal Operation

```bash
# 1. Check current status
curl http://localhost:8000/api/admin/batch-status

# 2. Clear table (simulate PLC done)
curl -X POST http://localhost:8000/api/admin/clear-mo-batch

# 3. Trigger manual sync (or wait 5 minutes)
curl -X POST http://localhost:8000/api/admin/trigger-sync

# 4. Verify data inserted
curl http://localhost:8000/api/admin/batch-status
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
