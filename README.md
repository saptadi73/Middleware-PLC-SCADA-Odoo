# FastAPI SCADA-Odoo Middleware

Middleware untuk integrasi SCADA PLC (Omron SYMAC CJ2M CPU31) dengan Odoo 14 menggunakan FastAPI.

## 🚀 Features

- **Auto-Sync Scheduler**: Fetch MO dari Odoo secara otomatis dengan smart-wait logic
- **Bidirectional PLC Communication**: 
  - **Write**: Send MO data ke PLC menggunakan FINS/UDP protocol
  - **Read**: Ambil actual consumption dan status dari PLC
  - **Sync**: Update database dengan data real-time dari PLC
- **Memory Mapping**: 
  - MASTER_BATCH_REFERENCE.json untuk write operations (D7000-D7418)
  - READ_DATA_PLC_MAPPING.json untuk read operations (D6001-D6058)
- **Smart Update**: Change detection - hanya update jika data berubah
- **JSON-RPC Client**: Komunikasi dengan Odoo menggunakan XML-RPC over JSON
- **Database Storage**: PostgreSQL dengan tracking actual consumption per silo
- **RESTful API**: FastAPI endpoints untuk CRUD operations

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Odoo 14 (running on localhost:8070)
- Omron PLC SYMAC CJ2M CPU31 (192.168.1.2:9600)
- Windows/Linux OS

## 🔧 Installation

### 1. Clone Repository

```bash
cd C:\projek\fastapi-scada-odoo
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy `.env` file dan sesuaikan:

```env
# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/plc

# Odoo Configuration
ODOO_URL=http://localhost:8070
ODOO_DATABASE=odoo14
ODOO_USERNAME=admin
ODOO_PASSWORD=yourpassword

# PLC Configuration
PLC_IP=192.168.1.2
PLC_PORT=9600
PLC_PROTOCOL=udp
PLC_TIMEOUT_SEC=2
CLIENT_NODE=1
PLC_NODE=2

# Auto-Sync Scheduler
AUTO_SYNC_ENABLED=true
SYNC_INTERVAL_MINUTES=60
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start Application

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 PLC Write API Usage

### 1. Check PLC Configuration

```bash
curl http://localhost:8000/api/plc/config
```

Response:
```json
{
  "status": "success",
  "data": {
    "plc_ip": "192.168.1.2",
    "plc_port": 9600,
    "client_node": 1,
    "plc_node": 2,
    "batches_loaded": 30
  }
}
```

### 2. Write Single Field

Write nilai ke satu field PLC:

```bash
curl -X POST http://localhost:8000/api/plc/write-field \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "BATCH01",
    "field_name": "BATCH",
    "value": 1
  }'
```

Response:
```json
{
  "status": "success",
  "message": "Field BATCH written to BATCH01",
  "data": {
    "batch_name": "BATCH01",
    "field_name": "BATCH",
    "value": 1,
    "address": "D7000",
    "word_count": 1
  }
}
```

### 3. Write ASCII Field

```bash
curl -X POST http://localhost:8000/api/plc/write-field \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "BATCH01",
    "field_name": "NO-MO",
    "value": "WH/MO/00002"
  }'
```

### 4. Write Multiple Fields

Write beberapa field sekaligus:

```bash
curl -X POST http://localhost:8000/api/plc/write-batch \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "BATCH01",
    "data": {
      "BATCH": 1,
      "NO-MO": "WH/MO/00002",
      "NO-BoM": "JF PLUS 25",
      "finished_goods": "JF PLUS 25",
      "Quantity Goods_id": 2500,
      "SILO 1 Consumption": 825.0
    }
  }'
```

### 5. Write MO from Database

Transfer data MO dari database ke PLC slot:

```bash
curl -X POST http://localhost:8000/api/plc/write-mo-batch \
  -H "Content-Type: application/json" \
  -d '{
    "batch_no": 1,
    "plc_batch_slot": 1
  }'
```

Response:
```json
{
  "status": "success",
  "message": "MO batch 1 written to PLC BATCH01",
  "data": {
    "mo_id": 5,
    "mo_name": "WH/MO/00002",
    "plc_batch_name": "BATCH01"
  }
}
```

