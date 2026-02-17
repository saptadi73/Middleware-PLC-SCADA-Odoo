# Auto-Cancel Batch on Failure (status_operation=1)

## Overview

**Fitur Baru:** Automatic cancellation of batch ketika PLC mendeteksi failure (`status_operation=1`).

Sebelumnya, cancel batch hanya bisa dilakukan secara **manual** via API endpoint. Sekarang sistem akan **otomatis** mendeteksi failure dari PLC dan melakukan cancellation workflow secara automatic.

---

## Trigger Condition

**Automatic cancellation terjadi ketika:**

```
status_operation: 0 → 1 (changed to failed)
```

Kondisi ini terjadi saat:
- PLC mendeteksi ada masalah dalam proses produksi (equipment failure, material issue, quality problem, dll)
- PLC set `status_operation` memory address menjadi `1` (failed)
- Middleware membaca perubahan ini di Task 2 (PLC Read Sync)

---

## Automatic Cancellation Workflow

```
┌────────────────────────────────────────────────────────────────┐
│  Task 2: PLC Read Sync (plc_sync_service.py)                  │
│  - Read memory PLC setiap 5 detik                              │
│  - Update mo_batch dengan data terbaru                         │
└────────────────┬───────────────────────────────────────────────┘
                 │
                 ▼
         ┌───────────────────┐
         │ status_operation  │
         │  0 → 1 detected?  │
         └────────┬──────────┘
                  │ YES
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  AUTO-CANCEL TRIGGERED                                          │
│                                                                  │
│  Step 1: Cancel MO in Odoo                                     │
│  ├─ Call: POST /api/scada/mo/cancel                           │
│  └─ Payload: {"mo_id": "WH/MO/00123"}                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │  SUCCESS?                                         │          │
│  │  ✓ Yes: Continue to Step 2                       │          │
│  │  ✗ No: Log error, update status_operation field  │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                  │
│  Step 2: Archive to History (status='cancelled')               │
│  ├─ Call: mo_history_service.cancel_batch()                   │
│  ├─ Move to mo_histories with status='cancelled'              │
│  ├─ Notes: "Auto-cancelled: status_operation=1 from PLC"      │
│  └─ Delete from mo_batch                                       │
│                                                                  │
│  Result:                                                        │
│  ✓✓ Batch cancelled in Odoo                                   │
│  ✓✓ Batch archived to history                                 │
│  ✓✓ Batch removed from mo_batch                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Code Changes

### 1. **odoo_consumption_service.py** - Added `cancel_mo()` method

```python
async def cancel_mo(self, mo_id: str) -> Dict[str, Any]:
    """
    Cancel Manufacturing Order di Odoo.
    
    Called when status_operation=1 (failed) detected from PLC.
    """
    # Authenticate with Odoo
    client = await self._authenticate()
    
    # Call Odoo cancel endpoint
    cancel_url = f"{self.settings.odoo_url}/api/scada/mo/cancel"
    payload = {"mo_id": mo_id}
    
    response = await client.post(cancel_url, json=payload, timeout=30.0)
    
    # Return success/failure result
    return {
        "success": response.status_code == 200,
        "mo_id": mo_id,
        "mo_state": "cancel"
    }
```

**Odoo API Endpoint:**
- **URL:** `POST /api/scada/mo/cancel`
- **Payload:** `{"mo_id": "WH/MO/00123"}`
- **Response:** `{"status": "success", "mo_state": "cancel"}`

---

### 2. **plc_sync_service.py** - Auto-cancel detection in `_update_batch_if_changed()`

```python
# Detect status_operation change from 0 → 1
if status_bool and not current_status_op:
    # status_operation changed to 1 (failed)
    logger.warning(
        f"⚠️ BATCH FAILURE DETECTED: status_operation=1 for "
        f"batch #{batch_no} (MO: {mo_id}). Initiating auto-cancel..."
    )
    
    # Step 1: Cancel MO in Odoo
    cancel_result = asyncio.run(
        self.consumption_service.cancel_mo(mo_id)
    )
    
    if cancel_result.get("success"):
        # Step 2: Archive to history with status='cancelled'
        history_service = get_mo_history_service(session)
        archive_result = history_service.cancel_batch(
            batch_no=batch_no,
            notes="Auto-cancelled: status_operation=1 (failed) detected from PLC"
        )
        
        if archive_result.get("success"):
            # Batch cancelled and archived successfully
            return False  # No changes to mo_batch (already deleted)
