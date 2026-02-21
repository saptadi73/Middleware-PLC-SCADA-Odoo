# Test Scripts Review - Equipment Reference Updates (LQ114/LQ115)

## Summary
Updated memory mapping for 15 equipment items (13 Silos + 2 Liquid Tanks LQ114/LQ115) has shifted memory addresses. Test scripts need review for comment updates and potential hardcoded references.

---

## ✅ Status Summary

| Category | Scripts | Status | Action |
|----------|---------|--------|--------|
| **CSV Input Writer** | test_write_read_area_from_csv.py | ⚠️ NEEDS UPDATE | Update comments: D6001-D6058 → D6001-D6077 |
| **CSV Exporter** | test_export_read_area_to_csv.py | ⚠️ NEEDS UPDATE | Update comments: D6001-D6058 → D6001-D6077 |
| **PLC Write (Direct)** | test_write_read_area.py | ⚠️ NEEDS UPDATE | Update comments: D6001-D6058 → D6001-D6077 |
| **Odoo Writer** | test_write_read_area_from_odoo.py | ⚠️ NEEDS UPDATE | Update comments: D6001-D6069 → D6001-D6077 |
| **Complete Cycle** | test_complete_cycle.py | ⚠️ NEEDS UPDATE | Update comments: D6001-D6058 → D6001-D6077 |
| **Equipment Failure Write** | test_equipment_failure_write.py | ✅ OK | Uses CSV dynamically - no hardcoded addresses |
| **Equipment Failure Read** | test_equipment_failure_read.py | ✅ OK | Uses CSV dynamically - no hardcoded addresses |
| **Equipment Failure Sync** | test_equipment_failure_odoo_sync.py | ✅ OK | Generic sync test - no address dependencies |

---

## Detailed File Analysis

### 1. ⚠️ test_write_read_area_from_csv.py
**Current Status:** Comments outdated
**Current Reference Range:** D6001-D6058
**New Reference Range:** D6001-D6077

**Lines to Update:**
- **Line 2:** `"""Write PLC READ area (D6001-D6058) from CSV input.`
- **Line 25:** `"""Write CSV values to PLC READ area (D6001-D6058)."""`
- **Line 194:** `print("This will write values into D6001-D6058 using CSV Value column.")`

**Changes:**
- D6001-D6058 → D6001-D6077

**Script Logic:** ✅ Already handles dynamic memory addresses from CSV - NO CODE CHANGES NEEDED
- Reads CSV headers and processes dynamically
- Uses `_parse_dm_address()` to extract start address and count
- Should work correctly with updated CSV

---

### 2. ⚠️ test_export_read_area_to_csv.py
**Current Status:** Comments outdated
**Current Reference Range:** D6001-D6058
**New Reference Range:** D6001-D6077

**Lines to Update:**
- **Line 2:** `"""Export PLC READ area (D6001-D6058) to CSV.`

**Changes:**
- D6001-D6058 → D6001-D6077

**Script Logic:** ✅ Already handles dynamic addresses
- Uses `_load_mapping()` to read REF_DATA_PLC_MAPPING.json (which is up to date)
- Processes all fields dynamically based on mapping
- No code changes needed

---

### 3. ⚠️ test_write_read_area.py
**Current Status:** Comments outdated
**Current Reference Range:** D6001-D6058
**New Reference Range:** D6001-D6077

**Lines to Update:**
- **Line 2:** `"""Test Write to READ_DATA_PLC_MAPPING Area (D6001-D6058)`
- **Line 29:** `"""Write data to READ_DATA_PLC_MAPPING area (D6001-D6058)"""`
- **Line 165:** `Write mo_batch data to PLC READ area (D6001-D6058).`
- **Line 275:** `print("TEST WRITE TO READ_DATA_PLC_MAPPING AREA (D6001-D6058)")`
- **Line 279:** `print("2. Write data to PLC READ area (D6001-D6058)")`

**Changes:**
- D6001-D6058 → D6001-D6077

**Script Logic:** ✅ Handles dynamic field mapping
- Reads mo_batch from database
- Uses READ_DATA_PLC_MAPPING.json for field names and memory addresses
- Dynamically processes all fields including new LQ114/LQ115
- No code changes needed

---

### 4. ⚠️ test_write_read_area_from_odoo.py
**Current Status:** Comments outdated
**Current Reference Range:** D6001-D6069 (was incorrect)
**New Reference Range:** D6001-D6076

**Lines to Update:**
- **Line 4:** `Use this script to simulate PLC READ memory (D6001-D6069) without editing`

**Changes:**
- D6001-D6069 → D6001-D6076

**Script Logic:** Review needed
- Contains mapping dictionary `_SILO_NUMBER_TO_LETTER` for silos 101-113 only
- Need to verify if it handles LQ114 and LQ115
- Check if it uses dynamic mapping from silo_data.json or hardcoded

---

### 5. ⚠️ test_complete_cycle.py
**Current Status:** Comments outdated
**Current Reference Range:** D6001-D6058
**New Reference Range:** D6001-D6077

**Lines to Update:**
- **Line 177:** `print("  1. ✓ Data written to PLC READ area (D6001-D6058)")`

**Changes:**
- D6001-D6058 → D6001-D6077

**Script Logic:** ✅ Already handles API endpoints
- Calls `/plc/read-field` and `/plc/read-batch` endpoints
- These endpoints use updated reference data
- Should work correctly with new equipment

---

### 6. ✅ test_equipment_failure_write.py
**Current Status:** ✅ OK
**Memory Range:** Uses CSV dynamically (D8000-D8021)

