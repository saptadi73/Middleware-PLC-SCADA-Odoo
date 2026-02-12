# Quick Start Guide - PLC Write Service

## 📋 Prerequisites Check

Before testing, pastikan:
- ✅ Virtual environment aktif
- ✅ Dependencies installed
- ✅ PostgreSQL running
- ✅ Database migrations complete
- ✅ PLC/Simulator accessible
- ✅ .env configured correctly

## 🚀 Quick Test Steps

### Step 1: Start Application

```bash
# Activate virtual environment
cd C:\projek\fastapi-scada-odoo
venv\Scripts\activate

# Start FastAPI server
python -m uvicorn app.main:app --reload
```

Server akan running di: http://localhost:8000

### Step 2: Verify PLC Configuration

```bash
curl http://localhost:8000/api/plc/config
```

Expected response:
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

✅ Jika response di atas muncul, configuration sudah benar!

### Step 3: Run Automated Tests

```bash
# Window baru
cd C:\projek\fastapi-scada-odoo
venv\Scripts\activate
python test_plc_write.py
```

Test script akan menjalankan:
1. Get PLC config
2. Write single REAL field
3. Write ASCII field
4. Write multiple fields
5. Write MO from database

### Step 4: Manual API Testing

#### Test 1: Write BATCH Number

```bash
curl -X POST http://localhost:8000/api/plc/write-field ^
  -H "Content-Type: application/json" ^
  -d "{\"batch_name\":\"BATCH01\",\"field_name\":\"BATCH\",\"value\":1}"
```

#### Test 2: Write MO Name (ASCII)

```bash
curl -X POST http://localhost:8000/api/plc/write-field ^
  -H "Content-Type: application/json" ^
  -d "{\"batch_name\":\"BATCH01\",\"field_name\":\"NO-MO\",\"value\":\"WH/MO/00002\"}"
```

#### Test 3: Write Complete Batch

```bash
curl -X POST http://localhost:8000/api/plc/write-batch ^
  -H "Content-Type: application/json" ^
  -d "{\"batch_name\":\"BATCH01\",\"data\":{\"BATCH\":1,\"NO-MO\":\"WH/MO/00002\",\"NO-BoM\":\"JF PLUS 25\",\"finished_goods\":\"JF PLUS 25\",\"Quantity Goods_id\":2500}}"
```

#### Test 4: Write from Database

```bash
# First, ensure MO data exists in database
curl http://localhost:8000/api/sync/batch-status

# Then write to PLC
curl -X POST http://localhost:8000/api/plc/write-mo-batch ^
  -H "Content-Type: application/json" ^
  -d "{\"batch_no\":1,\"plc_batch_slot\":1}"
```

## 🔍 Verify Results

### Check API Logs

Monitor FastAPI logs untuk melihat:
- FINS communication details
- Memory addresses written
- Response codes from PLC

### Check PLC Memory

Gunakan PLC monitoring tool untuk verify:
- Address D7000 → BATCH number
- Address D7001-D7008 → NO-MO (ASCII)
- Address D7009-D7016 → NO-BoM (ASCII)
- dst...

## 🐛 Troubleshooting

### Error: "PLC connection timeout"

**Penyebab:**
- PLC tidak reachable
- IP/Port salah
- Firewall blocking UDP port 9600

**Solusi:**
```bash
# Test connectivity
ping 192.168.1.2

# Update .env jika IP berbeda
PLC_IP=<actual_plc_ip>
```

### Error: "Batch name not found"

**Penyebab:**
- Typo di batch_name
- MASTER_BATCH_REFERENCE.json tidak loaded

**Solusi:**
- Gunakan batch name valid: BATCH01-BATCH30
- Check file MASTER_BATCH_REFERENCE.json ada

### Error: "Field not found in batch"

**Penyebab:**
- Field name typo
- Field tidak ada di MASTER_BATCH_REFERENCE.json

**Solusi:**
- Check field name di MASTER_BATCH_REFERENCE.json
- Gunakan exact name (case-sensitive)

### Error: "Database record not found"

**Penyebab:**
- batch_no tidak ada di mo_batch table

**Solusi:**
```bash
# Check database
curl http://localhost:8000/api/sync/batch-status

# Trigger sync jika kosong
curl -X POST http://localhost:8000/api/sync/trigger-sync
```

## 📊 Expected Test Results

Jika semua berjalan lancar:

```
======================================================================
PLC WRITE SERVICE TEST
======================================================================

[Test 1] Get PLC Configuration...
  PLC IP: 192.168.1.2
  PLC Port: 9600
  Client Node: 1
  PLC Node: 2
  Batches Loaded: 30

[Test 2] Write Single Field (BATCH number)...
  ✓ Status: success
  ✓ Message: Field BATCH written to BATCH01

[Test 3] Write ASCII Field (NO-MO)...
  ✓ Status: success
  ✓ Written: WH/MO/00002

[Test 4] Write Multiple Fields (Batch Data)...
  ✓ Status: success
  ✓ Fields Written: 7

[Test 5] Write MO Batch from Database...
  ✓ Status: success
  ✓ MO ID: 5
  ✓ PLC Batch: BATCH01

======================================================================
TEST COMPLETED!
======================================================================
```

## 🎯 Next Steps

Setelah basic testing berhasil:

1. **Integration Testing**: Test dengan PLC real device
2. **Performance Testing**: Test write speed dan latency
3. **Error Recovery**: Test reconnection setelah PLC disconnect
4. **Workflow Integration**: Integrate dengan SCADA workflow
5. **Production Deployment**: Deploy ke production server

## 📚 Additional Resources

- [README.md](README.md) - Full project documentation
- [middleware.md](middleware.md) - Comprehensive technical docs
- [MASTER_BATCH_REFERENCE.json](MASTER_BATCH_REFERENCE.json) - Memory mapping reference

## 💡 Tips

1. **Development**: Gunakan PLC simulator untuk testing tanpa hardware
2. **Debugging**: Enable FastAPI debug logs dengan `--log-level debug`
3. **Monitoring**: Monitor logs untuk FINS frame hex dump
4. **Backup**: Backup PLC memory sebelum testing
5. **Testing**: Test dengan dummy values dulu sebelum production data

---

**Status**: ✨ PLC Write Service Ready for Testing!
**Last Updated**: 2024