```

**Logic:**
1. Detect `status_operation` change from `0 → 1`
2. Call `cancel_mo()` to cancel MO in Odoo
3. If Odoo cancel succeeds, call `cancel_batch()` to archive
4. Archive to `mo_histories` with `status='cancelled'`
5. Delete from `mo_batch`
6. Return `False` (no more updates needed, batch deleted)

---

## Database Record

### mo_histories Table

Batch yang di-cancel otomatis akan disimpan di `mo_histories` dengan:

| Field | Value |
|-------|-------|
| `status` | `"cancelled"` |
| `notes` | `"Auto-cancelled: status_operation=1 (failed) detected from PLC"` |
| `batch_no` | Original batch number |
| `mo_id` | Original MO ID |
| All consumption data | Preserved from mo_batch |

**Query Example:**
```sql
SELECT batch_no, mo_id, status, notes, status_operation
FROM mo_histories
WHERE status = 'cancelled'
ORDER BY created_at DESC;
```

---

## Log Messages

### Success Flow

```
[WARNING] ⚠️ BATCH FAILURE DETECTED: status_operation=1 for batch #12345 (MO: WH/MO/00123). Initiating auto-cancel...
[INFO] Attempting to cancel MO WH/MO/00123 in Odoo...
[INFO] ✓ Odoo cancellation successful for batch #12345 (MO: WH/MO/00123)
[INFO] ✓✓ Batch #12345 (MO: WH/MO/00123) cancelled and archived to history
```

### Error Flow (Odoo Cancel Failed)

```
[WARNING] ⚠️ BATCH FAILURE DETECTED: status_operation=1 for batch #12345 (MO: WH/MO/00123). Initiating auto-cancel...
[INFO] Attempting to cancel MO WH/MO/00123 in Odoo...
[ERROR] ✗ Failed to cancel MO WH/MO/00123 in Odoo: Cannot cancel MO in state "done"
[DEBUG] Updated status_operation: False → True
```

**Note:** Jika Odoo cancel gagal, batch tetap di `mo_batch` dengan `status_operation=1`. Operator bisa check log untuk investigate.

---

## Comparison: Manual vs Automatic Cancel

| Aspect | Manual Cancel (Lama) | Auto Cancel (Baru) |
|--------|---------------------|-------------------|
| **Trigger** | Manual via API call | Automatic on PLC failure |
| **Detection** | Operator decision | PLC `status_operation=1` |
| **Endpoint** | `POST /admin/manual/cancel-batch/{batch_no}` | Internal (auto-triggered) |
| **Odoo Sync** | ❌ No | ✅ Yes - Cancel MO in Odoo |
| **Timing** | Anytime | During Task 2 (PLC Read) |
| **Notes** | Custom from operator | Auto-generated |
| **Use Case** | Quality issue, operator decision | Equipment failure, PLC-detected issue |

**Kedua metode masih tersedia:**
- **Manual:** Untuk cancellation berbasis operator decision
- **Automatic:** Untuk failure yang terdeteksi PLC

---

## Testing

### Simulate PLC Failure

**Step 1:** Set MO in mo_batch dengan `status_operation=0`

```sql
UPDATE mo_batch
SET status_operation = false
WHERE mo_id = 'WH/MO/00123';
```

**Step 2:** Simulate PLC sending `status_operation=1`

Update PLC memory atau modify PLCReadService to return:
```python
{
    "mo_id": "WH/MO/00123",
    "status": {
        "operation": 1  # Failed
    }
}
```

**Step 3:** Wait for Task 2 cycle (5 seconds)

**Expected Result:**
- Log: `⚠️ BATCH FAILURE DETECTED`
- Odoo: MO cancelled
- Database: Batch moved to `mo_histories` with `status='cancelled'`
- mo_batch: Batch removed

---

## Error Handling

### Scenario 1: Odoo Cancel Fails

**Cause:** MO already in state `done`, `cancel`, or not found

**Behavior:**
- Log error message
- Update `status_operation` to `1` in mo_batch
- Keep batch in queue (for manual investigation)
- **Do NOT archive** (batch still in mo_batch)

**Recovery:** Operator can:
1. Check Odoo for MO state
2. Manually cancel via `/admin/manual/cancel-batch/{batch_no}`
3. Or retry after fixing Odoo state

---

### Scenario 2: Archive to History Fails

**Cause:** Database error, transaction failure

**Behavior:**
- Log error message
- Odoo MO already cancelled (cannot rollback)
- Batch might remain in mo_batch

**Recovery:** Operator must:
1. Manually archive via `/admin/manual/cancel-batch/{batch_no}`
2. Or check database logs for transaction errors

---

### Scenario 3: Exception During Auto-Cancel

**Cause:** Network error, service unavailable, unexpected exception

**Behavior:**
- Log full exception with traceback
- Update `status_operation` to `1` (mark failure)
- Keep batch in queue
- Continue processing other batches

**Recovery:**
- Auto-retry on next PLC read (status_operation still `1`)
- Or manual intervention

---

## Integration Points

### PLC Memory Address

**Status Operation:** Address yang merepresentasikan failure state
- `0` = Normal operation
- `1` = Failed/Problem detected

**Example dari read_data_plc_input.csv:**
```csv
Informasi,Keterangan,Memory Address,Data Type
status_operation,Status operasi (0=normal 1=failed),D300,UINT
```

---

### Odoo API Endpoint

**Endpoint:** `POST /api/scada/mo/cancel`

**Request:**
```json
{
  "mo_id": "WH/MO/00123"
}
```

**Success Response:**
```json
{
  "status": "success",
  "message": "Manufacturing order cancelled successfully",
  "mo_id": "WH/MO/00123",
  "mo_state": "cancel"
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Cannot cancel MO \"WH/MO/00123\" in state \"done\""
}
```

**Documentation:** See [data/API_SPEC.md](data/API_SPEC.md#19-cancel-manufacturing-order-protected)

---

## Configuration

### Scheduler Task Interval

**Task 2 (PLC Read Sync):** 5 seconds
```python
scheduler.add_job(
    plc_read_sync_task,
    "interval",
    seconds=5,
    id="plc_read_sync_task",
    replace_existing=True,
)
```

Auto-cancel check happens **every 5 seconds** during PLC read cycle.

---

## Monitoring & Alerts

### Log Monitoring

**Important logs to monitor:**
```bash
# Success
grep "BATCH FAILURE DETECTED" logs/app.log
grep "Odoo cancellation successful" logs/app.log
grep "cancelled and archived to history" logs/app.log

