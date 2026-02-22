# PLC Bidirectional Communication Testing Guide

Panduan lengkap untuk testing PLC Read/Write/Sync functionality dengan fokus pada **bidirectional communication** antara Middleware dan PLC.

## ðŸ“‹ Table of Contents

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
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    Testing Flow                             â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                             â”‚
â”‚  1. WRITE TEST                                              â”‚
â”‚     Database (mo_batch) â”€â”€â–º PLC READ Area (D6001-D6077)    â”‚
â”‚     Script: test_write_read_area.py                        â”‚
â”‚                                                             â”‚
â”‚  2. READ TEST                                               â”‚
â”‚     PLC READ Area (D6001-D6077) â”€â”€â–º API Response           â”‚
â”‚     Script: test_plc_read.py                               â”‚
â”‚                                                             â”‚
â”‚  3. SYNC TEST                                               â”‚
â”‚     PLC READ Area (D6001-D6077) â”€â”€â–º Database (mo_batch)    â”‚
â”‚     Script: test_plc_sync.py                               â”‚
â”‚                                                             â”‚
â”‚  4. HANDSHAKE TEST                                          â”‚
â”‚     Test PLC â†” Middleware handshaking (status_read_data)   â”‚
â”‚     Script: test_handshake.py                              â”‚
â”‚                                                             â”‚
â”‚  5. COMPLETE CYCLE TEST                                     â”‚
â”‚     All steps combined with verification                    â”‚
â”‚     Script: test_complete_cycle.py                         â”‚
â”‚                                                             â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
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
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                     PLC DM Memory                             â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                               â”‚
â”‚  D6001-D6077  â”‚ READ AREA (Production Feedback)              â”‚
â”‚               â”‚ âœ“ Current MO being processed                 â”‚
â”‚               â”‚ âœ“ Actual consumption per silo (13 silos)     â”‚
â”‚               â”‚ âœ“ Actual consumption liquid tanks (LQ114/115)â”‚
â”‚               â”‚ âœ“ Real-time status (manufacturing/operation) â”‚
â”‚               â”‚ âœ“ Actual finished goods weight               â”‚
â”‚               â”‚ âœ“ status_read_data per-batch: D6076/D6176/.../D6976 (handshake flag)   â”‚
â”‚               â”‚ Mapping: READ_DATA_PLC_MAPPING.json          â”‚
â”‚               â”‚                                              â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                               â”‚
â”‚  D7000-D7976  â”‚ WRITE AREA (Production Commands)            â”‚
â”‚               â”‚ âœ“ Queue of 10 MO batches (BATCH01-10)       â”‚
â”‚               â”‚ âœ“ Planned consumption (silos + LQ tanks)     â”‚
â”‚               â”‚ âœ“ Production parameters                      â”‚
â”‚               â”‚ âœ“ D7076: status_read_data (handshake flag)   â”‚
â”‚               â”‚ Mapping: MASTER_BATCH_REFERENCE.json         â”‚
â”‚               â”‚                                              â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                               â”‚
â”‚  D8000-D8022  â”‚ EQUIPMENT FAILURE AREA                      â”‚
â”‚               â”‚ âœ“ Equipment code (silo101, lq114, etc)       â”‚
â”‚               â”‚ âœ“ Failure info (START_FAILURE, SENSOR_ERROR) â”‚
â”‚               â”‚ âœ“ Timestamp (Year, Month, Day, H:M:S)        â”‚
â”‚               â”‚ âœ“ D8022: status_read_data (handshake flag)   â”‚
â”‚               â”‚ Mapping: EQUIPMENT_FAILURE_REFERENCE.json    â”‚
â”‚               â”‚                                              â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Handshake Protocol

The middleware uses **status_read_data** flags for bidirectional handshaking:

