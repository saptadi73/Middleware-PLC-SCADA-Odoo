# Consumption dan Mark Done API - Usage Guide

Dokumentasi lengkap untuk menggunakan consumption update dan mark done endpoints.

## Overview

Setelah membaca data dari PLC dan menyimpan ke database, middleware ini juga update consumption ke Odoo dan mark MO sebagai done.

### Workflow

```
PLC Read Data (dengan silo_a, silo_b, silo_c format)
    ↓
Update mo_batch table
    ↓
Convert SCADA tag (silo_a) → Odoo code (silo101) via silo_data.json
    ↓
Update consumption ke Odoo (untuk setiap silo/component)
    ↓
Check status_manufacturing
    ↓
Jika status_manufacturing = 1 → Mark MO as done
```

## Silo Mapping Reference

**Location**: `app/reference/silo_data.json`

Mapping lengkap antara internal representation dengan Odoo equipment codes:

```
Silo ID | SCADA Tag | Odoo Code | Odoo Name
--------|-----------|-----------|----------
101     | silo_a    | silo101   | SILO A
102     | silo_b    | silo102   | SILO B
103     | silo_c    | silo103   | SILO C
104     | silo_d    | silo104   | SILO D
105     | silo_e    | silo105   | SILO E
106     | silo_f    | silo106   | SILO F
107     | silo_g    | silo107   | SILO G
108     | silo_h    | silo108   | SILO H
109     | silo_i    | silo109   | SILO I
110     | silo_j    | silo110   | SILO J
111     | silo_k    | silo111   | SILO K
112     | silo_l    | silo112   | SILO L
113     | silo_m    | silo113   | SILO M
```

**Key Points**:
- **SCADA Tag** (silo_a, silo_b, etc): Internal representation untuk PLC & database
- **Odoo Code** (silo101, silo102, etc): Equipment code yang digunakan di Odoo API
- Service otomatis convert antara keduanya menggunakan silo_data.json

---

## API Endpoints

### RECOMMENDED: Odoo's Update-with-Consumptions (Efficient)

**Endpoint**: `POST /api/scada/mo/update-with-consumptions` (Odoo endpoint)

This is the **recommended approach** untuk single API call yang handle semua silos.

**Request** (menggunakan Odoo codes - silo101, silo102, etc):

```json
{
  "mo_id": "WH/MO/00001",
  "quantity": 2000,
  "silo101": 825,
  "silo102": 600,
  "silo103": 375,
  "silo104": 240.25
}
```

**Response - Success**:
```json
{
  "status": "success",
  "message": "MO updated successfully",
  "mo_id": "WH/MO/00001",
  "consumed_items": [
    {
      "equipment_code": "silo101",
      "equipment_name": "SILO A",
      "applied_qty": 825.0,
      "move_ids": [123],
      "products": ["Pollard Angsa"]
    },
    {
      "equipment_code": "silo102",
      "equipment_name": "SILO B",
      "applied_qty": 600.0,
      "move_ids": [124],
      "products": ["Kopra mesh"]
    }
  ],
  "errors": []
}
```

**Service Method**:
```python
from app.services.odoo_consumption_service import get_consumption_service

service = get_consumption_service()

# Format consumption dengan odoo codes (silo101, silo102)
consumption = {
    "silo101": 825,
    "silo102": 600,
    "silo103": 375
}

result = await service.update_consumption_with_odoo_codes(
    mo_id="WH/MO/00001",
    consumption_data=consumption,
    quantity=2000  # optional
)
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/update-with-consumptions \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mo_id": "WH/MO/00001",
    "quantity": 2000,
    "silo101": 825,
    "silo102": 600,
    "silo103": 375,
    "silo104": 240.25
  }'
```

#### Automatic SCADA Tag Conversion

Service juga support input menggunakan SCADA tags (silo_a, silo_b, etc) yang otomatis convert ke Odoo codes:

