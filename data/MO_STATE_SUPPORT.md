# Endpoint Update Consumption - State Support

## ✅ State Yang Didukung

Endpoint `/api/scada/mo/update-with-consumptions` **BISA** update MO dengan state:

### 1. **CONFIRMED** ✅
- MO baru yang sudah di-confirm
- Belum ada consumption
- **Setelah update pertama** → state otomatis berubah ke **PROGRESS**

### 2. **PROGRESS** ✅  
- MO yang sudah dimulai produksi
- Sudah ada consumption sebelumnya
- **Bisa di-update berkali-kali** tanpa batasan
- State tetap PROGRESS

## 🧪 Test Results

### Test 1: MO dengan state 'confirmed'
```json
Request:
{
  "mo_id": "WH/MO/00004",
  "silo101": 25.0,
  "silo103": 30.0
}

Response:
{
  "status": "success",
  "mo_id": "WH/MO/00004",
  "mo_state": "progress",  ← Berubah dari 'confirmed' ke 'progress'
  "consumed_items": [...]
}
```

### Test 2: MO dengan state 'progress'
```json
Request:
{
  "mo_id": "WH/MO/00001",
  "silo101": 15.0,
  "silo102": 20.0
}

Response:
{
  "status": "success",
  "mo_id": "WH/MO/00001",
  "mo_state": "progress",  ← Tetap 'progress'
  "consumed_items": [...]
}
```

## 📋 Behavior Summary

| MO State | Bisa Update? | State Setelah Update |
|----------|--------------|---------------------|
| **draft** | ❓ Belum dicoba | Kemungkinan bisa |
| **confirmed** | ✅ YA | → **progress** (auto) |
| **progress** | ✅ YA | → **progress** (tetap) |
| **done** | ❓ Belum dicoba | Kemungkinan tidak bisa |
| **cancel** | ❌ TIDAK | N/A |

## 🔍 Cara Kerja

1. **Tidak ada validasi state** di kode
2. Selama MO ditemukan, akan di-update
3. Odoo secara otomatis mengelola state transition:
   - `confirmed` → `progress` saat ada consumption pertama
   - `progress` tetap `progress` saat update consumption

## 💡 Use Case

### Sequential Updates (SCADA Realtime)
```python
# Update 1 - MO masih confirmed
POST /api/scada/mo/update-with-consumptions
{
  "mo_id": "WH/MO/00005",
  "silo101": 100
}
# → State berubah ke 'progress'

# Update 2 - MO sudah progress (5 menit kemudian)
POST /api/scada/mo/update-with-consumptions
{
  "mo_id": "WH/MO/00005",
  "silo101": 150  # Tambah 50 kg lagi
}
# → State tetap 'progress'

# Update 3 - Update equipment lain
POST /api/scada/mo/update-with-consumptions
{
  "mo_id": "WH/MO/00005",
  "silo101": 200,  # Total sekarang 200
  "silo102": 80,   # Tambah equipment baru
  "silo103": 60
}
# → State tetap 'progress'
```

### Batch Update Multiple Equipment
```python
# Update sekaligus banyak equipment
POST /api/scada/mo/update-with-consumptions
{
  "mo_id": "WH/MO/00002",
  "silo101": 825,    # SILO A
  "silo102": 600,    # SILO B
  "silo103": 375,    # SILO C
  "silo104": 50,     # SILO D
  "silo105": 381.25  # SILO E
}
```

## ⚠️ Catatan Penting

### Replace Mode (Default)
Update consumption menggunakan **REPLACE mode**, bukan APPEND:

```python
# Update pertama
{"silo101": 100}  # Move quantity_done = 100

# Update kedua
{"silo101": 150}  # Move quantity_done = 150 (BUKAN 100+150=250)
```

Setiap update **mengganti nilai lama**, bukan menambah.

### State Transition
State otomatis berubah dari `confirmed` → `progress` karena:
- **Odoo behavior**: Saat ada consumption (quantity_done > 0) di raw materials
- **Tidak bisa dicegah**: Ini adalah fitur bawaan Odoo MRP

### Equipment Code Required
```python
# ✅ Berhasil - Equipment ditemukan
{"silo101": 100}  

# ❌ Gagal - Equipment tidak ada
{"silo999": 100}
→ Error: "silo999: Equipment not found"

# ⚠️ Skip - Equipment code tidak valid
{"": 100}
→ Diabaikan, tidak error
```

## 🔧 Test Scripts

### Test Update Berbagai State
```bash
python test_mo_states.py
```

### Test Update Lengkap
```bash
python test_mo_consumption_api.py
```

### Check MO Status
```bash
python check_mo_status.py
```

## 📚 Endpoint Documentation

**URL**: `POST /api/scada/mo/update-with-consumptions`  
**Auth**: Session Cookie (JSON-RPC)  
**Content-Type**: `application/json`

**Request Body**:
```json
{
  "jsonrpc": "2.0",
  "params": {
    "mo_id": "WH/MO/00001",
    "quantity": 2500,  // Optional: Update MO qty
    "silo101": 825,    // Equipment consumption
    "silo102": 600,
    // ... more equipment codes
  }
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "id": null,
  "result": {
    "status": "success",
    "message": "MO updated successfully",
    "mo_id": "WH/MO/00001",
    "mo_state": "progress",
    "consumed_items": [
      {
        "equipment_code": "silo101",
        "equipment_name": "SILO A",
        "applied_qty": 825.0,
        "move_ids": [45],
        "products": ["Pollard Angsa"]
      }
    ],
    "errors": []  // Optional: list of errors
  }
}
```

---

**Dibuat**: 15 Februari 2026  
**Status**: ✅ TESTED & VERIFIED