| Flag | Address | Direction | Purpose |
|------|---------|-----------|---------|
| READ status | D6076/D6176/.../D6976 | MWâ†’PLC | Middleware marks production data as read |
| WRITE status | D7076 | PLCâ†’MW | PLC marks batch recipe as read |
| FAILURE status | D8022 | MWâ†’PLC | Middleware marks equipment failure as read |

**Flow:**
- **READ**: PLC writes data â†’ MW reads â†’ MW sets status_read_data per-batch=1 â†’ PLC sees flag â†’ PLC resets to 0
- **WRITE**: MW checks D7076 â†’ If 1: write batch, set to 0 â†’ PLC reads â†’ PLC sets to 1
- **FAILURE**: PLC writes failure â†’ MW reads â†’ MW sets D8022=1 â†’ PLC resets to 0

### Field Mapping: Database â†” PLC READ Area

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
| `silo_m` | SILO ID 113 | D6050 | REAL | 1.0 |
| `consumption_silo_m` | SILO 13 Consumption | D6051 | REAL | 10.0 |
| `lq_tetes` | LQ ID 114 (TETES) | D6052 | REAL | 1.0 |
| `consumption_lq_tetes` | LQ 114 Consumption | D6053 | REAL | 10.0 |
| `lq_fml` | LQ ID 115 (FML) | D6054 | REAL | 1.0 |
| `consumption_lq_fml` | LQ 115 Consumption | D6055 | REAL | 10.0 |
| `status_manufacturing` | status manufaturing | D6056 | boolean | - |
| `status_operation` | Status Operation | D6057 | boolean | - |
| `actual_weight_quantity_finished_goods` | weight_finished_good | D6073-6074 | REAL | 100.0 |
| `status_read_data` | Handshake flag (per-batch) | D6076/D6176/.../D6976 | boolean | - |

**Important Notes:**

1. **Scale Factor**: Consumption fields menggunakan scale 100.0
   - Database value: `825.5` kg
   - PLC value: `82550` (825.5 Ã— 100)
   - When reading back: PLC `82550` Ã· 100 = `825.5` kg

2. **ASCII Encoding**: 2 characters per word, big-endian
   - "WH/MO/00002" â†’ 8 words (16 bytes)

3. **Boolean**: 
   - True â†’ PLC value `1`
   - False â†’ PLC value `0`

---

## Test Scripts

### 1. test_write_read_area.py

**Purpose**: Write data dari database ke PLC READ area untuk simulasi.

**What it does:**
- Read `batch_no=1` dari table `mo_batch`
- Convert data to PLC format (dengan scale factor)
- Write ke PLC memory D6001-D6077
- Menggunakan mapping dari `READ_DATA_PLC_MAPPING.json`

**Usage:**

```bash
python test_write_read_area.py
```

**Output:**

```
================================================================================
TEST WRITE TO READ_DATA_PLC_MAPPING AREA (D6001-D6077)
================================================================================

[1] Reading batch_no=1 from database...
âœ“ Found batch: WH/MO/00002
  Product: JF SUPER 2A 25
  Consumption: 2500.0

[2] Writing data to PLC READ area...
âœ“ Written: NO-MO = WH/MO/00002 â†’ D6001
âœ“ Written: finished_goods = JF SUPER 2A 25 â†’ D6017
âœ“ Written: Quantity Goods_id = 2500.0 â†’ D6025
âœ“ Written: SILO ID 101 (SILO BESAR) = 101 â†’ D6026
âœ“ Written: SILO 1 Consumption = 825.5 â†’ D6027
...

================================================================================
WRITE RESULTS
================================================================================
âœ“ Success: 33 fields
âœ— Failed: 0 fields
```

**Key Features:**

- âœ… Auto-apply scale factor (consumption Ã— 10 untuk PLC)
- âœ… ASCII encoding (big-endian, 2 chars/word)
- âœ… Boolean conversion (0/1)
- âœ… Error handling per field

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

### 1d. test_write_read_area_from_odoo.py

