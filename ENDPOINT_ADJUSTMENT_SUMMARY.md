# Equipment Failure API - Endpoint Adjustment Summary

## Perubahan yang Dilakukan

### 1. ✓ Endpoint Path Updated
- **Old:** `POST /api/scada/failure-report`
- **New:** `POST /api/scada/equipment-failure`

### 2. ✓ Response Structure Updated

#### Before:
```json
{
  "status": "success",
  "message": "Failure report created",
  "data": {
    "id": 1,
    "equipment_code": "PLC01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15 08:30:00"
  }
}
```

#### After (Sesuai Spek):
```json
{
  "status": "success",
  "message": "Equipment failure report created",
  "data": {
    "id": 1,
    "equipment_id": 1,
    "equipment_code": "PLC01",
    "equipment_name": "Main PLC - Injection Machine 01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15T08:30:00"
  }
}
```

### 3. ✓ Date Format Updated
- **Before:** `2026-02-15 08:30:00` (datetime string)
- **After:** `2026-02-15T08:30:00` (ISO 8601 format)

### 4. ✓ Response Data Fields Added
- ✓ `equipment_id` - ID dari equipment master
- ✓ `equipment_name` - Nama lengkap equipment

---

## Files Modified

### 1. **app/api/routes/scada.py**
- Function name changed: `create_failure_report()` → `create_equipment_failure()`
- Endpoint path changed: `/api/scada/failure-report` → `/api/scada/equipment-failure`
- Updated docstring dengan response format baru

### 2. **app/services/equipment_failure_service.py**
- Updated `create_failure_report()` method:
  - Changed API URL to new endpoint
  - Added `_format_failure_report_response()` method untuk format response
  - Updated response message ke "Equipment failure report created"
  - Updated logging messages
  - Converts date format ke ISO 8601

### 3. **app/schemas/equipment_failure.py**
- Updated `FailureReportResponse` schema:
  - Added field `equipment_id: int`
  - Changed `equipment_name` dari Optional ke required
  - Changed `date` dari `datetime` ke `str` (ISO 8601)
  - Removed `created_at` field

### 4. **data/API_SPEC.md**
- Updated endpoint specification
- Updated request/response examples
- Updated cURL example

### 5. **app/core/scheduler.py**
- Updated logging to show new endpoint path

---

## Response Format Transformation

### New Helper Method:
```python
def _format_failure_report_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Format Odoo response ke struktur standard API."""
    # Converts datetime strings ke ISO 8601 format
    # Returns dict dengan: id, equipment_id, equipment_code, 
    #                      equipment_name, description, date
```

---

## API Contract (Spesifikasi Baru)

### Endpoint
```
POST /api/scada/equipment-failure
```

### Request
```json
{
  "equipment_code": "PLC01",
  "description": "Motor overload saat proses mixing",
  "date": "2026-02-15 08:30:00"
}
```

### Response (Success)
```json
{
  "status": "success",
  "message": "Equipment failure report created",
  "data": {
    "id": 1,
    "equipment_id": 1,
    "equipment_code": "PLC01",
    "equipment_name": "Main PLC - Injection Machine 01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15T08:30:00"
  }
}
```

### Response (Error)
```json
{
  "status": "error",
  "message": "Equipment with code \"PLC01\" not found"
}
```

---

## Backward Compatibility

⚠️ **Note:** Old endpoint `/api/scada/failure-report` has been replaced with `/api/scada/equipment-failure`

If you need to maintain backward compatibility, you can keep both endpoints by:
1. Creating an alias route that points to the same handler
2. Or keep the old endpoint alongside the new one

---

## Testing

### Using cURL:
```bash
# Test new endpoint
curl -X POST http://localhost:8009/api/scada/equipment-failure \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_code": "PLC01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15 08:30:00"
  }'
```

### Using Python:
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8009/api/scada/equipment-failure",
        json={
            "equipment_code": "PLC01",
            "description": "Motor overload saat proses mixing",
            "date": "2026-02-15 08:30:00"
        }
    )
    print(response.json())
```

---

## Validation Checklist

- [x] Endpoint path updated
- [x] Response schema updated
- [x] Date format converted to ISO 8601
- [x] equipment_id added to response
- [x] equipment_name added to response
- [x] Message updated
- [x] Logging updated
- [x] API spec documentation updated
- [x] Python syntax validated
- [x] Helper method for format conversion created

---

## Summary

✓ Endpoint sekarang sesuai spesifikasi: `/api/scada/equipment-failure`
✓ Response format sesuai spek dengan equipment_id dan equipment_name
✓ Date format ISO 8601 diimplementasikan
✓ Semua file sudah updated dan validated
✓ Siap untuk testing dan deployment

