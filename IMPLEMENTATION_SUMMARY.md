# Implementation Summary - Odoo Consumption & Mark Done Service

## Overview

Telah dibuat service lengkap untuk update consumption di Odoo dan mark MO sebagai done setelah membaca data dari PLC. Service ini terintegrasi dengan sistem existing yang already update database, dan sekarang juga update ke Odoo side dengan referensi silo mapping dari `silo_data.json`.

---

## What Was Created

### 1. **Core Service: `odoo_consumption_service.py`**

**File**: `app/services/odoo_consumption_service.py`

Service lengkap dengan 5 method utama:

#### Method 1: `update_consumption_with_odoo_codes()` - **Recommended**
- Update MO dengan consumption menggunakan Odoo endpoint `/api/scada/mo/update-with-consumptions`
- Single API call untuk semua silos (efficient)
- Input: consumption_data dengan `{odoo_code: quantity}` format (e.g., silo101: 825)
- Support automatic conversion dari SCADA tags (silo_a → silo101 via silo_data.json)
- Return detailed consumed_items dari Odoo response
- **Use case**: Recommended untuk production - paling efficient & powerful

#### Method 2: `update_consumption()`
- Update material consumption per hari-hari untuk single atau multiple silo ke Odoo
- Receive consumption data dalam format `{silo_tag: quantity, ...}`
- Return detailed result untuk setiap silo
- Note: Deprecated dalam favor method 1, tapi masih tersedia untuk backward compatibility

#### Method 3: `mark_mo_done()`
- Mark Manufacturing Order sebagai done di Odoo
- Require `finished_qty > 0`
- Support `auto_consume` flag untuk auto-apply remaining consumption
- Update dengan `date_end_actual` timestamp

#### Method 4: `process_batch_consumption()`
- Comprehensive method yang process semua silos & mark done
- Input: batch data dengan format `consumption_silo_{letter}: quantity`
- Auto detect `status_manufacturing` dan auto-mark done jika = 1
- Return combined result untuk consumption dan mark-done status

#### Method 5: Silo Mapping Support & Conversion
- `get_silo_mapping()` - Get semua silo mapping
- `get_silo_by_id()` - Lookup by silo ID
- `get_silo_by_scada_tag()` - Lookup by SCADA tag (e.g., "silo_a")
- `_convert_scada_tag_to_odoo_code()` - Convert silo_a → silo101 (auto used in method 1)
- `_convert_odoo_code_to_scada_tag()` - Convert silo101 → silo_a (untuk reverse mapping)
- Auto load dari `silo_data.json` saat initialization

**Key Features:**
- Async/await support untuk non-blocking HTTP calls ke Odoo
- Session-based authentication dengan Odoo
- Comprehensive error handling dan logging
- Singleton pattern untuk resource efficiency

---

### 2. **API Endpoints: `scada.py`**

**File**: `app/api/routes/scada.py`

Tiga endpoint baru ditambahkan:

#### Endpoint 1: `POST /consumption/update`
Update consumption untuk silo/component ke Odoo
- Input: mo_id, equipment_id, consumption_data dict
- Output: Detailed result untuk setiap silo update
- Use case: Manual consumption update atau testing

#### Endpoint 2: `POST /consumption/mark-done`
Mark MO sebagai done di Odoo
- Input: mo_id, finished_qty, equipment_id, auto_consume
- Output: Confirmation dengan date_end_actual
- Use case: Manual mark done atau testing

#### Endpoint 3: `POST /consumption/batch-process` - **Recommended**
Comprehensive endpoint untuk full workflow
- Input: batch_data dengan consumption & status fields
- Auto update consumption + auto mark done (if status_manufacturing = 1)
- Output: Combined result
- Use case: Primary endpoint untuk PLC sync integration

---

### 3. **PLC Sync Integration: `plc_sync_service.py`**

**File**: `app/services/plc_sync_service.py` (Enhanced)

Ditambahkan 2 method baru untuk Odoo consumption sync:

#### Method 1: `sync_consumption_to_odoo(batch)`
- Async method yang sync single batch ke Odoo
- Extract consumption dari batch untuk semua silo
- Call consumption service untuk process batch consumption
- Return result dengan consumption_updated & mo_marked_done status