**Purpose**: Populate PLC READ area langsung dari list MO Odoo tanpa edit CSV manual.

**What it does:**
- Authenticate ke Odoo dan fetch `mo-list-detailed`
- Map `mo_id`, `product_name`, `quantity`, dan `components_consumption` ke field READ area
- Write ke PLC berdasarkan `READ_DATA_PLC_MAPPING.json`
- Force status untuk semua data yang ditulis: `status_manufacturing=1` dan `status_operation=0`
- Support retry per field write untuk mengurangi timeout transien PLC

**Usage (single run):**

```bash
python test_write_read_area_from_odoo.py --limit 10 --interval-seconds 5
```

**Usage (continuous loop):**

```bash
python test_write_read_area_from_odoo.py --loop --limit 10 --interval-seconds 10 --write-retries 3
```

**Usage (specific MO):**

```bash
python test_write_read_area_from_odoo.py --single-mo-id "WH/MO/00007" --write-retries 3 --retry-delay-seconds 0.3
```

**Useful options:**
- `--weight-finished-good <float>` untuk simulasi berat output
- `--write-retries <int>` dan `--retry-delay-seconds <float>` untuk stabilkan write saat PLC timeout transien

**Important:**
- Opsi `--status-manufacturing` dan `--status-operation` sudah tidak tersedia.
- Nilai status selalu dipaksa `1` (manufacturing done) dan `0` (operation normal).

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
âœ“ PLC IP: 192.168.1.2
âœ“ PLC Port: 9600

[2] Read ASCII Field: NO-MO
âœ“ Value: WH/MO/00002

[3] Read REAL Field: Quantity Goods_id
âœ“ Value: 2500.0

[4] Read Silo Consumption (with scale)
âœ“ SILO 1 Consumption: 825.5 kg
   (PLC value: 82550, scale: 100.0)

[5] Read All Fields
âœ“ Total fields: 33
âœ“ Sample fields:
   NO-MO: WH/MO/00002
   finished_goods: JF SUPER 2A 25
   Quantity Goods_id: 2500.0

[6] Read Formatted Batch Data
âœ“ MO ID: WH/MO/00002
âœ“ Product: JF SUPER 2A 25
âœ“ Silos with consumption:
   - Silo a: ID=101, Consumption=825.5 kg
   - Silo b: ID=102, Consumption=1200.0 kg
```

---

### 3. test_plc_sync.py

**Purpose**: Test sync data dari PLC ke database.

**What it does:**
- Read all data dari PLC (D6001-D6077)
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
âœ“ MO_ID: WH/MO/00002
âœ“ Updated: True
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
COMPLETE TEST: Write â†’ Read â†’ Sync
================================================================================

[1] Verify PLC Configuration
âœ“ PLC IP: 192.168.1.2
âœ“ PLC Port: 9600

[2] Read MO_ID from PLC
âœ“ MO_ID from PLC: WH/MO/00002

[3] Read Product Name from PLC
âœ“ Product: JF SUPER 2A 25

[4] Read Quantity from PLC
âœ“ Quantity: 2500.0

[5] Read Silo Consumptions from PLC
âœ“ Silo A: 825.5 kg
âœ“ Silo B: 1200.0 kg
âœ“ Silo C: 950.0 kg

[6] Read Complete Batch Data from PLC
âœ“ MO_ID: WH/MO/00002
âœ“ Product: JF SUPER 2A 25
âœ“ Quantity: 2500.0
âœ“ Status Manufacturing: True
âœ“ Status Operation: True
âœ“ Active Silos: 13 silos

[7] Sync PLC Data to Database
Syncing MO_ID: WH/MO/00002
âœ“ Status: success
âœ“ Message: Batch data updated successfully
âœ“ MO_ID: WH/MO/00002
âœ“ Updated: True

  Database fields updated:
  - actual_consumption_silo_a, b, c, ...
  - actual_weight_quantity_finished_goods
  - status_manufacturing
  - status_operation
  - last_read_from_plc (timestamp)

[8] Verify Change Detection (Re-sync)
Re-syncing same data (should detect no changes)...
âœ“ Change detection works! No update needed.

================================================================================
TEST SUMMARY
================================================================================

âœ… Complete cycle tested successfully!

Flow verified:
  1. âœ“ Data written to PLC READ area (D6001-D6077)
  2. âœ“ Data read back from PLC via API
  3. âœ“ Data synced to database (actual_consumption_*)
  4. âœ“ Change detection working (smart update)
```