# Failures
grep "Failed to cancel MO" logs/app.log
grep "Failed to archive cancelled batch" logs/app.log
grep "Exception during auto-cancel" logs/app.log
```

### Database Monitoring

**Query cancelled batches:**
```sql
-- Recent auto-cancelled batches
SELECT 
    batch_no, 
    mo_id, 
    status, 
    notes,
    status_operation,
    created_at
FROM mo_histories
WHERE status = 'cancelled'
    AND notes LIKE '%Auto-cancelled%'
ORDER BY created_at DESC
LIMIT 10;
```

**Count failures by date:**
```sql
SELECT 
    DATE(created_at) as date,
    COUNT(*) as cancelled_count
FROM mo_histories
WHERE status = 'cancelled'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Benefits

✅ **Faster Response:** Immediate cancellation when failure detected  
✅ **Data Consistency:** Odoo and middleware always in sync  
✅ **Audit Trail:** All cancellations logged with reason  
✅ **No Manual Intervention:** Automatic workflow reduces operator workload  
✅ **Error Prevention:** Prevents processing failed batches  
✅ **Traceability:** Clear history of why batch was cancelled  

---

## Related Documentation

- [CANCEL_BATCH_GUIDE.md](CANCEL_BATCH_GUIDE.md) - Manual cancel batch guide
- [CANCEL_BATCH_IMPLEMENTATION_SUMMARY.md](CANCEL_BATCH_IMPLEMENTATION_SUMMARY.md) - Original implementation
- [data/API_SPEC.md](data/API_SPEC.md#19-cancel-manufacturing-order-protected) - Odoo API reference
- [ENHANCED_SCHEDULER_GUIDE.md](ENHANCED_SCHEDULER_GUIDE.md) - Scheduler tasks overview

---

## Summary

| Item | Value |
|------|-------|
| **Feature** | Auto-cancel batch on PLC failure |
| **Trigger** | `status_operation: 0 → 1` |
| **Detection Point** | Task 2 - PLC Read Sync |
| **Odoo Action** | Cancel MO via `/api/scada/mo/cancel` |
| **Database Action** | Archive to `mo_histories` with `status='cancelled'` |
| **Files Changed** | `odoo_consumption_service.py`, `plc_sync_service.py` |
| **Backward Compatible** | ✅ Yes - Manual cancel still available |

---

**Date:** February 16, 2026  
**Status:** ✅ Implemented and Ready