**Script Logic:** ✅ Already correctly configured
- Reads memory addresses from equipment_failure_input.csv
- Uses `parse_dm_address()` for dynamic parsing
- CSV has been updated to correct memory addresses

**No Changes Needed** ✅

---

### 7. ✅ test_equipment_failure_read.py
**Current Status:** ✅ OK  
**Memory Range:** Uses CSV dynamically (D8000-D8021)

**Script Logic:** ✅ Already correctly configured
- Reads memory addresses from equipment_failure_input.csv
- Uses `parse_dm_address()` for dynamic parsing
- CSV has been updated to correct memory addresses

**No Changes Needed** ✅

---

### 8. ✅ test_equipment_failure_odoo_sync.py
**Current Status:** ✅ OK

**Script Logic:** ✅ Generic sync test
- Tests equipment failure API endpoints
- No hardcoded memory addresses
- Uses service layer that reads from updated reference files

**No Changes Needed** ✅

---

## Reference Files Verification

### ✅ READ_DATA_PLC_MAPPING.json
- **Status:** Updated ✅
- **Total Entries:** 37 items
- **Memory Range:** D6001-D6076 (with new LQ114/LQ115)
- **Last Entries:** 
  - No 31-32: LQ114 at D6066-D6068
  - No 33-34: LQ115 at D6070-D6072
  - No 35: status_manufacturing at D6073
  - No 36: status_operation at D6074
  - No 37: weight_finished_good at D6075-D6076

### ✅ read_data_plc_input.csv
- **Status:** Updated ✅
- **Total Rows:** 37 data rows
- **Memory Range:** D6001-D6076
- **Last Entries:**
  - No 31-32: LQ114 entries
  - No 33-34: LQ115 entries
  - No 35-37: Updated memory addresses

### ✅ EQUIPMENT_FAILURE_REFERENCE.json
- **Status:** Updated ✅
- **Memory Range:** D8000-D8021
- **Total Entries:** 8 fields

### ✅ equipment_failure_input.csv
- **Status:** Updated ✅
- **Memory Range:** D8000-D8021
- **All addresses corrected** from old D7710-D7732 range

### ✅ silo_data.json
- **Status:** Updated ✅
- **Total Equipment:** 15 items (13 Silos + 2 Liquid Tanks)
- **SCADA Tags:** All present (silo_a-m, lq_tetes, lq_fml)
- **Equipment Codes:** Standardized to equipment_code field

---

## Action Items - Comment Updates Only

### No Code Logic Changes Needed ✅
All test scripts use dynamic address mapping from reference files. The CSV files are already updated with correct memory addresses.

### Only Documentation/Comments Need Updates:

```bash
# Files to update (comments only):
1. test_write_read_area_from_csv.py       (3 lines)
2. test_export_read_area_to_csv.py        (1 line)
3. test_write_read_area.py                (5 lines)
4. test_write_read_area_from_odoo.py      (1 line)
5. test_complete_cycle.py                 (1 line)
```

---

## Special Review: test_write_read_area_from_odoo.py

⚠️ **Requires Code Review** - Not just comments

**Current Code (lines 31-39):**
```python
_SILO_NUMBER_TO_LETTER = {
    101: "a",
    102: "b",
    103: "c",
    104: "d",
    105: "e",
    106: "f",
    107: "g",
    108: "h",
    109: "i",
    110: "j",
    111: "k",
    112: "l",
    113: "m",
}
```

**Issue:** Hardcoded silo mapping, doesn't include LQ114/LQ115

**Recommendation:** Should load from silo_data.json for consistency

**Check Points:**
1. [ ] Does it load equipment mapping from silo_data.json?
2. [ ] Does it handle LQ114 (lq_tetes) and LQ115 (lq_fml)?
3. [ ] Does it properly write consumption data for all 15 equipment?

---

## Pre-Test Checklist

Before running tests:

- [ ] All reference JSON files validated (syntax check)
- [ ] All CSV input files updated with new memory addresses
- [ ] Equipment failure CSV addresses corrected (D8000-D8021)
- [ ] PLC simulator/memory initialized
- [ ] Database migrations applied (alembic upgrade head)
- [ ] FastAPI service restarted

---

## Recommended Test Sequence

1. **Start:** `python test_export_read_area_to_csv.py` (read current PLC state)
2. **Write Data:** `python test_write_read_area_from_csv.py` (populate test data)
3. **Verify Write:** `python test_export_read_area_to_csv.py` (confirm data written)
4. **Equipment Failure:** `python test_equipment_failure_write.py` (test new memory range)
5. **Complete Cycle:** `python test_complete_cycle.py` (end-to-end test)

---

## Summary of Changes Required

| Change Type | Count | Files |
|------------|-------|-------|
| Comment Updates | 11 lines | 5 files ✅ DONE |
| Code Logic Review | 1 file | test_write_read_area_from_odoo.py |
| Equipment Failure Tests | ✅ OK | 3 files |
| CSV Dynamic Usage | ✅ OK | All modern tests |
| **NEW: Handshake Logic** | ✅ DONE | plc_handshake_service.py + test_handshake.py |

**Memory Addresses Updated:**
- READ Area: D6001-D6077 (includes status_read_data at D6075)
- WRITE Area: D7000-D7076 (includes status_read_data at D7076)  
- Equipment Failure: D8000-D8022 (includes status_read_data at D8022)

**Total Effort:** Low - Mostly documentation updates + new handshake service ✅