---

### 5. test_handshake.py

**Purpose**: Test PLC â†” Middleware handshaking mechanism using status_read_data flags.

**What it does:**
1. **READ Area Test (per-batch status_read_data):**
   - Reset flag to 0 (PLC ready)
   - Mark as read (set to 1)
   - Verify flag changed
   
2. **WRITE Area Test (D7076)**:
   - Set to 1 (simulate PLC has read)
   - Verify safe to write
   - Reset to 0 after write
   - Verify flag changed
   
3. **Equipment Failure Test (D8022)**:
   - Reset to 0
   - Mark as read (set to 1)
   - Verify flag changed

**Usage:**

```bash
python test_handshake.py
```

**Output:**

```
================================================================================
PLC HANDSHAKE SERVICE TEST
================================================================================
This test validates the handshaking mechanism for:
  - READ Area (per-batch status_read_data): Middleware â†’ PLC
  - WRITE Area (D7076): PLC â†’ Middleware
  - Equipment Failure (D8022): Middleware â†’ PLC

================================================================================
TEST 1: READ Area Handshake (per-batch status_read_data)
================================================================================

[1] Check current READ area status:
   Current status: NOT READ (0)

[2] Reset READ area status to 0 (simulate PLC ready):
   âœ“ Successfully reset to 0 (status_read_data per-batch=0)
   Verified: False (should be False)

[3] Mark READ area as read (simulate Middleware read):
   âœ“ Successfully marked as read (status_read_data per-batch=1)
   Verified: True (should be True)

âœ… READ Area Handshake Test PASSED

================================================================================
TEST 2: WRITE Area Handshake (D7076)
================================================================================

[1] Check current WRITE area status:
   PLC has read previous batch: NO (0)

[2] Simulate PLC finished reading (set D7076=1):
   âœ“ Set D7076 = 1 (PLC has read previous batch)
   Safe to write new batch: YES

[3] Simulate Middleware writing new batch:
   After write, Middleware resets D7076 = 0
   âœ“ Successfully reset (D7076=0) - waiting for PLC to read
   Verified: PLC has read = False (should be False)

âœ… WRITE Area Handshake Test PASSED

================================================================================
TEST 3: Equipment Failure Handshake (D8022)
================================================================================

[1] Check current equipment failure status:
   Current status: NOT READ (0)

[2] Reset equipment failure status to 0:
   âœ“ Successfully reset to 0 (D8022=0)

[3] Mark equipment failure as read:
   âœ“ Successfully marked as read (D8022=1)
   Verified: True (should be True)

âœ… Equipment Failure Handshake Test PASSED

================================================================================
TEST SUMMARY
================================================================================
READ Area                      âœ… PASSED
WRITE Area                     âœ… PASSED
Equipment Failure              âœ… PASSED

ðŸŽ‰ ALL TESTS PASSED!
```

**Documentation:**
- [Handshake Implementation Summary](HANDSHAKE_IMPLEMENTATION_SUMMARY.md)
- [Handshake Quick Reference](HANDSHAKE_QUICK_REF.md)

---

## Testing Workflow

### ðŸŽ¯ Recommended Testing Sequence

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

#### **Option 3: Production-like Test (Odoo â†’ PLC â†’ Sync)**