#### Method 2: `sync_from_plc_with_consumption()` - **Recommended**
- Combined workflow: PLC read → batch update → Odoo sync
- Single method yang handle semua steps:
  1. Read data dari PLC
  2. Update mo_batch table
  3. Sync consumption ke Odoo
  4. Auto mark done (jika status_manufacturing = 1)
- Return comprehensive result

**Integration Flow:**
```
PLC Read
  ↓
Update mo_batch (existing)
  ↓
Sync consumption to Odoo (NEW)
  ↓
Check status_manufacturing
  ↓
Mark done in Odoo (NEW - if status = 1)
```

---

### 4. **Reference & Documentation**

#### A. `CONSUMPTION_API_GUIDE.md`
Comprehensive guide dengan:
- Overview & workflow diagram
- All 3 endpoint specifications
- Complete cURL examples
- Integration code snippets (both sequential & combined)
- Silo mapping usage examples
- Error handling guide
- Best practices
- Troubleshooting Q&A

#### B. `test_odoo_consumption.py`
Test file dengan:
- Silo mapping test (uncommented)
- Consumption update test (commented - requires Odoo)
- Mark MO done test (commented - requires Odoo)
- Batch consumption test (commented - requires Odoo)
- Notes untuk integration testing

---

## Silo Mapping Reference

**Location**: `app/reference/silo_data.json`

Current mapping (13 silos):

```
Silo ID | Odoo Code | SCADA Tag
--------|-----------|----------
101     | silo101   | silo_a
102     | silo102   | silo_b
103     | silo103   | silo_c
104     | silo104   | silo_d
105     | silo105   | silo_e
106     | silo106   | silo_f
107     | silo107   | silo_g
108     | silo108   | silo_h
109     | silo109   | silo_i
110     | silo110   | silo_j
111     | silo111   | silo_k
112     | silo112   | silo_l
113     | silo113   | silo_m
```

Service otomatis load & use mapping ini untuk consumption updates.

---

## Usage Examples

### Example 1: Via API - Comprehensive Batch Process

```bash
curl -X POST http://localhost:8000/consumption/batch-process \
  -H "Content-Type: application/json" \
  -d '{
    "mo_id": "MO/2025/001",
    "equipment_id": "PLC01",
    "batch_data": {
      "consumption_silo_a": 50.5,
      "consumption_silo_b": 25.3,
      "consumption_silo_c": 10.0,
      "status_manufacturing": 1,
      "actual_weight_quantity_finished_goods": 1000
    }
  }'
```

Response:
```json
{
  "status": "success",
  "message": "Batch consumption processed successfully",
  "data": {
    "consumption": {
      "consumption_updated": true,
      "consumption_details": { ... }
    },
    "mark_done": {
      "mo_marked_done": true,
      "mark_done_details": { ... }
    }
  }
}
```

### Example 2: Via Service - Combined PLC Sync

```python
from app.services.plc_sync_service import get_plc_sync_service

sync_service = get_plc_sync_service()
result = sync_service.sync_from_plc_with_consumption()

if result['success']:
    print(f"Batch updated: {result['batch_updated']}")
    print(f"Consumption synced: {result['consumption_sync']}")
```

### Example 3: Via Service - Step by Step

```python
from app.services.plc_sync_service import get_plc_sync_service
from app.db.session import SessionLocal
from sqlalchemy import select
from app.models.tablesmo_batch import TableSmoBatch

sync_service = get_plc_sync_service()

# Step 1: Read & update batch
result = sync_service.sync_from_plc()

if result['success']:
    # Step 2: Get updated batch
    with SessionLocal() as session:
        batch = session.execute(
            select(TableSmoBatch).where(
                TableSmoBatch.mo_id == result['mo_id']
            )
        ).scalar_one_or_none()
        
        # Step 3: Sync consumption ke Odoo
        consumption_result = await sync_service.sync_consumption_to_odoo(batch)
        print(f"Consumption result: {consumption_result}")
```

---

## Architecture Diagram