## � PLC Read API Usage

### 1. Read Single Field

Read satu field dari PLC:

```bash
curl http://localhost:8000/api/plc/read-field/NO-MO
```

Response:
```json
{
  "status": "success",
  "message": "Read NO-MO from PLC",
  "data": {
    "field_name": "NO-MO",
    "value": "WH/MO/00002"
  }
}
```

### 2. Read Quantity Field

```bash
curl "http://localhost:8000/api/plc/read-field/Quantity%20Goods_id"
```

Response:
```json
{
  "status": "success",
  "message": "Read Quantity Goods_id from PLC",
  "data": {
    "field_name": "Quantity Goods_id",
    "value": 2500.0
  }
}
```

### 3. Read Silo Consumption (dengan scale)

```bash
curl "http://localhost:8000/api/plc/read-field/SILO%201%20Consumption"
```

Response:
```json
{
  "status": "success",
  "message": "Read SILO 1 Consumption from PLC",
  "data": {
    "field_name": "SILO 1 Consumption",
    "value": 825.0
  }
}
```

**Note**: Scale factor (10.0) otomatis diterapkan untuk REAL values.

### 4. Read All Fields

Read semua field sekaligus:

```bash
curl http://localhost:8000/api/plc/read-all
```

Response:
```json
{
  "status": "success",
  "message": "Read 37 fields from PLC",
  "data": {
    "NO-MO": "WH/MO/00002",
    "NO-BoM": "JF PLUS 25",
    "finished_goods": "JF PLUS 25",
    "Quantity Goods_id": 2500.0,
    "SILO ID 101 (SILO BESAR)": 101,
    "SILO 1 Consumption": 825.0,
    ...
  }
}
```

### 5. Read Formatted Batch Data

Read data batch dengan format terstruktur:

```bash
curl http://localhost:8000/api/plc/read-batch
```

Response:
```json
{
  "status": "success",
  "message": "Read batch data from PLC",
  "data": {
    "mo_id": "WH/MO/00002",
    "product_name": "JF PLUS 25",
    "bom_name": "JF PLUS 25",
    "quantity": 2500.0,
    "silos": {
      "a": {"id": 101, "consumption": 825.0},
      "b": {"id": 102, "consumption": 375.0},
      "c": {"id": 103, "consumption": 240.25},
      ...
    },
    "status": {
      "manufacturing": false,
      "operation": false
    },
    "weight_finished_good": 0.0
  }
}
```

## �🔄 Auto-Sync Scheduler

Auto-sync scheduler fetch MO dari Odoo setiap interval tertentu dengan smart-wait logic:

- **Smart-Wait**: Scheduler hanya fetch jika tabel `mo_batch` kosong
- **Interval**: Default 60 menit (configurable via `SYNC_INTERVAL_MINUTES`)
- **Batching**: Fetch 7 MO per sync session

### Monitor Scheduler

```bash
curl http://localhost:8000/api/sync/batch-status
```

### Manual Trigger

```bash
curl -X POST http://localhost:8000/api/sync/trigger-sync
```

### Clear Database

```bash
curl -X DELETE http://localhost:8000/api/sync/clear-mo-batch
```

## � PLC Sync API - Bidirectional Communication

PLC Sync Service membaca data dari PLC dan update database berdasarkan MO_ID.

### How It Works

1. **Read from PLC**: Menggunakan `READ_DATA_PLC_MAPPING.json` untuk membaca 37 fields
2. **Extract MO_ID**: Mendapatkan NO-MO dari PLC (contoh: "WH/MO/00002")
3. **Find Record**: Cari mo_batch berdasarkan MO_ID
4. **Smart Update**: Hanya update fields yang berubah
5. **Timestamp**: Set `last_read_from_plc` dengan waktu sinkronisasi

### Fields yang Diupdate

**Actual Consumption (13 silos):**
- `actual_consumption_silo_a` - SILO 1 Consumption (D6027)
- `actual_consumption_silo_b` - SILO 2 Consumption (D6029)
- `actual_consumption_silo_c` - SILO ID 103 Consumption (D6031)
- ... hingga `actual_consumption_silo_m` (D6051)

