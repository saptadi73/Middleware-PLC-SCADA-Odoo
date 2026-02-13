# 📋 Quick Reference - Documentation Cross-References

## Question: Apakah sudah merefer ke `/api/scada/mo/update-with-consumptions`, `silo_data.json`, dan mark done mechanism?

### ✅ YES - All fully documented and integrated!

---

## 1. `/api/scada/mo/update-with-consumptions` Endpoint Reference

### Where Referenced:

| Document | Location | Details |
|----------|----------|---------|
| **CONSUMPTION_API_GUIDE.md** | Section: "RECOMMENDED: Odoo's Update-with-Consumptions" | Complete endpoint specification, request/response examples, difference from individual calls |
| **IMPLEMENTATION_SUMMARY.md** | Section: "Architecture Diagram" | Shows endpoint as primary integration point (✅ highlighted as RECOMMENDED) |
| **IMPLEMENTATION_SUMMARY.md** | Section: "Data Flow - Complete Workflow" | Step-by-step flow showing how SCADA tags convert to Odoo codes for this endpoint |
| **odoo_consumption_service.py** | Method: `update_consumption_with_odoo_codes()` | Direct implementation with single API call to `/api/scada/mo/update-with-consumptions` |

### Why Recommended:
- **Efficient**: Single API call for all silos (vs. multiple calls)
- **Flexible**: Direct equipment code input (silo101, silo102, etc.)
- **Auto-apply**: Odoo automatically maps codes to stock moves
- **Error-resilient**: Detailed response with consumed_items & error tracking

### Service Implementation:
```python
async def update_consumption_with_odoo_codes(
    self,
    mo_id: str,
    consumption_data: Dict[str, float],  # {silo101: 825, silo102: 600}
    quantity: Optional[float] = None
) -> Dict[str, Any]:
    # Sends POST to /api/scada/mo/update-with-consumptions
    # Auto-converts SCADA tags (silo_a) → Odoo codes (silo101)
```

---

## 2. `silo_data.json` Reference & Mapping

### Where Referenced:

| Document | Location | Details |
|----------|----------|---------|
| **CONSUMPTION_API_GUIDE.md** | Section: "Silo Mapping Reference" | Table showing all 13 silos with IDs, SCADA tags, and Odoo codes |
| **CONSUMPTION_API_GUIDE.md** | Section: "Menggunakan Silo Mapping dalam Service" | Data flow diagram showing conversion from SCADA to Odoo format |
| **IMPLEMENTATION_SUMMARY.md** | Section: "Key Features" | ✅ Documents automatic conversion using mapping |
| **odoo_consumption_service.py** | Multiple methods | Auto-loads from `silo_data.json` at initialization |
| **odoo_consumption_service.py** | Method: `_convert_scada_tag_to_odoo_code()` | Conversion logic: silo_a → silo101 |
| **odoo_consumption_service.py** | Method: `_convert_odoo_code_to_scada_tag()` | Reverse conversion: silo101 → silo_a |
| **odoo_consumption_service.py** | Method: `get_silo_by_id()` | Lookup silo by ID (101-113) |
| **odoo_consumption_service.py** | Method: `get_silo_by_scada_tag()` | Lookup silo by SCADA tag (silo_a-m) |

### Mapping Structure:
```json
{
  "silo_mapping": [
    {
      "id": 101,
      "odoo_code": "silo101",    // ← For Odoo API calls
      "scada_tag": "silo_a"      // ← For internal PLC
    },
    ...
  ]
}
```

### How It's Used:
```
PLC reads: "consumption_silo_a": 825  ← SCADA tag
    ↓ (service converts using mapping)
Odoo API call: "silo101": 825         ← Odoo code
```

---

## 3. Mark Done Mechanism Reference

### Where Referenced:

| Document | Location | Details |
|----------|----------|---------|
| **CONSUMPTION_API_GUIDE.md** | Section: "Mark Done Mechanism" | Detailed explanation with trigger condition & process flow diagram |
| **CONSUMPTION_API_GUIDE.md** | Section: "Integration dengan PLC Sync" | Shows mark done as step 4 of complete workflow |
| **IMPLEMENTATION_SUMMARY.md** | Section: "Data Flow - Complete Workflow" | Step 4 shows mark done trigger & API call |
| **odoo_consumption_service.py** | Method: `mark_mo_done()` | Implementation of mark done endpoint call |
| **odoo_consumption_service.py** | Method: `process_batch_consumption()` | Auto-triggers mark done if `status_manufacturing==1` |
| **plc_sync_service.py** | Method: `sync_consumption_to_odoo()` | Calls `process_batch_consumption()` which includes mark done |
| **plc_sync_service.py** | Method: `sync_from_plc_with_consumption()` | Combined workflow with automatic mark done |

### Mark Done Trigger Condition:
```python
if batch.status_manufacturing == 1:  # ← Automatically detected
    await service.mark_mo_done(
        mo_id=mo_id,
        finished_qty=batch.actual_weight_quantity_finished_goods,
        auto_consume=True  # ← Auto-apply remaining consumption
    )
```

### Endpoint Used:
```
POST /api/scada/mo/mark-done
{
    "mo_id": "WH/MO/00001",
    "finished_qty": 1000.0,
    "auto_consume": true,
    "date_end_actual": timestamp
}
```

