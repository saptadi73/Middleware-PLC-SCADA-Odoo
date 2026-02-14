# Cancel Batch Guide

## Overview

Fitur **Cancel Batch** memungkinkan operator untuk membatalkan batch yang gagal atau tidak jadi diproses, tanpa perlu melakukan retry. Batch yang di-cancel akan dipindahkan ke tabel `mo_histories` dengan status `"cancelled"` dan dihapus dari `mo_batch`.

## Kapan Menggunakan Cancel Batch?

Gunakan cancel batch dalam situasi berikut:

### 1. **Masalah Kualitas Produk**
- Material quality issue (bahan baku tidak sesuai standar)
- Equipment malfunction yang mempengaruhi kualitas output
- Hasil produksi tidak sesuai spesifikasi

### 2. **Data Error yang Tidak Bisa Diperbaiki**
- MO ID tidak valid di Odoo
- Component mapping salah dan tidak bisa di-fix
- Data silo incorrect dan menyebabkan consumption calculation error

### 3. **Operational Decision**
- Management decision untuk skip batch tertentu
- Change in production schedule
- Emergency stop untuk batch tertentu

### 4. **Gagal Berulang Kali (After Multiple Retries)**
- Batch sudah di-retry berkali-kali tapi tetap gagal
- Error yang persistent dan tidak bisa di-resolve
- Memutuskan untuk abandon batch daripada blocking queue

## Perbedaan: Cancel vs Failed vs Completed

| Status | Deskripsi | Use Case | Bisa Retry? |
|--------|-----------|----------|-------------|
| **completed** | Batch berhasil diproses dan data sudah di-push ke Odoo | Normal successful flow | ❌ No |
| **failed** | Batch gagal proses tapi masih bisa di-retry | Temporary error (network, timeout) | ✅ Yes |
| **cancelled** | Batch dibatalkan dan tidak akan diproses lagi | Quality issue, data error, operational decision | ❌ No |

## Database Schema Changes

### Migration: `20260214_0010_add_status_column_to_histories.py`

Menambahkan 2 kolom baru di tabel `mo_histories`:

```python
# Status column
status = Column(
    String(20),
    nullable=False,
    server_default="completed",
    index=True
)

# Notes column untuk alasan cancellation
notes = Column(Text, nullable=True)
```

### Status Values

- `"completed"`: Batch successfully processed
- `"failed"`: Batch failed but can be retried
- `"cancelled"`: Batch cancelled by operator (no retry)

## API Endpoint

### POST `/admin/manual/cancel-batch/{batch_no}`

Cancel sebuah batch dan pindahkan ke history dengan status cancelled.

#### Request

```bash
POST /admin/manual/cancel-batch/12345
Content-Type: application/json

{
  "notes": "Material quality issue - batch cancelled by QC department"
}
```

**Path Parameters:**
- `batch_no` (integer, required): Nomor batch yang akan di-cancel

**Body Parameters:**
- `notes` (string, optional): Alasan cancellation

#### Response Success (200)

```json
{
  "success": true,
  "message": "Batch 12345 cancelled successfully",
  "batch_no": 12345,
  "mo_id": "MO/00123",
  "status": "cancelled"
}
```

#### Response Error (404)

```json
{
  "detail": "Batch 12345 not found"
}
```

#### Response Error (500)

```json
{
  "detail": "Error cancelling batch: <error details>"
}
```

## Workflow

### Cancel Batch Flow

```
┌─────────────────┐
│  mo_batch       │
│  (active batch) │
└────────┬────────┘
         │
         │ POST /admin/manual/cancel-batch/{batch_no}
         │
         ▼
┌────────────────────────────┐
│ 1. Cari batch by batch_no  │
│ 2. Validate batch exists   │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│ 3. Move to mo_histories    │
│    - Copy all fields       │
│    - Set status=cancelled  │
│    - Set notes             │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│ 4. Delete from mo_batch    │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│  mo_histories              │
│  status = "cancelled"      │
│  notes = "reason..."       │
└────────────────────────────┘
```

### Integration dengan Task 1

**Task 1** (Auto-sync MO) melakukan check:

```sql
SELECT COUNT(*) FROM mo_batch
```

Behaviour setelah cancellation:
- ✅ Cancelled batch sudah tidak ada di `mo_batch`
- ✅ COUNT berkurang setelah cancellation
- ✅ Jika semua batch di-cancel, table jadi empty
- ✅ Task 1 akan fetch new MOs dari Odoo

**Tidak ada perubahan logic Task 1 diperlukan** karena cancelled batches otomatis excluded dari count.

## Service Layer: MOHistoryService

### cancel_batch Method

```python
def cancel_batch(
    self,
    batch_no: int,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel a batch dan pindahkan ke history dengan status 'cancelled'.
    
    Args:
        batch_no: Nomor batch yang akan di-cancel
        notes: Alasan cancellation (optional)

    Returns:
        Dict dengan info hasil cancellation
    """
```

#### Success Return

```python
{
    "success": True,
    "message": "Batch 12345 cancelled successfully",
    "batch_no": 12345,
    "mo_id": "MO/00123",
    "status": "cancelled",
}
```

#### Failure Return

```python
{
    "success": False,
    "message": "Batch 12345 not found",
}
```

## Usage Examples

### Example 1: Cancel Batch dengan Reason

```bash
curl -X POST "http://localhost:8000/admin/manual/cancel-batch/12345" \\
  -H "Content-Type: application/json" \\
  -d '{
    "notes": "Equipment malfunction during production - batch quality compromised"
  }'
```

### Example 2: Cancel Batch tanpa Notes

```bash
curl -X POST "http://localhost:8000/admin/manual/cancel-batch/12345"
```

Default notes: `"Manually cancelled by operator"`