**Status & Weight:**
- `actual_weight_quantity_finished_goods` - weight_finished_good (D6058)
- `status_manufacturing` - status manufaturing (D6056)
- `status_operation` - Status Operation (D6057)

**Metadata:**
- `last_read_from_plc` - Timestamp saat terakhir dibaca

### Sync from PLC

```bash
curl -X POST http://localhost:8000/api/plc/sync-from-plc
```

Response (data berubah):
```json
{
  "status": "success",
  "message": "Batch data updated successfully",
  "data": {
    "mo_id": "WH/MO/00002",
    "updated": true
  }
}
```

Response (data tidak berubah):
```json
{
  "status": "success",
  "message": "No changes detected, skip update",
  "data": {
    "mo_id": "WH/MO/00002",
    "updated": false
  }
}
```

### Use Case: Periodic Monitoring

PLC Sync ideal untuk:
- **Real-time monitoring**: Cek actual consumption vs planned
- **Production tracking**: Monitor status manufacturing/operation
- **Quality control**: Verifikasi actual weight vs target
- **Data validation**: Bandingkan data PLC dengan database

**Example Workflow:**
```bash
# 1. Write MO to PLC
curl -X POST http://localhost:8000/api/plc/write-mo-batch \
  -H "Content-Type: application/json" \
  -d '{"batch_no": 1, "plc_batch_slot": 1}'

# 2. PLC runs manufacturing process...
# (actual consumption data updates in PLC)

# 3. Sync actual data back to database
curl -X POST http://localhost:8000/api/plc/sync-from-plc

# 4. Check updated data in database
# actual_consumption_silo_* now contains real values from PLC
```
## 🗺️ PLC Memory Areas

Sistem menggunakan dua area memory PLC yang berbeda:

### **WRITE Area (D7000-D7418)** - Production Commands
- **Purpose**: Send manufacturing orders dari Middleware → PLC
- **Mapping**: MASTER_BATCH_REFERENCE.json
- **Batches**: 30 slots (BATCH01-BATCH30)
- **Fields per Batch**: 37 fields (MO, product, silos, status)
- **Use Case**: Write MO dari Odoo/Database ke PLC untuk production

### **READ Area (D6001-D6058)** - Production Feedback
- **Purpose**: Read actual data dari PLC → Middleware
- **Mapping**: READ_DATA_PLC_MAPPING.json
- **Fields**: 37 fields (current MO, actual consumption, status)
- **Use Case**: Monitor production progress, actual consumption, equipment status

### **Memory Addressing**
```
┌─────────────────────────────────────────────────┐
│  D6001-D6058  │ READ Area (Current Production)  │
│               │ - Actual consumption            │
│               │ - Real-time status              │
│               │ - Weight finished goods         │
├───────────────┴─────────────────────────────────┤
│                                                  │
│  D7000-D7418  │ WRITE Area (30 Batch Slots)    │
│               │ - MO queue                      │
│               │ - Planned consumption           │
│               │ - Production parameters         │
└──────────────────────────────────────────────────┘
```

**Workflow:**
1. **WRITE**: Middleware send MO → D7000-D7418 (queue of 30 batches)
2. **PLC Process**: PLC execute production, update D6001-D6058
3. **READ**: Middleware read D6001-D6058 → actual consumption
4. **SYNC**: Update database dengan actual values
## �📚 MASTER_BATCH_REFERENCE.json

Memory mapping reference untuk PLC communication:

```json
{
  "BATCH01": {
    "BATCH": {
      "address": "D7000",
      "data_type": "REAL",
      "id": "0001"
    },
    "NO-MO": {
      "address": "D7001-7008",
      "data_type": "ASCII",
      "id": "0002"
    },
    ...
  },
  "BATCH02": { ... },
  ...
  "BATCH30": { ... }
}
```

**Structure:**
- **30 Batches**: BATCH01 - BATCH30
- **37 Fields per Batch**: BATCH, NO-MO, NO-BoM, finished_goods, quantity, 13 silos, status
- **Data Types**: REAL, ASCII, boolean
- **Addressing**: Single (D7000) or Range (D7001-7008)