```python
# Input dengan SCADA tags
consumption = {
    "silo_a": 825,
    "silo_b": 600,
    "silo_c": 375
}

result = await service.update_consumption_with_odoo_codes(
    mo_id="WH/MO/00001",
    consumption_data=consumption  # Auto-convert ke silo101, silo102, silo103
)
```

---

### Alternative: Individual Consumption Endpoints

For more granular control atau testing individual silos, dapat menggunakan:

#### 1. Update Consumption untuk Single/Multiple Silos

**Endpoint:** `POST /consumption/update` (Middleware endpoint)

**Request:**
```json
{
  "mo_id": "MO/2025/001",
  "equipment_id": "PLC01",
  "consumption_data": {
    "silo_a": 50.5,
    "silo_b": 25.3,
    "silo_c": 10.0
  },
  "timestamp": "2025-02-13T10:30:00"
}
```

**Response - Success:**
```json
{
  "status": "success",
  "message": "Consumption updated successfully",
  "data": {
    "success": true,
    "mo_id": "MO/2025/001",
    "equipment_id": "PLC01",
    "items_updated": 3,
    "details": [
      {
        "product": "silo_a",
        "quantity": 50.5,
        "status": "success",
        "message": "Material consumption applied to MO moves"
      }
    ]
  }
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8000/consumption/update \
  -H "Content-Type: application/json" \
  -d '{
    "mo_id": "MO/2025/001",
    "equipment_id": "PLC01",
    "consumption_data": {
      "silo_a": 50.5,
      "silo_b": 25.3,
      "silo_c": 10.0
    }
  }'
```

---

#### 2. Mark Manufacturing Order as Done

**Endpoint:** `POST /consumption/mark-done` (Middleware endpoint)

**Request:**
```json
{
  "mo_id": "MO/2025/001",
  "finished_qty": 1000.0,
  "equipment_id": "PLC01",
  "auto_consume": true,
  "message": "Production completed successfully"
}
```

**Response - Success:**
```json
{
  "status": "success",
  "message": "Manufacturing order marked as done",
  "data": {
    "success": true,
    "mo_id": "MO/2025/001",
    "finished_qty": 1000.0,
    "message": "Manufacturing order marked as done"
  }
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8000/consumption/mark-done \
  -H "Content-Type: application/json" \
  -d '{
    "mo_id": "MO/2025/001",
    "finished_qty": 1000.0,
    "equipment_id": "PLC01",
    "auto_consume": true
  }'
```

---

#### 3. Process Batch Consumption (Comprehensive)

**Endpoint:** `POST /consumption/batch-process` (Middleware endpoint)

Endpoint comprehensive yang:
- Update consumption untuk semua silo yang punya data
- Auto mark-done jika `status_manufacturing = 1`

**Request:**
```json
{
  "mo_id": "MO/2025/001",
  "equipment_id": "PLC01",
  "batch_data": {
    "consumption_silo_a": 50.5,
    "consumption_silo_b": 25.3,
    "consumption_silo_c": 10.0,
    "status_manufacturing": 1,
    "actual_weight_quantity_finished_goods": 1000.0
  }
}
```

**Response - Success:**
```json
{
  "status": "success",
  "message": "Batch consumption processed successfully",
  "data": {
    "success": true,
    "mo_id": "MO/2025/001",
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

**cURL Example:**
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
      "actual_weight_quantity_finished_goods": 1000.0
    }
  }'
```

---

## Menggunakan Silo Mapping dalam Service

```python
from app.services.odoo_consumption_service import get_consumption_service

service = get_consumption_service()

# 1. Get semua mapping
mapping = service.get_silo_mapping()
# Returns: {101: {"odoo_code": "silo101", "scada_tag": "silo_a"}, ...}

# 2. Get mapping by ID
silo_101 = service.get_silo_by_id(101)
# Returns: {"odoo_code": "silo101", "scada_tag": "silo_a"}

# 3. Get mapping by SCADA tag
silo_a = service.get_silo_by_scada_tag("silo_a")
# Returns: {"odoo_code": "silo101", "scada_tag": "silo_a"}
```