### Example 3: Query Cancelled Batches

```bash
# Get all cancelled batches from history
curl "http://localhost:8000/admin/history?status=cancelled&limit=50"
```

Response:
```json
{
  "histories": [
    {
      "batch_no": 12345,
      "mo_id": "MO/00123",
      "status": "cancelled",
      "notes": "Material quality issue",
      "last_read_from_plc": "2026-02-14T10:30:00Z",
      ...
    }
  ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

## Monitoring & Reporting

### Get History dengan Filter Status

```python
# Di admin.py atau custom service
history_service = get_mo_history_service(db)

# Get cancelled batches only
cancelled_batches = history_service.get_history(
    limit=100,
    offset=0,
    status="cancelled"
)
```

### Logging

Cancel operation menghasilkan log entries:

```
INFO - ✓ Moved MO MO/00123 (batch 12345) to history with status: cancelled
INFO - ✓ Deleted MO MO/00123 (batch 12345) from mo_batch
INFO - ✓ Cancelled batch 12345 (MO: MO/00123) and moved to history
```

## Best Practices

### 1. **Selalu Berikan Notes yang Jelas**

❌ Bad:
```json
{"notes": "error"}
```

✅ Good:
```json
{
  "notes": "Material quality check failed - moisture content 15% (max 10%). Cancelled by QC Supervisor John Doe at 14:30"
}
```

### 2. **Verify Before Cancel**

```bash
# Check batch status first
curl "http://localhost:8000/admin/batch-status?batch_no=12345"

# If confirmed, then cancel
curl -X POST "http://localhost:8000/admin/manual/cancel-batch/12345" \\
  -H "Content-Type: application/json" \\
  -d '{"notes": "Verified quality issue - cancelling batch"}'
```

### 3. **Track Cancellation Trends**

```sql
-- Query untuk analytics
SELECT 
    DATE(last_read_from_plc) as cancellation_date,
    COUNT(*) as cancelled_count,
    notes
FROM mo_histories
WHERE status = 'cancelled'
GROUP BY DATE(last_read_from_plc), notes
ORDER BY cancellation_date DESC;
```

### 4. **Review Cancelled Batches Regularly**

- Weekly review semua cancelled batches
- Identify patterns (recurring issues)
- Improve process berdasarkan cancellation reasons

## Troubleshooting

### Problem: Batch Not Found

```json
{
  "detail": "Batch 12345 not found"
}
```

**Possible Causes:**
- Batch number salah
- Batch sudah di-process (ada di history)
- Batch belum di-sync dari Odoo

**Solution:**
1. Check `mo_batch` table: `SELECT * FROM mo_batch WHERE batch_no = 12345`
2. Check `mo_histories` table: `SELECT * FROM mo_histories WHERE batch_no = 12345`
3. Verify batch_no dari Odoo

### Problem: Cannot Delete from mo_batch

```
Error cancelling batch: Failed to delete batch 12345 from mo_batch
```

**Possible Causes:**
- Database constraint violation
- Foreign key references
- Transaction conflict

**Solution:**
1. Check database logs
2. Verify no other process is updating the batch
3. Retry the operation

### Problem: History Created but Batch Not Deleted

Jika terjadi error antara move_to_history dan delete_from_batch, akan terjadi **automatic rollback**:

```python
# Rollback history jika delete gagal
self.db.delete(history)
self.db.commit()
```

System ensures **atomic operation** - either both succeed or both fail.

## Migration Instructions

### Step 1: Run Alembic Migration

```bash
# Apply migration
alembic upgrade head
```

Ini akan:
1. Add `status` column ke `mo_histories`
2. Add `notes` column ke `mo_histories`
3. Create index on `status` column
4. Set default value: `status = 'completed'`

### Step 2: Verify Migration

```sql
-- Check new columns exist
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'mo_histories' 
AND column_name IN ('status', 'notes');
```

Expected result:
```
column_name | data_type         | column_default
------------|-------------------|----------------
status      | character varying | 'completed'
notes       | text              | NULL
```

### Step 3: Backfill Existing Data (Optional)

```sql
-- Semua existing records akan automatically have status='completed'
-- karena server_default='completed'

-- Verify
SELECT status, COUNT(*) 
FROM mo_histories 
GROUP BY status;
```

### Step 4: Restart Application

```bash
# Restart FastAPI application untuk load model changes
# Model sudah include new columns
```

## Related Documentation

- [DATABASE_PERSISTENCE_GUIDE.md](DATABASE_PERSISTENCE_GUIDE.md) - Data protection logic
- [ENHANCED_SCHEDULER_GUIDE.md](ENHANCED_SCHEDULER_GUIDE.md) - Scheduler tasks overview
- [AUTO_SYNC_README.md](AUTO_SYNC_README.md) - Auto-sync workflow
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - System architecture

## Summary

### Key Points

✅ **Cancel batch** = Move to history dengan status "cancelled" + delete from mo_batch  
✅ **Endpoint**: `POST /admin/manual/cancel-batch/{batch_no}`  
✅ **Database**: New `status` and `notes` columns in `mo_histories`  
✅ **Use case**: Quality issues, data errors, operational decisions  
✅ **Cannot retry**: Cancelled batches tidak bisa di-retry  
✅ **Automatic exclusion**: Task 1 automatically excludes cancelled batches  
✅ **Atomic operation**: Move + delete both succeed or both fail  

### Quick Reference

```bash
# Cancel a batch
POST /admin/manual/cancel-batch/{batch_no}
Body: {"notes": "reason"}

# View cancelled batches
GET /admin/history?status=cancelled

# Run migration
alembic upgrade head
```

---

**Created:** 2026-02-14  
**Version:** 1.0  
**Status:** Production Ready