## 📖 READ_DATA_PLC_MAPPING.json

Memory mapping reference untuk PLC read operations:

```json
{
  "meta": {
    "total_points": 37,
    "address_range": "D6001-D6058"
  },
  "raw_list": [
    {
      "No": 1,
      "Informasi": "NO-MO",
      "Data Type": "ASCII",
      "length": 16,
      "DM - Memory": "D6001-6008"
    },
    {
      "No": 6,
      "Informasi": "SILO 1 Consumption",
      "Data Type": "REAL",
      "scale": 10.0,
      "DM - Memory": "D6027"
    },
    ...
  ]
}
```

**Structure:**
- **37 Fields**: NO-MO, finished_goods, quantity, 13 silos (ID + consumption), status
- **Address Range**: D6001 - D6058
- **Data Types**: ASCII, REAL (with scale factor), boolean
- **Scale Factors**: 
  - Consumption: 10.0 (nilai PLC 8250 = 825.0 kg)
  - Quantity: 1.0 (no scaling)

**Field Mapping:**
- D6001-6008: NO-MO (ASCII, 16 chars)
- D6017-6024: finished_goods (ASCII, 16 chars)
- D6025: Quantity Goods_id (REAL, scale=1.0)
- D6027, D6029, D6031, ..., D6051: Silo Consumptions (REAL, scale=10.0)
- D6056: status manufaturing (boolean)
- D6057: Status Operation (boolean)
- D6058: weight_finished_good (REAL, scale=1.0)

## 🧪 Testing

### PLC Write Tests

Run test script untuk validate PLC write service:

```bash
python test_plc_write.py
```

Test coverage:
1. ✓ Get PLC configuration
2. ✓ Write single REAL field
3. ✓ Write ASCII field
4. ✓ Write multiple fields
5. ✓ Write MO batch from database

### PLC Read Tests

Run test script untuk validate PLC read service:

```bash
# Test via HTTP API
python test_plc_read.py

# Test direct (tanpa HTTP)
python test_plc_read_direct.py
```

Test coverage:
1. ✓ Read single field (ASCII)
2. ✓ Read single field (REAL with scale)
3. ✓ Read all fields
4. ✓ Read formatted batch data

### PLC Sync Tests

Test PLC data synchronization ke database:

```bash
# Test sync only
python test_plc_sync.py

# Test full workflow: Write → Read → Sync
python test_plc_workflow.py
```

Test `test_plc_workflow.py` melakukan:
1. ✓ Write MO batch dari database ke PLC
2. ✓ Read batch data dari PLC
3. ✓ Sync data PLC ke database (update actual consumption)
4. ✓ Verify change detection (no update jika data sama)

Fitur PLC Sync:
- Update `actual_consumption_silo_a` s/d `actual_consumption_silo_m` dari PLC
- Update `actual_weight_quantity_finished_goods` dari field `weight_finished_good`
- Update `status_manufacturing` dan `status_operation`
- Set `last_read_from_plc` timestamp
- **Smart update**: Hanya update jika ada perubahan data

### Write to READ Area (Testing Helper)

Script khusus untuk simulasi data PLC pada READ area (D6001-D6058):

```bash
python test_write_read_area.py
```

Workflow:
1. ✓ Read batch_no=1 dari database
2. ✓ Write data ke PLC READ area (D6001-D6058)
3. ✓ Menggunakan mapping dari READ_DATA_PLC_MAPPING.json

**Use Case:**
- Testing read & sync functionality tanpa PLC real
- Simulasi data PLC untuk development
- Verify mapping field antara database ↔ PLC

**Next Steps setelah write:**
```bash
# Read data dari PLC
python test_plc_read.py

# Sync ke database
python test_plc_sync.py

# Or run complete cycle test
python test_complete_cycle.py
```

**Complete Cycle Test:**

Test lengkap yang verify seluruh flow:

```bash
python test_complete_cycle.py
```

