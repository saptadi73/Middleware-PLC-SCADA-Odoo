# FastAPI SCADA-Odoo Middleware

Middleware untuk integrasi SCADA PLC (Omron SYMAC CJ2M CPU31) dengan Odoo 14 menggunakan FastAPI.

## 🚀 Features

- **Auto-Sync Scheduler**: Fetch MO dari Odoo secara otomatis dengan smart-wait logic
- **PLC Write Service**: Write data ke PLC menggunakan FINS/UDP protocol
- **Memory Mapping**: MASTER_BATCH_REFERENCE.json sebagai referensi alamat memory PLC
- **JSON-RPC Client**: Komunikasi dengan Odoo menggunakan XML-RPC over JSON
- **Database Storage**: PostgreSQL untuk menyimpan MO batch data
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

## 🔄 Auto-Sync Scheduler

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

## 📚 MASTER_BATCH_REFERENCE.json

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

## 🧪 Testing

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

- `GET /api/plc/config` - Get PLC configuration
- `POST /api/plc/write-field` - Write single field
- `POST /api/plc/write-batch` - Write multiple fields
- `POST /api/plc/write-mo-batch` - Write MO from database

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

**System Status**: ✨ PLC Write Service Implemented & Ready for Testing
#   M i d d l e w a r e - P L C - S C A D A - O d o o  
 