```
┌─────────────┐
│  PLC Data   │ (SCADA format: silo_a, silo_b, silo_c)
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│  PLCReadService      │ (reads FINS protocol)
│  read_batch_data()   │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ PLCSyncService       │ (existing: update mo_batch)
│ sync_from_plc()      │
│ _update_batch_if_changed()
└──────┬───────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ PLC Sync Service (NEW METHODS)          │
│ - sync_consumption_to_odoo() [async]  │
│ - sync_from_plc_with_consumption()      │
│ (convert SCADA → Odoo codes)           │
└──────┬──────────────────────────────────┘
       │
       ├─► OdooConsumptionService [async]
       │   ├─ update_consumption_with_odoo_codes()  ← RECOMMENDED
       │   │  (efficient: single API call)
       │   └─ mark_mo_done() & silo mapping
       │
       ├─► Convert SCADA tags → Odoo codes
       │   (silo_a → silo101 via silo_data.json)
       │
       ├─► Odoo API: /api/scada/mo/update-with-consumptions
       │   │ (Single call for all silos - EFFICIENT)
       │   └─► Auto apply consumption to stock moves
       │
       └─► Odoo API: /api/scada/mo/mark-done (if status=1)
            └─► Mark MO done + auto-apply remaining consumption
```

---

## Data Flow - Complete Workflow with Mark Done

**Recommended approach using update-with-consumptions endpoint:**

```
Step 1: PLC Reads Data (SCADA tag format - internal)
┌──────────────────────────────────────────────────┐
│ {                                                │
│   "mo_id": "WH/MO/00001",                       │
│   "consumption_silo_a": 825,    ← SCADA tags   │
│   "consumption_silo_b": 600,    (silo_a, etc)  │
│   "consumption_silo_c": 375,                    │
│   "status_manufacturing": 1,    ← Mark done?   │
│   "actual_weight_quantity_finished_goods": 1000 │
│ }                                                │
└──────────────────────────────────────────────────┘
                    ↓
Step 2: Update mo_batch Table (store internal format)
┌──────────────────────────────────────────────────┐
│ mo_batch record:                                 │
│ • mo_id: WH/MO/00001                           │
│ • consumption_silo_a: 825                       │
│ • consumption_silo_b: 600                       │
│ • consumption_silo_c: 375                       │
│ • status_manufacturing: 1                       │
│ • actual_weight_qty_finished: 1000              │
└──────────────────────────────────────────────────┘
                    ↓
Step 3: Convert & Call Odoo (1 efficient API call)
┌──────────────────────────────────────────────────┐
│ Service converts using silo_data.json:           │
│ • silo_a (id=101) → silo101 (Odoo code)         │
│ • silo_b (id=102) → silo102                     │
│ • silo_c (id=103) → silo103                     │
└──────────────────────────────────────────────────┘
                    ↓
POST /api/scada/mo/update-with-consumptions
┌──────────────────────────────────────────────────┐
│ Request:                                         │
│ {                                                │
│   "mo_id": "WH/MO/00001",                       │
│   "silo101": 825,   ← Odoo equipment codes     │
│   "silo102": 600,   (converted in step 3)      │
│   "silo103": 375                                │
│ }                                                │
│                                                  │
│ Odoo Response:                                   │
│ {                                                │
│   "status": "success",                          │
│   "consumed_items": [                           │
│     {                                            │
│       "equipment_code": "silo101",              │
│       "applied_qty": 825,                       │
│       "products": ["Pollard Angsa"],            │
│       "move_ids": [123]                         │
│     },                                           │
│     ...                                          │
│   ]                                              │
│ }                                                │
└──────────────────────────────────────────────────┘
                    ↓
Step 4: Check & Auto Mark Done (if status_manufacturing = 1)
┌──────────────────────────────────────────────────┐
│ Condition met: status_manufacturing == 1         │
│ → Trigger marking done to Odoo                  │
└──────────────────────────────────────────────────┘
                    ↓
POST /api/scada/mo/mark-done
┌──────────────────────────────────────────────────┐
│ Request:                                         │
│ {                                                │
│   "mo_id": "WH/MO/00001",                       │
│   "finished_qty": 1000.0,  ← From PLC data     │
│   "auto_consume": true,    ← Auto-apply        │
│   "date_end_actual": "2025-02-13T10:30:00"    │
│ }                                                │
│                                                  │
│ Odoo Updates:                                    │
│ ✓ MO state: confirmed → done                   │
│ ✓ date_end_actual: set                         │
│ ✓ Stock moves created                          │
│ ✓ Remaining consumption applied (auto)         │
└──────────────────────────────────────────────────┘
                    ↓
Final Result:
┌──────────────────────────────────────────────────┐
│ ✓ Consumption applied: 825 + 600 + 375 = 1800  │
│ ✓ Stock moves updated (quantity_done)          │
│ ✓ MO manually marked as done                   │
│ ✓ Production finished goods: 1000              │
│ ✓ All completed in 2 API calls (EFFICIENT!)    │
└──────────────────────────────────────────────────┘
```