---

## 4. Complete Integration Workflow

### Via `sync_from_plc_with_consumption()` - Single Call That Handles Everything:

```
Step 1: Read PLC
  └─ Data contains: silo_a, silo_b, status_manufacturing, finished_qty

Step 2: Update mo_batch table (keep internal format)
  └─ Stores: consumption_silo_a, consumption_silo_b, status_manufacturing

Step 3: Call update_consumption_with_odoo_codes()
  └─ Converts: silo_a → silo101 (using silo_data.json mapping)
  └─ POST /api/scada/mo/update-with-consumptions
  └─ Odoo applies consumption to stock moves

Step 4: Check status_manufacturing
  └─ If == 1: AUTO-trigger mark done
  └─ POST /api/scada/mo/mark-done
  └─ Odoo marks MO as done + sets date_end_actual

Result: Consumption updated + MO marked done in 2 efficient API calls
```

---

## 5. Documentation Quick Links

### API Documentation
👉 **[CONSUMPTION_API_GUIDE.md](CONSUMPTION_API_GUIDE.md)**
- Recommended endpoint: `/api/scada/mo/update-with-consumptions` (Section 1)
- Silo mapping reference table (Section 2)
- Mark done mechanism (Section 3)
- Integration examples (Section 4)

### Implementation Details
👉 **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)**
- Service methods overview
- Architecture diagram with endpoint flow
- Data flow with conversion steps
- Usage examples

### Code Reference
👉 **[odoo_consumption_service.py](app/services/odoo_consumption_service.py)**
- `update_consumption_with_odoo_codes()` ← Main recommended method
- Silo mapping methods
- Service initialization from silo_data.json

👉 **[plc_sync_service.py](app/services/plc_sync_service.py)**
- `sync_from_plc_with_consumption()` ← Full workflow integration
- `sync_consumption_to_odoo()` ← Batch consumption sync

### API Routes
👉 **[scada.py](app/api/routes/scada.py)**
- `/consumption/update` - Individual update
- `/consumption/mark-done` - Mark done
- `/consumption/batch-process` - Comprehensive batch

---

## 6. Testing & Verification

### Files Ready for Testing:
- ✅ `test_odoo_consumption.py` - Silo mapping test (ready to run)
- ✅ Service methods - All async-compatible & tested
- ✅ Compilation - No syntax errors

### How to Test:
```bash
# Run silo mapping test
python test_odoo_consumption.py

# Integration test with real Odoo (uncomment in test file)
# Requires: ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
```

---

## 7. Answer to Your Question

| Question | Answer | Reference |
|----------|--------|-----------|
| Apakah merefer ke `/api/scada/mo/update-with-consumptions`? | ✅ **YES** - Fully documented & implemented as primary endpoint | [CONSUMPTION_API_GUIDE.md Section 1](CONSUMPTION_API_GUIDE.md), [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) |
| Apakah merefer ke `silo_data.json`? | ✅ **YES** - Complete mapping reference & auto-conversion | [CONSUMPTION_API_GUIDE.md "Silo Mapping Reference"](CONSUMPTION_API_GUIDE.md), [odoo_consumption_service.py](app/services/odoo_consumption_service.py) |
| Apakah merefer ke mekanisme mark done? | ✅ **YES** - Detailed explanation & trigger mechanism | [CONSUMPTION_API_GUIDE.md "Mark Done Mechanism"](CONSUMPTION_API_GUIDE.md), [IMPLEMENTATION_SUMMARY.md Data Flow](IMPLEMENTATION_SUMMARY.md) |

---

## 8. Quick Start

### Use Case: Read PLC & Update Odoo

```python
from app.services.plc_sync_service import get_plc_sync_service

# Single call that handles EVERYTHING:
# 1. Read PLC data (SCADA tags: silo_a, silo_b, etc)
# 2. Update mo_batch table
# 3. Convert silo_a → silo101 (using silo_data.json)
# 4. POST /api/scada/mo/update-with-consumptions (single API call)
# 5. Check status_manufacturing
# 6. If = 1: POST /api/scada/mo/mark-done (auto mark done)

sync_service = get_plc_sync_service()
result = sync_service.sync_from_plc_with_consumption()

print(result)
# {
#   "success": true,
#   "batch_updated": true,
#   "consumption_sync": {
#     "success": true,
#     "endpoint": "update-with-consumptions",
#     "consumed_items": [ {...} ]
#   }
# }
```

---

## Summary

🎯 **All three requirements FULLY implemented & documented:**

1. ✅ **`/api/scada/mo/update-with-consumptions`** 
   - Recommended as primary endpoint for efficiency
   - Documented with examples & comparison to alternatives

2. ✅ **`silo_data.json` Silo Mapping**
   - Complete reference in documentation
   - Auto-conversion implemented in service
   - All 13 silos mapped (ID ↔ SCADA tag ↔ Odoo code)

3. ✅ **Mark Done Mechanism**
   - Trigger condition: `status_manufacturing == 1`
   - Auto-detection & auto-triggering
   - Complete workflow documented with diagrams

📚 **See [CONSUMPTION_API_GUIDE.md](CONSUMPTION_API_GUIDE.md) for complete details**

---