```bash
# 1. Clear database
curl -X DELETE http://localhost:8000/api/sync/clear-mo-batch

# 2. Fetch dari Odoo
python test_plc_write_from_odoo.py

# 3. Write to PLC WRITE area (D7000-D7976)
# (already done in step 2)

# Done! Now PLC will process and update READ area
# In real production, PLC updates D6001-D6077 during manufacturing

# 4. Read from PLC READ area
python test_plc_read.py

# 5. Sync to database
python test_plc_sync.py
```

#### **Option 4: Auto READ-Area Feed from Odoo (No CSV Manual Edit)**

```bash
# 1. Start server (optional, needed if you also call API tests)
python -m uvicorn app.main:app --reload

# 2. Continuously write Odoo MO data into PLC READ area
python test_write_read_area_from_odoo.py --loop --limit 10 --interval-seconds 10 --write-retries 3

# 3. In parallel, run middleware read/sync checks
python test_plc_read.py
python test_plc_sync.py
```

---

## Expected Results

### 1. After test_write_read_area.py

**PLC Memory (D6001-D6077):**
- âœ… D6001-6008: Contains MO_ID as ASCII
- âœ… D6017-6024: Contains product name
- âœ… D6025: Contains quantity
- âœ… D6027, D6029, D6031...: Contains silo consumptions (scaled Ã— 10)
- âœ… D6056-6057: Contains status (0/1)
- âœ… status_read_data per-batch: D6076/D6176/.../D6976

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
- âœ… `actual_consumption_silo_a` = 825.5 (from PLC 8255 Ã· 10)
- âœ… `actual_consumption_silo_b` = 1200.0 (from PLC 12000 Ã· 10)
- âœ… `last_read_from_plc` = current timestamp
- âœ… Status fields updated

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
âœ— Batch not found! Please ensure batch_no=1 exists in mo_batch table.
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
âœ— Error writing to PLC: [Errno 10061] Connection refused
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
- PLC should have: `8255` (825.5 Ã— 10)
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
SILO 1 Consumption: scale=100.0
SILO 2 Consumption: scale=100.0
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
| `test_write_read_area_from_odoo.py` | Populate PLC READ area from Odoo MO list | Integration test tanpa edit CSV berulang |
| `test_export_read_area_to_csv.py` | Export PLC READ area to CSV | Capture PLC snapshot |
| `test_plc_read.py` | Verify read functionality | After PLC has data |
| `test_plc_sync.py` | Test database sync | Verify actual_consumption update |
| `test_complete_cycle.py` | End-to-end test | CI/CD, integration testing |
| `test_mo_batch_process.py` | Full MO batch lifecycle | Manual end-to-end validation |

**Development Workflow:**

1. **Development**: `test_write_read_area.py` â†’ `test_plc_read.py`
2. **Integration**: `test_complete_cycle.py`
3. **Process Validation**: `test_mo_batch_process.py`
4. **Production**: PLC updates D6001-D6077 â†’ `test_plc_sync.py` (periodic)
5. **CSV Simulation**: `test_write_read_area_from_csv.py` â†’ `test_plc_sync.py`
6. **CSV Snapshot**: `test_export_read_area_to_csv.py` â†’ edit CSV â†’ `test_write_read_area_from_csv.py`
7. **Odoo-driven READ Simulation**: `test_write_read_area_from_odoo.py --loop` -> `test_plc_sync.py`

---

## Next Steps

1. Run migration: `alembic upgrade head`
2. Populate database: `python test_plc_write_from_odoo.py`
3. Test write: `python test_write_read_area.py`
4. Test Odoo-driven READ feed: `python test_write_read_area_from_odoo.py --loop --limit 10 --interval-seconds 10 --write-retries 3`
5. Test cycle: `python test_complete_cycle.py`
6. Test MO lifecycle: `python test_mo_batch_process.py`
7. Schedule periodic sync (production)

---

**Document Version:** 1.1  
**Last Updated:** February 17, 2026  
**Author:** FastAPI SCADA-Odoo Integration Team