Test ini melakukan:
1. ✓ Read MO_ID dari PLC (D6001-6008)
2. ✓ Read product & quantity
3. ✓ Read silo consumptions
4. ✓ Read complete batch data
5. ✓ Sync ke database (update actual_consumption_*)
6. ✓ Re-sync untuk verify change detection
7. ✓ Display summary

### Write dari Odoo ke PLC

Test complete workflow: Odoo → Database → PLC:

```bash
python test_plc_write_from_odoo.py
```

Workflow:
1. Clear mo_batch table
2. Fetch MO list dari Odoo (7 MO)
3. Map MO data to PLC format
4. Write to PLC slots BATCH01-BATCH07

## 📖 Documentation

Comprehensive documentation tersedia di [middleware.md](middleware.md):

- Installation & Setup
- Configuration Guide
- API Endpoints Reference
- Database Schema
- PLC Integration Details
- Troubleshooting Guide
- Production Deployment

## 🛠️ Tech Stack

- **FastAPI**: 0.128.8 - Web framework
- **SQLAlchemy**: 2.0.46 - ORM
- **Alembic**: 1.18.4 - Database migrations
- **Pydantic**: 2.12.5 - Data validation
- **httpx**: 0.28.1 - Async HTTP client
- **APScheduler**: 3.11.0 - Background scheduler
- **PostgreSQL**: 12+ - Database
- **FINS Protocol**: UDP - PLC communication

## 🏗️ Project Structure

```
fastapi-scada-odoo/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── plc.py           # PLC write endpoints
│   │       ├── sync.py          # Auto-sync endpoints
│   │       └── router.py        # Main router
│   ├── core/
│   │   ├── config.py            # Config management
│   │   └── database.py          # DB connection
│   ├── models/
│   │   └── mo_batch.py          # SQLAlchemy models
│   ├── schemas/
│   │   └── mo_batch.py          # Pydantic schemas
│   ├── services/
│   │   ├── odoo_service.py      # Odoo JSON-RPC client
│   │   ├── plc_write_service.py # PLC write service
│   │   ├── fins_client.py       # FINS UDP client
│   │   └── fins_frames.py       # FINS frame builder
│   └── main.py                  # FastAPI app
├── alembic/
│   └── versions/                # Database migrations
├── MASTER_BATCH_REFERENCE.json  # Memory mapping
├── requirements.txt             # Dependencies
├── .env                         # Environment config
├── middleware.md                # Comprehensive docs
├── test_plc_write.py            # Test script
└── README.md                    # This file
```

## 🐛 Troubleshooting

### PLC Connection Timeout

```bash
# Check PLC is reachable
ping 192.168.1.2

# Verify port is open
telnet 192.168.1.2 9600
```

### Database Connection Error

```bash
# Check PostgreSQL is running
psql -U user -d plc -h localhost

# Run migrations
alembic upgrade head
```

### Odoo Authentication Failed

```bash
# Verify Odoo credentials in .env
# Test Odoo connection
curl http://localhost:8070/web/database/list
```

## 📞 API Endpoints

### PLC Operations

**Write Operations:**
- `POST /api/plc/write-field` - Write single field
- `POST /api/plc/write-batch` - Write multiple fields
- `POST /api/plc/write-mo-batch` - Write MO from database

**Read Operations:**
- `GET /api/plc/read-field/{field_name}` - Read single field
- `GET /api/plc/read-all` - Read all fields
- `GET /api/plc/read-batch` - Read formatted batch data

**Sync Operations:**
- `POST /api/plc/sync-from-plc` - Read from PLC and update database based on MO_ID

**Configuration:**
- `GET /api/plc/config` - Get PLC configuration

### Auto-Sync Operations

- `GET /api/sync/batch-status` - Get batch status
- `POST /api/sync/trigger-sync` - Manual sync trigger
- `DELETE /api/sync/clear-mo-batch` - Clear database

### Health Check

- `GET /health` - API health status

## 📝 License

Proprietary - Internal Use Only

## 👤 Author

FastAPI SCADA-Odoo Integration Team

---

**System Status**: ✨ Bidirectional PLC Communication - Read/Write/Sync Fully Implemented
#   M i d d l e w a r e - P L C - S C A D A - O d o o 
 
 