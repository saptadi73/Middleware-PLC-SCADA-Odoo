# PLC Read → Odoo Consumption Test Scripts

Comprehensive test scripts untuk read PLC memory dan direct update Odoo MO consumption.

## Overview

### Workflow

```
PLC Memory (FINS Protocol)
        ↓
  PLCReadService.read_batch_data()
        ↓
  Format untuk Odoo API
        ↓
  OdooConsumptionService.update_consumption_with_odoo_codes()  [SINGLE EFFICIENT CALL]
        ↓
  Odoo MO Consumption Updated ✓
        ↓
  Auto Mark-Done jika status_manufacturing = 1 (optional)
        ↓
  Workflow Complete
```

## Test Scripts

### 0. **test_write_read_area_from_odoo.py** (READ Area Feeder)

**Purpose**: Feed PLC READ area dari Odoo MO list untuk persiapan test read/sync.

**Run**:
```bash
python test_write_read_area_from_odoo.py --loop --limit 10 --interval-seconds 10 --write-retries 3
```

**Behavior**:
- Status di READ area selalu dipaksa:
  - `status_manufacturing = 1`
  - `status_operation = 0`

Use this before `test_plc_read_quick.py` or `test_plc_read_update_odoo.py` when you want automatic test data refresh from Odoo.

---

### 1. **test_plc_read_quick.py** (Quick Verification)

**Purpose**: Quick PLC read test untuk verify connection dan consumption data mapping.

**Features**:
- Synchronous (no async)
- Fast execution
- JSON output untuk inspection
- Ideal untuk development & debugging

**When to use**:
- Verify PLC is reachable
- Check consumption data mapping
- Quick development checks
- Before running full integration test

**Run**:
```bash
python test_plc_read_quick.py
```

**Output**:
```
MO Information:
  ID: WH/MO/00001
  Product: Product A
  BoM: BoM/001
  Quantity: 1000

Status:
  Manufacturing: True
  Operation: False
  Finished Weight: 950

Silo Consumption:
  ✓ Silo A (ID 101):       825.5
  ✓ Silo B (ID 102):       600.3
  ○ Silo C (ID 103):           0
  ...
```

---

### 2. **test_plc_read_update_odoo.py** (Full Integration)

**Purpose**: Complete workflow dari PLC read hingga Odoo consumption update.

**Features**:
- Asynchronous operations
- Step-by-step execution
- Direct Odoo update menggunakan efficient `/update-with-consumptions` endpoint
- Auto mark-done trigger
- Comprehensive logging & error handling
- Detailed progress output

**When to use**:
- End-to-end integration testing
- Production workflow validation
- After PLC & Odoo connectivity verified
- Load testing with real data

**Run**:
```bash
python test_plc_read_update_odoo.py
```

**Workflow Steps**:
1. Read batch data dari PLC
2. Format data untuk Odoo
3. Update MO consumption di Odoo (single efficient API call)
4. Mark MO as done (jika status_manufacturing = 1)

**Output**:
```
[STEP 1] Read Batch Data from PLC
✓ MO ID: WH/MO/00001
✓ Product: Product A
✓ BoM: BoM/001
✓ Quantity: 1000
✓ Status Manufacturing: True
✓ Status Operation: False
✓ Weight Finished: 950

✓ Silos Consumption:
    Silo a (ID 101): 825.5
    Silo b (ID 102): 600.3

[STEP 2] Format Batch Data for Odoo
✓ Formatted MO ID: WH/MO/00001
✓ Equipment: PLC01
✓ Consumption entries: 2
    - silo_a: 825.5
    - silo_b: 600.3

[STEP 3] Update MO Consumption in Odoo
Calling update_consumption_with_odoo_codes()...
✓ Consumption updated successfully
  - Status: success
  - Message: MO consumption updated
  - Items consumed: 2

[STEP 4] Mark MO as Done (if status_manufacturing=1)
Calling mark_mo_done()...
✓ MO marked as done successfully
  - Status: success
  - Message: MO marked as done

SUMMARY
✓ PLC Read: OK
✓ Format: OK
✓ Odoo Update: OK
✓ Mark Done: OK
```

