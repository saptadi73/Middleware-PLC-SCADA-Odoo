# PLC Bidirectional Communication Testing Guide

Panduan lengkap untuk testing PLC Read/Write/Sync functionality dengan fokus pada **bidirectional communication** antara Middleware dan PLC.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Understanding Memory Areas](#understanding-memory-areas)
4. [Test Scripts](#test-scripts)
5. [Testing Workflow](#testing-workflow)
6. [Expected Results](#expected-results)
7. [Troubleshooting](#troubleshooting)
8. [MO Batch Process Test](#mo-batch-process-test)

---

## Overview

Testing bidirectional PLC communication melibatkan 3 komponen utama:

```
┌─────────────────────────────────────────────────────────────┐
│                    Testing Flow                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. WRITE TEST                                              │
│     Database (mo_batch) ──► PLC READ Area (D6001-D6058)    │
│     Script: test_write_read_area.py                        │
│                                                             │
│  2. READ TEST                                               │
│     PLC READ Area (D6001-D6058) ──► API Response           │
│     Script: test_plc_read.py                               │
│                                                             │
│  3. SYNC TEST                                               │
│     PLC READ Area (D6001-D6058) ──► Database (mo_batch)    │
│     Script: test_plc_sync.py                               │
│                                                             │
│  4. COMPLETE CYCLE TEST                                     │
│     All steps combined with verification                    │
│     Script: test_complete_cycle.py                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. Database Setup

Pastikan ada minimal 1 record di table `mo_batch`:

```sql
-- Check existing data
SELECT 
  batch_no, 
  mo_id, 
  finished_goods, 
  consumption,
  silo_a, consumption_silo_a,
  silo_b, consumption_silo_b
FROM mo_batch
WHERE batch_no = 1;
```

Jika kosong, jalankan:

```bash
# Fetch dari Odoo
python test_plc_write_from_odoo.py
```

### 2. Database Migration

Pastikan migration terbaru sudah diapply:

```bash
alembic upgrade head
```

Cek migration status:

```bash
alembic current
```

Expected output:

```
20260212_0007 (head)
```

### 3. PLC Connection

Test koneksi PLC:

```bash
curl http://localhost:8000/api/plc/config
```

Response harus success:

```json
{
  "status": "success",
  "data": {
    "plc_ip": "192.168.1.2",
    "plc_port": 9600,
    "plc_protocol": "udp"
  }
}
```

### 4. Server Running

Start FastAPI server:

```bash
python -m uvicorn app.main:app --reload
```

---

## Understanding Memory Areas

### PLC Memory Layout

```
┌───────────────────────────────────────────────────────────────┐
│                     PLC DM Memory                             │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  D6001-D6058  │ READ AREA (Production Feedback)              │
│               │ ✓ Current MO being processed                 │
│               │ ✓ Actual consumption per silo                │
│               │ ✓ Real-time status (manufacturing/operation) │
│               │ ✓ Actual finished goods weight               │
│               │ Mapping: READ_DATA_PLC_MAPPING.json          │
│               │                                              │
├───────────────┴──────────────────────────────────────────────┤
│                                                               │
│  D7000-D7418  │ WRITE AREA (Production Commands)            │
│               │ ✓ Queue of 30 MO batches (BATCH01-30)       │
│               │ ✓ Planned consumption                        │
│               │ ✓ Production parameters                      │
│               │ Mapping: MASTER_BATCH_REFERENCE.json         │
│               │                                              │
└───────────────────────────────────────────────────────────────┘
```

### Field Mapping: Database ↔ PLC READ Area

| Database Field | PLC Field | DM Address | Data Type | Scale |
|----------------|-----------|------------|-----------|-------|
| `mo_id` | NO-MO | D6001-6008 | ASCII | - |
| `finished_goods` | finished_goods | D6017-6024 | ASCII | - |
| `consumption` | Quantity Goods_id | D6025 | REAL | 1.0 |
| `silo_a` | SILO ID 101 | D6026 | REAL | 1.0 |
| `consumption_silo_a` | SILO 1 Consumption | D6027 | REAL | 10.0 |
| `silo_b` | SILO ID 102 | D6028 | REAL | 1.0 |
| `consumption_silo_b` | SILO 2 Consumption | D6029 | REAL | 10.0 |
| ... | ... | ... | ... | ... |
| `status_manufacturing` | status manufaturing | D6056 | boolean | - |
| `status_operation` | Status Operation | D6057 | boolean | - |
| `actual_weight_quantity_finished_goods` | weight_finished_good | D6058 | REAL | 1.0 |

**Important Notes:**

1. **Scale Factor**: Consumption fields menggunakan scale 10.0
   - Database value: `825.5` kg
   - PLC value: `8255` (825.5 × 10)
   - When reading back: PLC `8255` ÷ 10 = `825.5` kg

2. **ASCII Encoding**: 2 characters per word, big-endian
   - "WH/MO/00002" → 8 words (16 bytes)

3. **Boolean**: 
   - True → PLC value `1`
   - False → PLC value `0`

---

## Test Scripts

### 1. test_write_read_area.py

**Purpose**: Write data dari database ke PLC READ area untuk simulasi.

**What it does:**
- Read `batch_no=1` dari table `mo_batch`
- Convert data to PLC format (dengan scale factor)
- Write ke PLC memory D6001-D6058
- Menggunakan mapping dari `READ_DATA_PLC_MAPPING.json`

**Usage:**

```bash
python test_write_read_area.py
```

**Output:**

```
================================================================================
TEST WRITE TO READ_DATA_PLC_MAPPING AREA (D6001-D6058)
================================================================================

[1] Reading batch_no=1 from database...
✓ Found batch: WH/MO/00002
  Product: JF SUPER 2A 25
  Consumption: 2500.0

[2] Writing data to PLC READ area...
✓ Written: NO-MO = WH/MO/00002 → D6001
✓ Written: finished_goods = JF SUPER 2A 25 → D6017
✓ Written: Quantity Goods_id = 2500.0 → D6025
✓ Written: SILO ID 101 (SILO BESAR) = 101 → D6026
✓ Written: SILO 1 Consumption = 825.5 → D6027
...

================================================================================
WRITE RESULTS
================================================================================
✓ Success: 33 fields
✗ Failed: 0 fields
```

**Key Features:**

- ✅ Auto-apply scale factor (consumption × 10 untuk PLC)
- ✅ ASCII encoding (big-endian, 2 chars/word)
- ✅ Boolean conversion (0/1)
- ✅ Error handling per field

---

### 1b. test_write_read_area_from_csv.py

**Purpose**: Write data ke PLC READ area dari file CSV (simulasi PLC manual).

**Input CSV:** `app/reference/read_data_plc_input.csv`

**Important Notes:**

- Kolom `Value` dianggap nilai **human**; script akan menerapkan `scale` sebelum ditulis ke PLC.
- Field `ASCII` akan dipotong/padded sesuai `length`.
- Jika `Value` kosong, field tersebut dilewati.

**Usage:**

```bash
python test_write_read_area_from_csv.py
```

---

### 1c. test_export_read_area_to_csv.py

**Purpose**: Export nilai PLC READ area ke CSV untuk diedit ulang.

**Output CSV:** `app/reference/read_data_plc_input.csv`

**Usage:**

```bash
python test_export_read_area_to_csv.py
```

---

### 2. test_plc_read.py

**Purpose**: Test reading data dari PLC via HTTP API.

**What it does:**
- Test read single field (ASCII, REAL)
- Test read all fields
- Test read formatted batch data

**Usage:**

```bash
python test_plc_read.py
```

**Output:**

```
[1] Get PLC Configuration
✓ PLC IP: 192.168.1.2
✓ PLC Port: 9600

[2] Read ASCII Field: NO-MO
✓ Value: WH/MO/00002

[3] Read REAL Field: Quantity Goods_id
✓ Value: 2500.0

[4] Read Silo Consumption (with scale)
✓ SILO 1 Consumption: 825.5 kg
   (PLC value: 8255, scale: 10.0)

[5] Read All Fields
✓ Total fields: 33
✓ Sample fields:
   NO-MO: WH/MO/00002
   finished_goods: JF SUPER 2A 25
   Quantity Goods_id: 2500.0

[6] Read Formatted Batch Data
✓ MO ID: WH/MO/00002
✓ Product: JF SUPER 2A 25
✓ Silos with consumption:
   - Silo a: ID=101, Consumption=825.5 kg
   - Silo b: ID=102, Consumption=1200.0 kg
```

---

### 3. test_plc_sync.py

**Purpose**: Test sync data dari PLC ke database.

**What it does:**
- Read all data dari PLC (D6001-D6058)
- Extract MO_ID dari PLC
- Find matching record di `mo_batch`
- Update fields jika ada perubahan:
  - `actual_consumption_silo_a` s/d `actual_consumption_silo_m`
  - `actual_weight_quantity_finished_goods`
  - `status_manufacturing`, `status_operation`
  - `last_read_from_plc`

**Usage:**

```bash
python test_plc_sync.py
```

**Output:**

```
[1] Sync data from PLC to database
Status: 200
Response: {
  "status": "success",
  "message": "Batch data updated successfully",
  "data": {
    "mo_id": "WH/MO/00002",
    "updated": true
  }
}
✓ MO_ID: WH/MO/00002
✓ Updated: True
```

**Database Changes:**

Check dengan SQL:

```sql
SELECT 
  mo_id,
  actual_consumption_silo_a,
  actual_consumption_silo_b,
  actual_consumption_silo_c,
  last_read_from_plc
FROM mo_batch
WHERE mo_id = 'WH/MO/00002';
```

Before sync:
```
mo_id           | actual_consumption_silo_a | last_read_from_plc
----------------|---------------------------|-------------------
WH/MO/00002     | NULL                      | NULL
```

After sync:
```
mo_id           | actual_consumption_silo_a | last_read_from_plc
----------------|---------------------------|-------------------
WH/MO/00002     | 825.5                     | 2026-02-12 10:30:00+07
```

---

### 4. test_complete_cycle.py

**Purpose**: Test complete bidirectional communication flow.

**What it does:**
1. Verify PLC configuration
2. Read MO_ID dari PLC
3. Read product & quantity
4. Read silo consumptions (first 3 silos)
5. Read complete batch data
6. **Sync to database**
7. Re-sync untuk verify change detection

**Usage:**

```bash
python test_complete_cycle.py
```

**Output:**

```
================================================================================
COMPLETE TEST: Write → Read → Sync
================================================================================

[1] Verify PLC Configuration
✓ PLC IP: 192.168.1.2
✓ PLC Port: 9600

[2] Read MO_ID from PLC
✓ MO_ID from PLC: WH/MO/00002

[3] Read Product Name from PLC
✓ Product: JF SUPER 2A 25

[4] Read Quantity from PLC
✓ Quantity: 2500.0

[5] Read Silo Consumptions from PLC
✓ Silo A: 825.5 kg
✓ Silo B: 1200.0 kg
✓ Silo C: 950.0 kg

[6] Read Complete Batch Data from PLC
✓ MO_ID: WH/MO/00002
✓ Product: JF SUPER 2A 25
✓ Quantity: 2500.0
✓ Status Manufacturing: True
✓ Status Operation: True
✓ Active Silos: 13 silos

[7] Sync PLC Data to Database
Syncing MO_ID: WH/MO/00002
✓ Status: success
✓ Message: Batch data updated successfully
✓ MO_ID: WH/MO/00002
✓ Updated: True

  Database fields updated:
  - actual_consumption_silo_a, b, c, ...
  - actual_weight_quantity_finished_goods
  - status_manufacturing
  - status_operation
  - last_read_from_plc (timestamp)

[8] Verify Change Detection (Re-sync)
Re-syncing same data (should detect no changes)...
✓ Change detection works! No update needed.

================================================================================
TEST SUMMARY
================================================================================

✅ Complete cycle tested successfully!

Flow verified:
  1. ✓ Data written to PLC READ area (D6001-D6058)
  2. ✓ Data read back from PLC via API
  3. ✓ Data synced to database (actual_consumption_*)
  4. ✓ Change detection working (smart update)
```

---

## Testing Workflow

### 🎯 Recommended Testing Sequence

#### **Option 1: Quick Test (API Only)**

```bash
# 1. Start server
python -m uvicorn app.main:app --reload

# 2. Test read (assumes PLC already has data)
python test_plc_read.py

# 3. Test sync
python test_plc_sync.py
```

#### **Option 2: Complete Test (Simulate PLC Data)**

```bash
# 1. Start server
python -m uvicorn app.main:app --reload

# 2. Populate PLC READ area dengan data dari database
python test_write_read_area.py

# 3. Test complete cycle
python test_complete_cycle.py
```

#### **Option 3: Production-like Test (Odoo → PLC → Sync)**

```bash
# 1. Clear database
curl -X DELETE http://localhost:8000/api/sync/clear-mo-batch

# 2. Fetch dari Odoo
python test_plc_write_from_odoo.py

# 3. Write to PLC WRITE area (D7000-D7418)
# (already done in step 2)

# Done! Now PLC will process and update READ area
# In real production, PLC updates D6001-D6058 during manufacturing

# 4. Read from PLC READ area
python test_plc_read.py

# 5. Sync to database
python test_plc_sync.py
```

---

## Expected Results

### 1. After test_write_read_area.py

**PLC Memory (D6001-D6058):**
- ✅ D6001-6008: Contains MO_ID as ASCII
- ✅ D6017-6024: Contains product name
- ✅ D6025: Contains quantity
- ✅ D6027, D6029, D6031...: Contains silo consumptions (scaled × 10)
- ✅ D6056-6057: Contains status (0/1)

**Verification:**

```bash
# Read back to verify
python test_plc_read.py
```

### 2. After test_plc_sync.py

**Database Table (mo_batch):**

```sql
-- Check actual consumption fields
SELECT 
  mo_id,
  actual_consumption_silo_a,
  actual_consumption_silo_b,
  actual_consumption_silo_c,
  actual_weight_quantity_finished_goods,
  status_manufacturing,
  status_operation,
  last_read_from_plc
FROM mo_batch
WHERE batch_no = 1;
```

Expected:
- ✅ `actual_consumption_silo_a` = 825.5 (from PLC 8255 ÷ 10)
- ✅ `actual_consumption_silo_b` = 1200.0 (from PLC 12000 ÷ 10)
- ✅ `last_read_from_plc` = current timestamp
- ✅ Status fields updated

### 3. Change Detection Test

**Test scenario:**

```bash
# First sync
python test_plc_sync.py
# Expected: "updated": true

# Second sync (without changing PLC data)
python test_plc_sync.py
# Expected: "updated": false
```

**Why this matters:**
- Prevents unnecessary database writes
- Reduces transaction overhead
- Only updates when PLC values actually change

---

## Troubleshooting

### Issue 1: "Batch not found"

**Error:**
```
✗ Batch not found! Please ensure batch_no=1 exists in mo_batch table.
```

**Solution:**

```bash
# Check database
python -c "
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch

with SessionLocal() as session:
    count = session.query(TableSmoBatch).count()
    print(f'Total records: {count}')
    
    batch = session.query(TableSmoBatch).first()
    if batch:
        print(f'First batch: batch_no={batch.batch_no}, mo_id={batch.mo_id}')
"

# If empty, fetch from Odoo
python test_plc_write_from_odoo.py
```

### Issue 2: "Connection refused" / "PLC timeout"

**Error:**
```
✗ Error writing to PLC: [Errno 10061] Connection refused
```

**Solution:**

```bash
# 1. Check PLC IP in .env
cat .env | grep PLC_IP

# 2. Ping PLC
ping 192.168.1.2

# 3. Check firewall
# Allow UDP port 9600

# 4. Test with netcat (Windows)
# Install: choco install netcat
nc -u 192.168.1.2 9600
```

### Issue 3: "MO batch not found for MO_ID"

**Error:**
```json
{
  "status": "error",
  "error": "MO batch not found for MO_ID: WH/MO/99999"
}
```

**Cause:** PLC has different MO_ID than database.

**Solution:**

```bash
# 1. Check what's in PLC
curl "http://localhost:8000/api/plc/read-field/NO-MO"

# 2. Check what's in database
python -c "
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch

with SessionLocal() as session:
    batches = session.query(TableSmoBatch).all()
    for b in batches:
        print(f'batch_no={b.batch_no}, mo_id={b.mo_id}')
"

# 3. Re-write correct batch to PLC READ area
python test_write_read_area.py
```

### Issue 4: Scale Factor Issues

**Problem:** Consumption values wrong (off by 10x).

**Example:**
- Database: `consumption_silo_a = 825.5`
- PLC should have: `8255` (825.5 × 10)
- But you see: `82.55` or `82550`

**Verification:**

```python
# Check scale factor in READ_DATA_PLC_MAPPING.json
import json
with open('app/reference/READ_DATA_PLC_MAPPING.json') as f:
    data = json.load(f)
    for item in data['raw_list']:
        if 'Consumption' in item['Informasi']:
            print(f"{item['Informasi']}: scale={item.get('scale', 1.0)}")
```

Expected output:
```
SILO 1 Consumption: scale=10.0
SILO 2 Consumption: scale=10.0
...
```

### Issue 5: "Field not found in mapping"

**Error:**
```
KeyError: 'SILO 1 Consumption'
```

**Cause:** Field name mismatch between code and JSON.

**Solution:**

```bash
# List all field names in mapping
python -c "
import json
with open('app/reference/READ_DATA_PLC_MAPPING.json') as f:
    data = json.load(f)
    for item in data['raw_list']:
        print(item['Informasi'])
"

# Check exact field name (case-sensitive, whitespace-sensitive)
```

---

## Advanced Testing

### Custom Test Data

Modify batch data before writing:

```python
# In test_write_read_area.py, after loading batch:
batch.consumption_silo_a = 1500.0  # Custom value
batch.status_manufacturing = True
batch.status_operation = False
```

### Test Multiple Batches

```python
# Write batch 2, 3, 4... to PLC
for batch_no in [1, 2, 3]:
    batch = session.query(TableSmoBatch).filter(
        TableSmoBatch.batch_no == batch_no
    ).first()
    
    if batch:
        results = writer.write_batch_data(batch)
        print(f"Batch {batch_no}: {results['success']} fields written")
```

### Performance Testing

```bash
# Test sync speed
import time

for i in range(10):
    start = time.time()
    response = requests.post("http://localhost:8000/api/plc/sync-from-plc")
    elapsed = time.time() - start
    print(f"Sync {i+1}: {elapsed:.3f}s")
```

---

## MO Batch Process Test

Script baru untuk menguji tahapan proses MO batch end-to-end sesuai kebutuhan produksi.

**Script:** `test_mo_batch_process.py`

**Tahapan yang diuji:**

1. Kosongkan table `mo_batch`
2. Ambil `mo_list` detail dari Odoo dan isi `mo_batch` jika kosong
3. Tulis data `mo_batch` ke memory PLC (slot BATCH01..BATCH30)
4. Baca memory PLC dan update `mo_batch` sesuai `mo_id`
5. Pindahkan MO selesai (`status_manufacturing = true`) ke `mo_histories`

**Usage:**

```bash
python test_mo_batch_process.py
```

**Expected output (ringkas):**

```
STEP 1 - Clear mo_batch
Cleared mo_batch rows: 7

STEP 2 - Fetch and fill mo_batch
Inserted MO rows: 10

STEP 3 - Write mo_batch queue to PLC
Batches written to PLC: 10

STEP 4 - Sync PLC data to mo_batch
PLC sync result: {'success': True, 'updated': True, 'mo_id': 'WH/MO/00002'}

STEP 5 - Move finished MO to history
Moved to mo_histories: 1
Total history rows: 12
Remaining mo_batch rows: 9
```

**Notes:**

- Jika PLC tidak mengirim status selesai, script akan menandai MO yang terbaca dari PLC sebagai selesai untuk tujuan test.
- Pastikan table `mo_histories` sudah ada (migration terbaru).

---

## Summary

| Test Script | Purpose | When to Use |
|-------------|---------|-------------|
| `test_write_read_area.py` | Populate PLC READ area | Development, testing tanpa PLC real |
| `test_write_read_area_from_csv.py` | Populate PLC READ area from CSV | Manual PLC input simulation |
| `test_export_read_area_to_csv.py` | Export PLC READ area to CSV | Capture PLC snapshot |
| `test_plc_read.py` | Verify read functionality | After PLC has data |
| `test_plc_sync.py` | Test database sync | Verify actual_consumption update |
| `test_complete_cycle.py` | End-to-end test | CI/CD, integration testing |
| `test_mo_batch_process.py` | Full MO batch lifecycle | Manual end-to-end validation |

**Development Workflow:**

1. **Development**: `test_write_read_area.py` → `test_plc_read.py`
2. **Integration**: `test_complete_cycle.py`
3. **Process Validation**: `test_mo_batch_process.py`
4. **Production**: PLC updates D6001-D6058 → `test_plc_sync.py` (periodic)
5. **CSV Simulation**: `test_write_read_area_from_csv.py` → `test_plc_sync.py`
6. **CSV Snapshot**: `test_export_read_area_to_csv.py` → edit CSV → `test_write_read_area_from_csv.py`

---

## Next Steps

1. ✅ Run migration: `alembic upgrade head`
2. ✅ Populate database: `python test_plc_write_from_odoo.py`
3. ✅ Test write: `python test_write_read_area.py`
4. ✅ Test cycle: `python test_complete_cycle.py`
5. ✅ Test MO lifecycle: `python test_mo_batch_process.py`
6. ✅ Schedule periodic sync (production)

---

**Document Version:** 1.0  
**Last Updated:** February 13, 2026  
**Author:** FastAPI SCADA-Odoo Integration Team