### Data Flow Dengan Silo Mapping

Contoh workflow PLC read → Odoo update:

```
Step 1: PLC Read (menggunakan SCADA tags)
┌─────────────────────────────────────────┐
│ PLC Data Response                       │
│ {                                       │
│   "mo_id": "WH/MO/00001",              │
│   "consumption_silo_a": 825,   ← SCADA │
│   "consumption_silo_b": 600,   ← tags  │
│   "consumption_silo_c": 375            │
│ }                                       │
└─────────────────────────────────────────┘
                ↓
Step 2: Store to Database mo_batch
┌─────────────────────────────────────────┐
│ mo_batch table (silo_a format)          │
│ mo_id: WH/MO/00001                      │
│ consumption_silo_a: 825                 │
│ consumption_silo_b: 600                 │
│ consumption_silo_c: 375                 │
└─────────────────────────────────────────┘
                ↓
Step 3: Convert & Update Odoo (via update-with-consumptions)
┌─────────────────────────────────────────┐
│ Service converts using silo_data.json:  │
│ silo_a (id=101) → silo101               │
│ silo_b (id=102) → silo102               │
│ silo_c (id=103) → silo103               │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ POST /api/scada/mo/update-with-consumptions
│ {                                       │
│   "mo_id": "WH/MO/00001",              │
│   "silo101": 825,  ← Odoo codes        │
│   "silo102": 600,                       │
│   "silo103": 375                        │
│ }                                       │
└─────────────────────────────────────────┘
                ↓
Step 4: Odoo Updates
┌─────────────────────────────────────────┐
│ Odoo Equipment (SILO A, SILO B, SILO C)│
│ Stock Moves: quantity_done += consumed  │
│ Manufacturing Order: status updated     │
└─────────────────────────────────────────┘
```

---

---

## Error Handling

### Common Errors

**1. MO tidak ditemukan di Odoo**
```json
{
  "status": "error",
  "message": "MO not found: MO/2025/001"
}
```

**2. Equipment tidak valid**
```json
{
  "status": "error",
  "message": "Equipment not found: INVALID_EQUIPMENT"
}
```

**3. Authentication gagal**
```json
{
  "status": "error",
  "message": "Failed to authenticate with Odoo"
}
```

**4. Consumption quantity tidak valid**
```json
{
  "status": "error",
  "message": "Quantity must be > 0"
}
```

---

## Mark Done Mechanism

System otomatis mark MO sebagai done saat `status_manufacturing = 1`:

### Trigger Condition
```python
if batch.status_manufacturing == 1:
    # Auto mark MO as done
    await service.mark_mo_done(
        mo_id=batch.mo_id,
        finished_qty=batch.actual_weight_quantity_finished_goods,
        auto_consume=True  # Auto-apply remaining material consumption
    )
```

### Mark Done Process

```
Manufacturing Data:
┌─────────────────────────────────────────┐
│ status_manufacturing = 1  ← Detected    │
│ actual_weight_qty_finished = 1000       │
└─────────────────────────────────────────┘
        ↓
POST /api/scada/mo/mark-done
┌─────────────────────────────────────────┐
│ {                                       │
│   "mo_id": "WH/MO/00001",              │
│   "finished_qty": 1000.0,              │
│   "auto_consume": true,                │
│   "date_end_actual": timestamp          │
│ }                                       │
└─────────────────────────────────────────┘
        ↓
Odoo Updates:
┌─────────────────────────────────────────┐
│ 1. Set MO state = "done"               │
│ 2. Set date_end_actual                 │
│ 3. Optional: Auto-apply remaining      │
│    material consumption                │
│ 4. Create production moves              │
└─────────────────────────────────────────┘
```

---

## Integration dengan PLC Sync

Untuk full workflow integration dengan PLC read, gunakan method di `plc_sync_service.py`:

### Method 1: Combined (Recommended)