---

## API Endpoints Used

### `/api/scada/mo/update-with-consumptions`

**Method**: POST

**Purpose**: Efficient single-call update untuk MO consumption dengan semua silo at once.

**Request**:
```json
{
  "mo_id": "WH/MO/00001",
  "consumption_data": {
    "silo101": 825.5,
    "silo102": 600.3,
    ...
  },
  "quantity": 950
}
```

**Response**:
```json
{
  "success": true,
  "status": "success",
  "message": "MO consumption updated",
  "consumed_items": ["silo101", "silo102"],
  "endpoint": "update-with-consumptions"
}
```

**Benefits**:
- Single API call (not N calls per component)
- More efficient
- Auto-converts SCADA tags to Odoo codes
- Lower latency

---

### `/api/scada/mo/mark-done`

**Method**: POST

**Purpose**: Mark Manufacturing Order sebagai done dengan finished qty.

**Request**:
```json
{
  "mo_id": "WH/MO/00001",
  "finished_qty": 950,
  "equipment_id": "PLC01",
  "auto_consume": true
}
```

**Response**:
```json
{
  "success": true,
  "status": "success",
  "message": "MO marked as done"
}
```

**Auto-Trigger**: Automatically called jika `status_manufacturing = 1` dalam PLC data.

---

## PLC Data Mapping

Data dibaca dari PLC sesuai `READ_DATA_PLC_MAPPING.json`:

```
NO-MO                           → mo_id
finished_goods                  → product_name
NO-BoM                          → bom_name
Quantity Goods_id               → quantity
status manufacturing            → status_manufacturing
SILO [n] ID [silo_id]          → silo ID
SILO [n] Consumption (scaled)  → consumption value
weight_finished_good            → finished_qty
```

---

## Services Integration

### PLCReadService

**File**: `app/services/plc_read_service.py`

**Key Methods**:
```python
# Read single field from PLC
service.read_field(field_name: str) -> Any

# Read all fields from PLC
service.read_all_fields() -> Dict[str, Any]

# Read formatted batch data (MO + silos + status)
service.read_batch_data() -> Dict[str, Any]
```

### OdooConsumptionService

**File**: `app/services/odoo_consumption_service.py`

**Key Methods**:
```python
# ✓ RECOMMENDED: Single efficient call
await service.update_consumption_with_odoo_codes(
    mo_id: str,
    consumption_data: Dict[str, float],  # {silo101: 825.5, ...}
    quantity: Optional[float]
) -> Dict[str, Any]

# Auto mark-done (triggered if status_manufacturing=1)
await service.mark_mo_done(
    mo_id: str,
    finished_qty: float,
    equipment_id: str,
    auto_consume: bool
) -> Dict[str, Any]

# Process batch (calls above two methods)
await service.process_batch_consumption(
    mo_id: str,
    equipment_id: str,
    batch_data: Dict[str, Any]
) -> Dict[str, Any]
```

---

## Prerequisites

### 1. **PLC Connection**
- PLC reachable via FINS UDP
- Configure in `.env`:
  ```
  PLC_IP=192.168.1.100
  PLC_PORT=9600
  ```

### 2. **Odoo API**
- Odoo running with SCADA module
- API credentials in `.env`:
  ```
  ODOO_BASE_URL=http://odoo-server:8069
  ODOO_USERNAME=admin
  ODOO_PASSWORD=password
  ```

### 3. **Database**
- Migrations applied: `alembic upgrade head`
- Tables: `mo_batch`, `mo_histories`

### 4. **PLC Memory Mapping**
- `READ_DATA_PLC_MAPPING.json` configured
- Fields for MO, silos, status defined

---

## Configuration

### `.env` File

```env
# PLC Configuration
PLC_IP=192.168.1.100
PLC_PORT=9600
PLC_NETWORK_NUMBER=0
PLC_UNIT_ID=0

# Odoo Configuration
ODOO_BASE_URL=http://localhost:8069
ODOO_USERNAME=admin
ODOO_PASSWORD=admin

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/scada_odoo

# Logging
LOG_LEVEL=INFO
```

