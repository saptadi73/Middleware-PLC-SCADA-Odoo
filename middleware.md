# FastAPI SCADA-Odoo Middleware Documentation

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Database Schema](#database-schema)
6. [API Endpoints](#api-endpoints)
7. [Auto-Sync Scheduler](#auto-sync-scheduler)
8. [Services](#services)
9. [Usage Examples](#usage-examples)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)
12. [Production Deployment](#production-deployment)

---

## Overview

FastAPI middleware untuk integrasi SCADA (Supervisory Control and Data Acquisition) dengan Odoo ERP. Sistem ini berfungsi sebagai jembatan antara:

- **PLC (Programmable Logic Controller)**: Omron SYMAC CJ2M CPU31
- **Odoo 14**: Manufacturing Order Management
- **PostgreSQL**: Local database untuk batch tracking

### Key Features

✅ **Bidirectional Communication**: Read/Write PLC memory + Fetch MO from Odoo  
✅ **Auto-Sync Scheduler**: Background task untuk fetch MO berkala  
✅ **Smart Queue Management**: Hanya fetch jika table kosong (PLC selesai)  
✅ **Silo Mapping**: Otomatis map component ke 13 silos (101-113 → A-M)  
✅ **RESTful API**: FastAPI dengan async support  
✅ **Database Persistence**: SQLAlchemy ORM + Alembic migrations  

---

## System Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Middleware                          │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │   API Layer  │───▶│   Services   │───▶│  Database    │    │
│  │   (Routes)   │    │              │    │  (SQLAlchemy)│    │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    │
│         │                   │                     │            │
│         │            ┌──────▼───────┐             │            │
│         │            │  Scheduler   │             │            │
│         │            │  (APScheduler)│            │            │
│         │            └──────────────┘             │            │
└─────────┼──────────────────────────────────────────┼───────────┘
          │                                          │
          ▼                                          ▼
┌──────────────────┐                      ┌──────────────────┐
│   Odoo 14 ERP    │                      │   PostgreSQL     │
│   (JSON-RPC)     │                      │   Database       │
│                  │                      │   (plc)          │
│  - MO Management │                      │  - mo_batch      │
│  - BOM Data      │                      │                  │
│  - Equipment     │                      │                  │
└──────────────────┘                      └──────────────────┘
          │
          │
          ▼
┌──────────────────┐
│   PLC Device     │
│   (OMRON CJ2M)   │
│                  │
│  - Read Memory   │
│  - Write Memory  │
│  - Control Silos │
└──────────────────┘
```

### Data Flow

```
┌─────────────┐
│ Odoo 14 ERP │
│ Manufacturing│
│ Orders (MO) │
└──────┬──────┘
       │ JSON-RPC
       │ /api/scada/mo-list-detailed
       ▼
┌──────────────────────────────────┐
│ FastAPI Middleware               │
│                                  │
│ 1. Fetch MO from Odoo           │
│ 2. Parse component consumption  │
│ 3. Map to silo (101-113)        │
│ 4. Store in mo_batch table      │
└──────┬───────────────────────────┘
       │
       │ SQL INSERT
       ▼
┌──────────────────────┐
│ PostgreSQL Database  │
│ Table: mo_batch      │
│                      │
│ - batch_no (1..10)   │
│ - mo_id              │
│ - silo_a .. silo_m   │
│ - consumption_*      │
└──────┬───────────────┘
       │
       │ SQL SELECT
       ▼
┌──────────────────────┐
│ PLC Control Program  │
│                      │
│ 1. Read batch_no = 1 │
│ 2. Process mixing    │
│ 3. Control silos     │
│ 4. Mark done         │
│ 5. Next batch...     │
└──────────────────────┘
```

---

## Installation & Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 12+
- Odoo 14 (running on http://localhost:8070)
- PLC Device (Omron SYMAC CJ2M CPU31) - optional untuk development

### Step 1: Clone & Setup Virtual Environment

```powershell
# Navigate to project directory
cd C:\projek\fastapi-scada-odoo

# Create virtual environment
python -m venv venv

# Activate venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Database

```powershell
# Login to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE plc;

# Create user (if not exists)
CREATE USER openpg WITH PASSWORD 'openpgpwd';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE plc TO openpg;
\q
```

### Step 3: Configure Environment Variables

Create `.env` file:

```env
# Application
APP_NAME=fastapi-scada-odoo
ENVIRONMENT=development
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql+psycopg2://openpg:openpgpwd@localhost:5432/plc

# Odoo Connection
ODOO_BASE_URL=http://localhost:8070
ODOO_URL=http://localhost:8070
ODOO_DB=your_odoo_database_name
ODOO_USERNAME=admin
ODOO_PASSWORD=admin

# PLC Memory Mapping (JSON format)
PLC_READ_MAP={}
PLC_WRITE_MAP={}

# Auto-Sync Scheduler
ENABLE_AUTO_SYNC=true
SYNC_INTERVAL_MINUTES=5
SYNC_BATCH_LIMIT=10
```

### Step 4: Run Migrations

```powershell
# Apply all migrations
alembic upgrade head

# Verify migration status
alembic current
```

### Step 5: Start Server

```powershell
# Development mode (auto-reload)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Server will start at: `http://127.0.0.1:8000`

---

## Configuration

### Environment Variables Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | string | `fastapi-scada-odoo` | Application name |
| `ENVIRONMENT` | string | `development` | Environment (development/production) |
| `LOG_LEVEL` | string | `info` | Logging level |
| `DATABASE_URL` | string | **required** | PostgreSQL connection string |
| `ODOO_BASE_URL` | string | **required** | Odoo server base URL |
| `ODOO_DB` | string | **required** | Odoo database name |
| `ODOO_USERNAME` | string | **required** | Odoo login username |
| `ODOO_PASSWORD` | string | **required** | Odoo login password |
| `PLC_READ_MAP` | JSON | `{}` | PLC memory read mapping |
| `PLC_WRITE_MAP` | JSON | `{}` | PLC memory write mapping |
| `ENABLE_AUTO_SYNC` | boolean | `false` | Enable/disable auto-sync scheduler |
| `SYNC_INTERVAL_MINUTES` | integer | `5` | Sync interval in minutes |
| `SYNC_BATCH_LIMIT` | integer | `10` | Number of batches to fetch per sync |

### PLC Memory Mapping Format

```json
{
  "PLC_READ_MAP": {
    "batch_status": "D100",
    "current_batch": "D101",
    "silo_a_weight": "D200"
  },
  "PLC_WRITE_MAP": {
    "start_production": "D300",
    "batch_target": "D301"
  }
}
```

---

## Database Schema

### Table: `mo_batch`

Manufacturing Order batch tracking dengan silo component mapping.

```sql
CREATE TABLE mo_batch (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_no INTEGER NOT NULL UNIQUE,
    mo_id VARCHAR(64) NOT NULL,
    consumption NUMERIC(18, 3),
    equipment_id_batch VARCHAR(64),
    
    -- Silo numbers (101-113)
    silo_a INTEGER DEFAULT 101,
    silo_b INTEGER DEFAULT 102,
    silo_c INTEGER DEFAULT 103,
    silo_d INTEGER DEFAULT 104,
    silo_e INTEGER DEFAULT 105,
    silo_f INTEGER DEFAULT 106,
    silo_g INTEGER DEFAULT 107,
    silo_h INTEGER DEFAULT 108,
    silo_i INTEGER DEFAULT 109,
    silo_j INTEGER DEFAULT 110,
    silo_k INTEGER DEFAULT 111,
    silo_l INTEGER DEFAULT 112,
    silo_m INTEGER DEFAULT 113,
    
    -- Component names per silo
    component_silo_a_name VARCHAR(64),
    component_silo_b_name VARCHAR(64),
    component_silo_c_name VARCHAR(64),
    component_silo_d_name VARCHAR(64),
    component_silo_e_name VARCHAR(64),
    component_silo_f_name VARCHAR(64),
    component_silo_g_name VARCHAR(64),
    component_silo_h_name VARCHAR(64),
    component_silo_i_name VARCHAR(64),
    component_silo_j_name VARCHAR(64),
    component_silo_k_name VARCHAR(64),
    component_silo_l_name VARCHAR(64),
    component_silo_m_name VARCHAR(64),
    
    -- Consumption per silo (kg)
    consumption_silo_a FLOAT,
    consumption_silo_b FLOAT,
    consumption_silo_c FLOAT,
    consumption_silo_d FLOAT,
    consumption_silo_e FLOAT,
    consumption_silo_f FLOAT,
    consumption_silo_g FLOAT,
    consumption_silo_h FLOAT,
    consumption_silo_i FLOAT,
    consumption_silo_j FLOAT,
    consumption_silo_k FLOAT,
    consumption_silo_l FLOAT,
    consumption_silo_m FLOAT,
    
    -- Status fields
    status_manufacturing BOOLEAN DEFAULT false,
    status_operation BOOLEAN DEFAULT false,
    actual_weight_quantity_finished_goods NUMERIC(18, 3)
);

CREATE INDEX idx_mo_batch_batch_no ON mo_batch(batch_no);
CREATE INDEX idx_mo_batch_mo_id ON mo_batch(mo_id);
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key (auto-generated) |
| `batch_no` | Integer | Sequential batch number (1, 2, 3, ...) |
| `mo_id` | String | Manufacturing Order ID from Odoo (e.g., "WH/MO/00002") |
| `consumption` | Numeric | Total consumption quantity (kg) |
| `equipment_id_batch` | String | Equipment code (e.g., "PLC01") |
| `silo_a` .. `silo_m` | Integer | Silo numbers (101-113) |
| `component_silo_*_name` | String | Component product name per silo |
| `consumption_silo_*` | Float | Consumption quantity per silo (kg) |
| `status_manufacturing` | Boolean | Manufacturing status flag |
| `status_operation` | Boolean | Operation status flag |
| `actual_weight_quantity_finished_goods` | Numeric | Actual finished goods weight |

### Silo Mapping

| Silo Letter | Silo Number | Equipment Code Pattern |
|-------------|-------------|------------------------|
| A | 101 | silo101, SILO A |
| B | 102 | silo102, SILO B |
| C | 103 | silo103, SILO C |
| D | 104 | silo104, SILO D |
| E | 105 | silo105, SILO E |
| F | 106 | silo106, SILO F |
| G | 107 | silo107, SILO G |
| H | 108 | silo108, SILO H |
| I | 109 | silo109, SILO I |
| J | 110 | silo110, SILO J |
| K | 111 | silo 111, SILO K |
| L | 112 | silo112, SILO L |
| M | 113 | silo113, SILO M |

---

## API Endpoints

### Base URL

```
http://localhost:8000/api
```

### Health Check

#### GET `/api/health`

Check API server health.

**Response:**
```json
{
  "status": "ok"
}
```

---

### Authentication

#### POST `/api/scada/authenticate`

Authenticate to Odoo and return session info.

**Request:**
```bash
curl -X POST http://localhost:8000/api/scada/authenticate
```

**Response:**
```json
{
  "status": "success",
  "message": "Authenticated successfully",
  "data": {
    "uid": 2,
    "login": "admin",
    "company_id": 1,
    "partner_id": 3
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "detail": "Authentication failed: database 'odoo_db' does not exist"
}
```

---

### Manufacturing Orders

#### POST `/api/scada/mo-list-detailed`

Fetch detailed MO list from Odoo and sync to local database.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Number of records to fetch (1-200) |
| `offset` | integer | 0 | Offset for pagination |

**Request:**
```bash
curl -X POST "http://localhost:8000/api/scada/mo-list-detailed?limit=10&offset=0"
```

**Response:**
```json
{
  "status": "success",
  "message": "MO list fetched and synced successfully",
  "data": {
    "count": 7,
    "total_fetched": 7,
    "limit": 10,
    "offset": 0
  }
}
```

**What it does:**

1. Authenticates to Odoo
2. Fetch MO list with `components_consumption` data
3. Parse equipment codes to extract silo numbers (101-113)
4. Map components to silo letters (A-M)
5. Insert/update records in `mo_batch` table
6. Assign sequential `batch_no` (1, 2, 3, ...)

**Error Response:**
```json
{
  "status": "error",
  "detail": "Failed to fetch MO list: Session Expired"
}
```

---

### Admin Endpoints

#### GET `/api/admin/batch-status`

Get current status of `mo_batch` table.

**Request:**
```bash
curl http://localhost:8000/api/admin/batch-status
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
      },
      {
        "batch_no": 2,
        "mo_id": "WH/MO/00003",
        "equipment": "PLC01",
        "consumption": 3000.0
      }
    ]
  }
}
```

#### POST `/api/admin/clear-mo-batch`

Clear all records from `mo_batch` table.

**Use Case:** Call this endpoint after PLC finishes processing all batches to prepare for next sync.

**Request:**
```bash
curl -X POST http://localhost:8000/api/admin/clear-mo-batch
```

**Response:**
```json
{
  "status": "success",
  "message": "mo_batch table cleared successfully",
  "deleted_count": 7
}
```

#### POST `/api/admin/trigger-sync`

Manually trigger auto-sync task (fetch MO from Odoo).

**Use Case:** Force sync without waiting for scheduler interval.

**Request:**
```bash
curl -X POST http://localhost:8000/api/admin/trigger-sync
```

**Response:**
```json
{
  "status": "success",
  "message": "Manual sync completed successfully"
}
```

**Note:** Sync will be skipped if table already has data (smart-wait logic).

---

## Auto-Sync Scheduler

### Overview

Background task yang berjalan berkala untuk fetch MO dari Odoo ke database. Menggunakan **smart-wait logic**: hanya fetch jika table `mo_batch` kosong (PLC sudah selesai proses semua batch).

### Configuration

```env
# .env
ENABLE_AUTO_SYNC=true          # ON/OFF switch
SYNC_INTERVAL_MINUTES=5        # Run every 5 minutes
SYNC_BATCH_LIMIT=10            # Fetch 10 batches per sync
```

### Workflow

```
┌─────────────────────────────────────────────────────────┐
│ Scheduler Timer (Every SYNC_INTERVAL_MINUTES)          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │ SELECT COUNT(*)     │
         │ FROM mo_batch       │
         └──────┬──────────────┘
                │
       ┌────────┴────────┐
       │                 │
   COUNT > 0         COUNT = 0
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────────────┐
│ SKIP SYNC    │  │ FETCH from Odoo      │
│ (Log: Table  │  │ - Authenticate       │
│  has data,   │  │ - Call mo-list API   │
│  waiting for │  │ - Get N batches      │
│  PLC to      │  │                      │
│  complete)   │  └──────────┬───────────┘
└──────────────┘             │
                             ▼
                  ┌──────────────────────┐
                  │ INSERT to mo_batch   │
                  │ - batch_no 1..N      │
                  │ - Map silos          │
                  │ - Map consumption    │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Log: "✓ Auto-sync    │
                  │  completed: N        │
                  │  batches synced"     │
                  └──────────────────────┘
```

### Smart-Wait Logic

```python
# Check if table is empty
result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
count = result.scalar()

if count > 0:
    logger.info(f"Table has {count} records. Skipping sync...")
    return  # Wait for PLC to complete
    
# Table is empty → Fetch new batches
logger.info("Table is empty. Fetching new batches...")
await fetch_mo_list_detailed(limit=SYNC_BATCH_LIMIT)
```

### Scheduler Lifecycle

**Startup:**
```
INFO: Application startup complete.
INFO: ✓ Auto-sync scheduler STARTED: interval=5 minutes, batch_limit=10
```

**Running (with data):**
```
INFO: Auto-sync task running...
INFO: Table mo_batch has 7 records. Skipping sync - waiting for PLC to complete all batches.
```

**Running (empty table):**
```
INFO: Auto-sync task running...
INFO: Table mo_batch is empty. Fetching new batches from Odoo...
INFO: ✓ Auto-sync completed: 7 MO batches synced
```

**Shutdown:**
```
INFO: Auto-sync scheduler stopped
INFO: Application shutdown complete.
```

### Enable/Disable Scheduler

**To Enable:**
```env
# .env
ENABLE_AUTO_SYNC=true
```

**To Disable:**
```env
# .env
ENABLE_AUTO_SYNC=false
```

Restart uvicorn after changing configuration.

---

## Services

### Odoo Auth Service

**File:** `app/services/odoo_auth_service.py`

#### `authenticate_odoo(client: httpx.AsyncClient) -> Dict`

Authenticate to Odoo via JSON-RPC.

**Parameters:**
- `client`: Persistent httpx.AsyncClient for session cookie management

**Returns:**
```json
{
  "uid": 2,
  "login": "admin",
  "company_id": 1,
  "partner_id": 3
}
```

**Endpoint Called:** `POST /web/session/authenticate`

#### `fetch_mo_list_detailed(limit: int, offset: int) -> Dict`

Fetch detailed MO list with component consumption data.

**Parameters:**
- `limit`: Number of records (1-200)
- `offset`: Pagination offset

**Returns:** Odoo JSON-RPC response with MO data

**Endpoint Called:** `POST /api/scada/mo-list-detailed`

**Session Management:** Creates persistent AsyncClient, authenticates first, then fetches data using same client (preserves cookies).

---

### MO Batch Service

**File:** `app/services/mo_batch_service.py`

#### `sync_mo_list_to_db(db: Session, mo_list: List[Dict])`

Sync MO list from Odoo to local database.

**Process:**

1. Iterate through MO list
2. For each MO:
   - Assign sequential `batch_no` (1, 2, 3, ...)
   - Extract equipment code from MO
   - Parse components consumption
   - Map each component to silo (A-M) based on equipment code
   - Upsert record to `mo_batch` table

**Mapping Logic:**

```python
# Extract silo number from equipment code
# Pattern: "silo101", "SILO A", "silo 111"
match = re.search(r"(\d{3})", equipment_code)
silo_number = int(match.group(1))  # e.g., 101

# Map to letter
silo_letter = {101: 'a', 102: 'b', ..., 113: 'm'}[silo_number]

# Set fields
batch.component_silo_a_name = "Pollard Angsa"
batch.consumption_silo_a = 825.0
```

---

## Usage Examples

### Example 1: Manual Fetch & Sync

```bash
# Fetch and sync 10 MO from Odoo
curl -X POST "http://localhost:8000/api/scada/mo-list-detailed?limit=10&offset=0"

# Check database
curl http://localhost:8000/api/admin/batch-status
```

**Expected Result:**
- 10 records inserted to `mo_batch`
- Sequential batch_no assigned (1..10)
- Component mapped to silos

### Example 2: PLC Integration (Pseudo-code)

```python
# PLC reads from mo_batch table
import psycopg2

conn = psycopg2.connect("postgresql://openpg:openpgpwd@localhost/plc")
cur = conn.cursor()

# Get first batch
cur.execute("""
    SELECT batch_no, mo_id, 
           component_silo_a_name, consumption_silo_a,
           component_silo_b_name, consumption_silo_b
    FROM mo_batch 
    WHERE batch_no = 1
""")

batch = cur.fetchone()

# Process mixing
for silo in ['a', 'b', 'c', ...]:
    component = batch[f'component_silo_{silo}_name']
    quantity = batch[f'consumption_silo_{silo}']
    
    if component:
        plc_write(f'SILO_{silo.upper()}_TARGET', quantity)
        plc_write(f'SILO_{silo.upper()}_START', 1)

# After batch complete, move to next
cur.execute("DELETE FROM mo_batch WHERE batch_no = 1")
conn.commit()
```

### Example 3: Auto-Sync Workflow

```bash
# 1. Enable auto-sync in .env
ENABLE_AUTO_SYNC=true
SYNC_INTERVAL_MINUTES=5

# 2. Start uvicorn
uvicorn app.main:app --reload

# 3. Clear table to trigger sync
curl -X POST http://localhost:8000/api/admin/clear-mo-batch

# 4. Wait 5 minutes → Check logs
# INFO: ✓ Auto-sync completed: 7 MO batches synced

# 5. Verify data
curl http://localhost:8000/api/admin/batch-status
```

### Example 4: Query Silo Details

```sql
-- Get all batches with silo A component
SELECT 
    batch_no,
    mo_id,
    component_silo_a_name,
    consumption_silo_a
FROM mo_batch
WHERE component_silo_a_name IS NOT NULL
ORDER BY batch_no;

-- Get total consumption per component
SELECT 
    component_silo_a_name AS component,
    SUM(consumption_silo_a) AS total_kg
FROM mo_batch
WHERE component_silo_a_name IS NOT NULL
GROUP BY component_silo_a_name
ORDER BY total_kg DESC;
```

---

## Testing

### Test Scripts

Project includes several test scripts for verification:

#### 1. test_mo_sync.py

Test basic MO fetch and sync functionality.

```powershell
python test_mo_sync.py
```

**Output:**
```
✓ Status: success
✓ Total fetched: 7
✓ Total records in mo_batch: 7
```

#### 2. check_mo_detail.py

Check detailed silo mapping for a specific batch.

```powershell
python check_mo_detail.py
```

**Output:**
```
Batch #1: WH/MO/00002
Equipment: PLC01
Total Consumption: 2500.000 kg

Component Consumption by Silo:
  Silo A (101): Pollard Angsa → 825.00 kg
  Silo B (102): Kopra mesh → 375.00 kg
  ...
```

#### 3. test_scheduler.py

Verify scheduler configuration and behavior.

```powershell
python test_scheduler.py
```

**Output:**
```
Configuration from .env:
  ENABLE_AUTO_SYNC: True
  SYNC_INTERVAL_MINUTES: 5
  SYNC_BATCH_LIMIT: 10

Current mo_batch table status:
  Total records: 7
  ⚠️ Table HAS DATA → Scheduler will SKIP sync
```

#### 4. demo_auto_sync.py

Demo full auto-sync cycle (clear → sync → verify).

```powershell
python demo_auto_sync.py
```

**Output:**
```
[Step 1] Check current batch status... ✓
[Step 2] Clearing mo_batch table... ✓
[Step 3] Verify table is empty... ✓
[Step 4] Trigger manual sync... ✓
[Step 5] Verify new batches inserted... ✓
```

### Manual Testing with cURL

```bash
# Health check
curl http://localhost:8000/api/health

# Authenticate to Odoo
curl -X POST http://localhost:8000/api/scada/authenticate

# Fetch MO list
curl -X POST "http://localhost:8000/api/scada/mo-list-detailed?limit=5"

# Check batch status
curl http://localhost:8000/api/admin/batch-status

# Clear table
curl -X POST http://localhost:8000/api/admin/clear-mo-batch

# Trigger sync
curl -X POST http://localhost:8000/api/admin/trigger-sync
```

### Unit Testing (Optional)

Create `tests/test_mo_batch_service.py`:

```python
import pytest
from app.services.mo_batch_service import _extract_silo_number

def test_extract_silo_number():
    # Test silo101 format
    equipment = {"code": "silo101", "name": "SILO A"}
    assert _extract_silo_number(equipment) == 101
    
    # Test silo 111 format (with space)
    equipment = {"code": "silo 111", "name": "SILO K"}
    assert _extract_silo_number(equipment) == 111
    
    # Test invalid format
    equipment = {"code": "PLC01", "name": "Main PLC"}
    assert _extract_silo_number(equipment) is None
```

Run tests:
```powershell
pytest tests/
```

---

## Troubleshooting

### Issue: Cannot connect to Odoo

**Symptoms:**
```
RuntimeError: Cannot connect to Odoo at http://localhost:8070: ...
```

**Solutions:**

1. Check Odoo is running:
   ```bash
   curl http://localhost:8070
   ```

2. Verify .env configuration:
   ```env
   ODOO_BASE_URL=http://localhost:8070  # Not https://
   ODOO_DB=correct_database_name        # Exact database name
   ```

3. Test Odoo API directly:
   ```bash
   curl -X POST http://localhost:8070/web/session/authenticate \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","params":{"db":"your_db","login":"admin","password":"admin"}}'
   ```

### Issue: Session Expired Error

**Symptoms:**
```json
{
  "error": {
    "code": 100,
    "message": "Odoo Session Expired"
  }
}
```

**Cause:** Session cookie not preserved between requests.

**Solution:** Already fixed in current implementation. `fetch_mo_list_detailed()` creates persistent AsyncClient and calls `authenticate_odoo()` first.

### Issue: Scheduler Not Running

**Symptoms:**
- No logs: "Auto-sync scheduler STARTED"
- No periodic fetch

**Solutions:**

1. Check .env configuration:
   ```env
   ENABLE_AUTO_SYNC=true  # Must be true
   ```

2. Restart uvicorn after changing .env

3. Check logs on startup:
   ```
   INFO: ✓ Auto-sync scheduler STARTED: interval=5 minutes
   ```

4. If disabled, logs show:
   ```
   INFO: Auto-sync is DISABLED in .env (ENABLE_AUTO_SYNC=false)
   ```

### Issue: Data Not Syncing to Database

**Symptoms:**
- API returns success but table is empty
- COUNT(*) = 0 after sync

**Solutions:**

1. Check database connection:
   ```powershell
   psql -U openpg -d plc -c "SELECT COUNT(*) FROM mo_batch;"
   ```

2. Check for SQL errors in logs

3. Verify migrations applied:
   ```powershell
   alembic current
   # Should show: 20260212_0005 (head)
   ```

4. Test manual insert:
   ```sql
   INSERT INTO mo_batch (batch_no, mo_id, consumption, equipment_id_batch)
   VALUES (999, 'TEST/MO/001', 1000, 'TEST01');
   ```

### Issue: Silo Mapping Incorrect

**Symptoms:**
- Components mapped to wrong silos
- `component_silo_*_name` is NULL

**Solutions:**

1. Check equipment code format in Odoo:
   - Must contain 3-digit number (101-113)
   - Valid: "silo101", "SILO A", "silo 111"
   - Invalid: "silo1", "silo-101"

2. Verify regex pattern in `mo_batch_service.py`:
   ```python
   match = re.search(r"(\d{3})", combined)
   ```

3. Test extraction manually:
   ```python
   from app.services.mo_batch_service import _extract_silo_number
   result = _extract_silo_number({"code": "silo101", "name": "SILO A"})
   print(result)  # Should be 101
   ```

### Issue: Memory Issues with Large MO Lists

**Symptoms:**
- Slow response times
- Out of memory errors

**Solutions:**

1. Reduce `SYNC_BATCH_LIMIT`:
   ```env
   SYNC_BATCH_LIMIT=5  # Instead of 10
   ```

2. Use pagination with offset:
   ```bash
   curl -X POST "http://localhost:8000/api/scada/mo-list-detailed?limit=5&offset=0"
   curl -X POST "http://localhost:8000/api/scada/mo-list-detailed?limit=5&offset=5"
   ```

3. Add database indexes (already included):
   ```sql
   CREATE INDEX idx_mo_batch_batch_no ON mo_batch(batch_no);
   CREATE INDEX idx_mo_batch_mo_id ON mo_batch(mo_id);
   ```

---

## Production Deployment

### Recommended Setup

```
┌──────────────────┐
│   Nginx/Caddy    │  (Reverse proxy)
│   Port 80/443    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Uvicorn        │  (Multiple workers)
│   Port 8000      │
└────────┬─────────┘
         │
         ├──────────────┐
         │              │
         ▼              ▼
┌──────────────┐  ┌──────────────┐
│  PostgreSQL  │  │  Odoo ERP    │
│  Port 5432   │  │  Port 8070   │
└──────────────┘  └──────────────┘
```

### Deployment Checklist

- [ ] Update .env for production:
  ```env
  ENVIRONMENT=production
  LOG_LEVEL=warning
  ENABLE_AUTO_SYNC=true
  SYNC_INTERVAL_MINUTES=15
  ```

- [ ] Use strong database password

- [ ] Enable SSL for PostgreSQL connection

- [ ] Setup systemd service for auto-restart

- [ ] Configure log rotation

- [ ] Setup monitoring (Prometheus + Grafana)

- [ ] Implement backup strategy for PostgreSQL

- [ ] Secure admin endpoints with authentication

- [ ] Use Nginx as reverse proxy

- [ ] Setup firewall rules

- [ ] Configure CORS if needed

### Systemd Service File

Create `/etc/systemd/system/fastapi-scada.service`:

```ini
[Unit]
Description=FastAPI SCADA Middleware
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/fastapi-scada-odoo
Environment="PATH=/opt/fastapi-scada-odoo/venv/bin"
ExecStart=/opt/fastapi-scada-odoo/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level warning
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable fastapi-scada
sudo systemctl start fastapi-scada
sudo systemctl status fastapi-scada
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name scada.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Monitoring

#### Prometheus Metrics

Add `prometheus-fastapi-instrumentator`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

Metrics available at: `http://localhost:8000/metrics`

#### Health Check Endpoint

Already implemented: `GET /api/health`

Use for uptime monitoring (UptimeRobot, Pingdom, etc.)

---

## Appendix

### Alembic Migrations

All migrations in `alembic/versions/`:

1. **20260212_0001**: Initial mo_batch table
2. **20260212_0002**: Add UUID primary key
3. **20260212_0003**: Add component_silo_*_name fields
4. **20260212_0004**: Rename quantity to consumption
5. **20260212_0005**: Add status and actual_weight fields

### Dependencies

```
fastapi==0.128.8
uvicorn==0.34.0
pydantic==2.12.5
pydantic-settings==2.7.1
sqlalchemy==2.0.46
alembic==1.18.4
psycopg2-binary==2.9.10
httpx==0.28.1
python-dotenv==1.0.1
apscheduler==3.11.0
```

### Project Structure

```
fastapi-scada-odoo/
├── alembic/
│   ├── versions/
│   │   ├── 20260212_0001_*.py
│   │   ├── 20260212_0002_*.py
│   │   ├── 20260212_0003_*.py
│   │   ├── 20260212_0004_*.py
│   │   └── 20260212_0005_*.py
│   └── env.py
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── admin.py
│   │       ├── auth.py
│   │       ├── health.py
│   │       ├── router.py
│   │       └── scada.py
│   ├── core/
│   │   ├── config.py
│   │   └── scheduler.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── middleware/
│   │   └── plc_middleware.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── tablesmo_batch.py
│   ├── services/
│   │   ├── mo_batch_service.py
│   │   └── odoo_auth_service.py
│   └── main.py
├── tests/
│   ├── check_mo_detail.py
│   ├── demo_auto_sync.py
│   ├── test_mo_sync.py
│   └── test_scheduler.py
├── .env
├── alembic.ini
├── middleware.md
├── requirements.txt
└── README.md
```

### Support & Contact

For issues, questions, or contributions:

- GitHub Issues: [Project Repository]
- Email: [Support Email]
- Documentation: [This File]

---

**Version:** 1.0.0  
**Last Updated:** February 12, 2026  
**Maintained by:** Development Team