Single method yang handle semua steps:

```python
from app.services.plc_sync_service import get_plc_sync_service

# One call yang:
# 1. Read PLC
# 2. Update batch
# 3. Sync consumption ke Odoo (update-with-consumptions)
# 4. Mark done (jika status_manufacturing = 1)
sync_service = get_plc_sync_service()
result = sync_service.sync_from_plc_with_consumption()

if result['success']:
    print(f"Batch updated: {result['batch_updated']}")
    print(f"Consumption sync: {result['consumption_sync']}")
    # Output:
    # {
    #   "success": true,
    #   "batch_updated": true,
    #   "consumption_sync": {
    #     "success": true,
    #     "endpoint": "update-with-consumptions",
    #     "consumed_items": [...],
    #     "errors": []
    #   }
    # }
```

### Method 2: Sequential (Update batch dulu, sync consumption terpisah)

```python
from app.services.plc_sync_service import get_plc_sync_service

# Step 1: Update batch dari PLC data
sync_service = get_plc_sync_service()
result = sync_service.sync_from_plc()

# Step 2: Setelah batch updated, sync consumption ke Odoo
if result['success']:
    batch = ... # Get updated batch from DB
    consumption_result = await sync_service.sync_consumption_to_odoo(batch)
    
    # consumption_result includes:
    # - consumption_updated: bool
    # - consumption_details: dict
    # - mo_marked_done: bool
    # - mark_done_details: dict
```

### Method 3: Using Service Directly

```python
from app.services.odoo_consumption_service import get_consumption_service
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch

service = get_consumption_service()

# For efficient single API call to Odoo:
result = await service.update_consumption_with_odoo_codes(
    mo_id="WH/MO/00001",
    consumption_data={
        "silo101": 825,  # Odoo codes directly
        "silo102": 600,
        "silo103": 375
    },
    quantity=2000
)

# Service automatically:
# 1. Converts if needed (silo_a → silo101 via silo_data.json)
# 2. Sends to Odoo's /api/scada/mo/update-with-consumptions endpoint
# 3. Returns detailed response with consumed_items
```

---

1. **Batch Processing**: Gunakan endpoint `/consumption/batch-process` untuk full workflow, jangan split ke multiple endpoints.

2. **Skip Zero Consumption**: Service otomatis skip consumption dengan quantity <= 0, tidak perlu filter di client.

3. **Timestamp**: Jika tidak provide timestamp, service otomatis gunakan current time. Format: ISO 8601 (e.g., "2025-02-13T10:30:00").

4. **Auto Consume**: Saat mark-done, set `auto_consume: true` supaya Odoo auto-apply remaining material consumption.

5. **Error Recovery**: Jika update consumption gagal untuk beberapa silo, response masih success tapi dengan error detail di `details` array. Check `details[i].status` untuk tiap item.

6. **Monitoring**: Log setiap consumption update dan mark done untuk audit trail. Service ini otomatis log ke application logs.

---

## Testing

```bash
# Run test file
python test_odoo_consumption.py

# Untuk integration test dengan real Odoo instance:
# 1. Uncomment async test functions di test file
# 2. Pastikan .env sudah set dengan:
#    - ODOO_BASE_URL
#    - ODOO_DB
#    - ODOO_USERNAME
#    - ODOO_PASSWORD
```

---

## Troubleshooting

### Q: Consumption tidak terupdate di Odoo

**A:** Check:
1. Odoo credentials di `.env` file
2. MO ID format benar (e.g., "MO/2025/001")
3. Product/silo tags valid di Odoo
4. Network connectivity ke Odoo server

### Q: Mark done gagal

**A:** Check:
1. `finished_qty` > 0
2. MO status masih "progress" (tidak bisa mark done MO yang sudah done)
3. Check Odoo logs untuk error detail

### Q: Silo mapping tidak load

**A:** Check:
1. `silo_data.json` exist di `app/reference/`
2. JSON format valid
3. File permissions readable

---