### `READ_DATA_PLC_MAPPING.json`

Structure:
```json
{
  "raw_list": [
    {
      "Informasi": "NO-MO",
      "Type": "ASCII",
      "Data Type": "ASCII",
      "DM Address": "D6001-6006",
      "Remark": "Manufacturing Order ID"
    },
    {
      "Informasi": "SILO 1 Consumption",
      "Type": "REAL",
      "Data Type": "REAL",
      "DM Address": "D6050-6051",
      "Scale": 0.1,
      "Remark": "Silo A consumption with scale"
    },
    ...
  ]
}
```

---

## Usage Examples

### Example 1: Quick PLC Check
```bash
python test_plc_read_quick.py
```
Output: MO data dan consumption from PLC

### Example 2: Full Integration Test
```bash
python test_plc_read_update_odoo.py
```
Output: Complete workflow from PLC → Odoo

### Example 3: In-Code Usage
```python
import asyncio
from app.services.plc_read_service import get_plc_read_service
from app.services.odoo_consumption_service import get_consumption_service

async def sync_workflow():
    # Read PLC
    plc_service = get_plc_read_service()
    batch_data = plc_service.read_batch_data()
    
    # Update Odoo
    odoo_service = get_consumption_service()
    result = await odoo_service.process_batch_consumption(
        mo_id=batch_data["mo_id"],
        equipment_id="PLC01",
        batch_data=batch_data
    )
    
    return result

asyncio.run(sync_workflow())
```

---

## Troubleshooting

### Issue: PLC Connection Failed
```
✗ Error reading PLC data: Connection refused
```
**Solution**:
- Verify PLC IP & Port in `.env`
- Check PLC is powered on
- Run: `ping <PLC_IP>`

### Issue: Odoo Authentication Failed
```
✗ Error: Failed to authenticate with Odoo
```
**Solution**:
- Verify ODOO_BASE_URL in `.env`
- Check ODOO_USERNAME & ODOO_PASSWORD
- Verify Odoo SCADA module installed: `http://odoo-server:8069/web`

### Issue: MO Not Found in Odoo
```
✗ Error: MO WH/MO/00001 not found in Odoo
```
**Solution**:
- Sync MO list first: `python test_mo_batch_process.py` (step 2)
- Or use endpoint: `POST /api/scada/mo-list-detailed`

### Issue: Silo ID Mismatch
```
✗ Error: Silo 101 not found in silo_data.json mapping
```
**Solution**:
- Verify `silo_data.json` has all silo IDs: 101-113
- Check if PLC returns valid silo IDs

---

## API Endpoints Comparison

| Endpoint | Method | Use Case | Efficiency | Auto Convert |
|----------|--------|----------|-----------|--------------|
| `/consumption/update` | POST | **Manual** per-component | Low (N calls) | Manual |
| `/consumption/batch-process` | POST | **Automated** batch ✓ | High (1 call) | Auto ✓ |
| `/consumption/mark-done` | POST | Mark MO done | N/A | N/A |

**Recommendation**: Use `/consumption/batch-process` untuk automated workflows.

---

## Logging

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Log Files
- Stdout untuk quick tests
- Check application logs untuk production

---

## Performance Notes

### PLC Read
- Speed: ~100-200ms per field
- Depends: Network latency, PLC CPU load
- Optimize: Read only needed fields

### Odoo Update
- Single call: ~500-1000ms
- Auto mark-done: +200-300ms extra
- Network: Latency affects most

### Total Workflow
- Quick test: ~2-5 seconds
- Full integration: ~2-3 seconds

---

## Next Steps

1. ✓ Run: `python test_plc_read_quick.py`
2. ✓ Verify: PLC data dan consumption mapping
3. ✓ Run: `python test_plc_read_update_odoo.py`
4. ✓ Check: OdooMO consumption updated
5. ✓ Monitor: Logs untuk errors

---

## References

- [PLC Middleware Documentation](../middleware.md)
- [API Specification](../data/API_SPEC.md)
- [Odoo SCADA Module](https://github.com/odoo-scada)
- [FINS Protocol Documentation](https://en.wikipedia.org/wiki/FINS)