---

## Key Features

✅ **Async/Non-blocking**: Semua Odoo API calls adalah async, tidak block PLC read cycle

✅ **Session Management**: Auto authenticate dengan Odoo, reuse session untuk multiple calls

✅ **Error Resilience**: Jika update 1 silo gagal, tetap lanjut untuk silo lainnya

✅ **Silo Mapping**: Auto-load dari silo_data.json, support lookup by ID atau SCADA tag

✅ **Comprehensive Logging**: Setiap operation log dengan detail untuk audit trail

✅ **Type Safe**: Full type hints, validated dengan Pydantic models

✅ **Singleton Pattern**: Service instances di-cache untuk efficiency

✅ **Backward Compatible**: Existing PLC sync methods tetap work, methods baru optional

---

## Technology Stack

- **Framework**: FastAPI + Pydantic (API validation)
- **Database**: SQLAlchemy ORM (mo_batch table)
- **HTTP Client**: httpx (async HTTP)
- **Authentication**: Session-based cookies (Odoo compatible)
- **Reference Data**: JSON (silo_data.json)
- **Async**: asyncio (non-blocking operations)
- **Logging**: Python logging module

---

## Integration Checklist

- [x] Create OdooConsumptionService dengan method utama
- [x] Add 3 API endpoints di scada.py
- [x] Enhance PLCSyncService dengan Odoo integration methods
- [x] Load & manage silo mapping dari silo_data.json
- [x] Async/await support untuk non-blocking calls
- [x] Comprehensive error handling
- [x] Full logging untuk debugging
- [x] Complete API documentation (CONSUMPTION_API_GUIDE.md)
- [x] Test file dengan examples (test_odoo_consumption.py)
- [x] Type hints & validation
- [x] No syntax errors ✅

---

## Next Steps / Optional Enhancements

1. **Batch Processing**: Implement batch consumption update (multiple MOs in one call) untuk efficiency

2. **Retry Logic**: Add exponential backoff untuk Odoo API calls yang timeout

3. **Event Logging**: Store consumption/mark-done events ke database untuk audit trail

4. **Webhook Support**: Add endpoint untuk receive notifications dari Odoo saat MO status changed

5. **Performance Optimization**:
   - Cache Odoo session lebih lama (reuse across multiple sync cycles)
   - Batch API calls ke Odoo (combine multiple silos in 1 request)

6. **Testing**: Integration tests dengan real Odoo instance

7. **Monitoring**: Add metrics untuk consumption update success rate & latency

---

## Files Created/Modified

### New Files:
1. `app/services/odoo_consumption_service.py` (NEW service)
2. `test_odoo_consumption.py` (NEW test file)
3. `CONSUMPTION_API_GUIDE.md` (NEW documentation)

### Modified Files:
1. `app/api/routes/scada.py` (added 3 new endpoints + imports)
2. `app/services/plc_sync_service.py` (added integration methods + asyncio import)

### Reference Files (Existing - Used):
1. `app/reference/silo_data.json` (silo mapping)

---

## Configuration Required

Update `.env` dengan Odoo credentials (sudah ada, digunakan oleh service):

```
ODOO_BASE_URL=http://localhost:8069
ODOO_DB=your_database
ODOO_USERNAME=admin
ODOO_PASSWORD=admin
```

---

## Support & Debugging

1. Check logs untuk detailed error messages
2. Run `test_odoo_consumption.py` untuk verify silo mapping
3. Use API documentation di `CONSUMPTION_API_GUIDE.md` untuk endpoint details
4. Uncomment tests di test file untuk integration testing dengan real Odoo

---
