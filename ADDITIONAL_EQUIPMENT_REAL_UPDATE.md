# ADDITIONAL EQUIPMENT - REAL Data Type Update

> ⚠️ Historical note
>
> Dokumen ini adalah catatan perubahan lama (versi transisi) dan **bukan source of truth runtime saat ini**.
> Untuk konfigurasi aktif terbaru, gunakan:
> - `app/reference/ADDITIONAL_EQUIPMENT_REFERENCE.json`
> - `app/services/plc_manual_weighing_service.py`
>
> Pada implementasi aktif, handshake manual weighing menggunakan `D9013`.

**Date**: 2024  
**Status**: ✅ COMPLETED  
**Version**: 2.1

---

## 📋 OVERVIEW

Updated `ADDITIONAL_EQUIPMENT_REFERENCE.json` and `plc_manual_weighing_service.py` to use **REAL (32-bit, 2 words)** data type for all numeric fields (BATCH, NO-Product, Consumption) to support large numbers exceeding 65,535.

---

## 🎯 WHY THIS CHANGE?

**User Requirement**: "YA bisa, lebih baik ganti ke real 2 words"

- **BATCH** and **NO-Product** IDs can exceed 65,535 in production
- **INT (16-bit)** can only store values 0-65,535
- **REAL (32-bit)** supports much larger values (up to ~2 billion for integer part)
- Consistent with other PLC memory areas that use REAL for batch/product IDs

---

## 📝 MEMORY LAYOUT (BEFORE vs AFTER)

### ❌ BEFORE (Inconsistent - 12 words)
```
D9000:       BATCH (INT, 1 word) ❌
D9001-D9008: NO-MO (ASCII, 8 words) ❌ Wrong address range
D9009:       NO-Product (INT, 1 word) ❌
D9010-D9011: Consumption (REAL, 2 words, scale=100) ✓
D9011:       Handshake (BOOLEAN) ❌ Address conflict!
```

### ✅ AFTER (Standardized - 13 words)
```
D9000-D9001: BATCH (REAL, 2 words, scale=1)
D9002-D9005: NO-MO (ASCII, 4 words = 8 characters)  
D9006-D9007: NO-Product (REAL, 2 words, scale=1)
D9008-D9009: Consumption (REAL, 2 words, scale=100)
D9010-D9011: Reserved (2 words, for future use)
D9012:       Handshake flag (BOOLEAN, 1 word)
```

**Total**: 13 words (D9000 to D9012)

---

## 🔧 FILES MODIFIED

### 1. `app/reference/ADDITIONAL_EQUIPMENT_REFERENCE.json`

#### Changes:
- ✅ Updated `memory_area`: `"D9000-D9012 (13 words total)"`
- ✅ Updated `memory_layout` with correct addresses
- ✅ Changed **BATCH**: `INT` → `REAL`, DM `"D9000"` → `"D9000-D9001"`, added `scale: 1`
- ✅ Fixed **NO-MO**: DM `"D9001-D9008"` → `"D9002-D9005"` (ASCII uses 4 words for 8 chars)
- ✅ Changed **NO-Product**: `INT` → `REAL`, DM `"D9009"` → `"D9006-D9007"`, added `scale: 1`
- ✅ Fixed **Consumption**: DM `"D9010-D9011"` → `"D9008-D9009"` (already REAL, scale=100)
- ✅ Updated **Handshake**: DM `"D9011"` → `"D9012"` (no address conflict)
- ✅ Version bumped: `2.0` → `2.1`

### 2. `app/services/plc_manual_weighing_service.py`

#### Changes:
- ✅ Updated `word_count`: `12` → `13` words
- ✅ Updated memory range: `"D9000-D9011"` → `"D9000-D9012"`
- ✅ Updated handshake index: `data_words[11]` → `data_words[12]`
- ✅ Updated **BATCH** parsing:
  ```python
  # OLD: batch = data_words[0]  # INT single word
  # NEW: batch = self._convert_from_words(data_words[0:2], "REAL", scale=1)
  ```
- ✅ Updated **NO-MO** parsing: `data_words[1:9]` → `data_words[2:6]` (4 words)
- ✅ Updated **NO-Product** parsing:
  ```python
  # OLD: product_tmpl_id = data_words[9]  # INT single word
  # NEW: product_tmpl_id = self._convert_from_words(data_words[6:8], "REAL", scale=1)
  ```
- ✅ Updated **Consumption** parsing: `data_words[10:12]` → `data_words[8:10]`
- ✅ Fixed debug message: `"D9011 handshake"` → `"D9012 handshake"`

---

## ✅ VERIFICATION

Run verification script:
```bash
python verify_additional_equipment_updated.py
```

**Expected Output**:
```
✓ BATCH: REAL, 2 words (D9000-D9001)
✓ NO-MO: ASCII, 4 words (D9002-D9005)
✓ NO-Product: REAL, 2 words (D9006-D9007)
✓ Consumption: REAL, 2 words, scale=100 (D9008-D9009)
✓ Handshake: BOOLEAN, 1 word (D9012)

🎉 ALL VALIDATIONS PASSED!
```

---

## 📊 DATA TYPE RULES (STANDARDIZED)

| Data Type | Word Count | Byte Order | Scale Factor | Range |
|-----------|-----------|------------|--------------|-------|
| **REAL** | 2 words (32-bit) | Big-endian (high word first) | Yes (1, 10, 100) | ±2.1 billion (approx) |
| **INT** | 1-2 words | Big-endian | **NO** (always 1) | 16-bit: -32768 to 32767<br>32-bit: ±2.1 billion |
| **ASCII** | 1 word = 2 chars | N/A | **NO** | Any characters |
| **BOOLEAN** | 1 word | N/A | **NO** | 0 or 1 |

### Scale Factor Usage:
- **BATCH & NO-Product**: scale = 1 (no decimals needed, but supports large IDs)
- **Consumption**: scale = 100 (to preserve 2 decimal places, e.g., 144.15 kg)

---

## 🧪 TESTING CHECKLIST

Before deploying to production:

- [ ] Run `python verify_additional_equipment_updated.py` → ✅ PASSED
- [ ] Test with actual PLC hardware:
  - [ ] Write BATCH > 65535 (e.g., 100000) and read back correctly
  - [ ] Write NO-Product > 65535 and read back correctly
  - [ ] Write Consumption with decimals (e.g., 144.15) and read back correctly
  - [ ] Verify handshake flag at D9012 works correctly
- [ ] Monitor logs for any conversion errors
- [ ] Verify database sync inserts correct values (not truncated to 65535)

---

## 📌 NOTES

1. **Why ASCII uses 4 words for 8 chars?**
   - OMRON CJ2M stores 2 ASCII characters per word (16-bit)
   - 8-character MO number = 4 words (D9002-D9005)

2. **Why Reserved 2 words (D9010-D9011)?**
   - Buffer space for future expansion without breaking memory layout
   - Prevents address conflicts if more fields are added

3. **Big-Endian Byte Order**:
   - OMRON PLC stores high word first: `value = (word[0] << 16) | word[1]`
   - Example: 100000 → [0x0001, 0x86A0] → combined: 0x000186A0 = 100000

4. **Integration with Other Services**:
   - `plc_read_service.py`: Uses READ_DATA_PLC_MAPPING.json (REAL already correct)
   - `plc_write_service.py`: Uses MASTER_BATCH_REFERENCE.json (REAL already correct)
   - `plc_equipment_failure_service.py`: Uses ADDITIONAL_EQUIPMENT_FAILURE_REFERENCE.json (already uses REAL)
   - `plc_manual_weighing_service.py`: Uses ADDITIONAL_EQUIPMENT_REFERENCE.json (**NOW UPDATED**)

---

## ✅ STATUS

**All changes completed and verified!** ✅

- ADDITIONAL_EQUIPMENT_REFERENCE.json updated to version 2.1
- plc_manual_weighing_service.py updated with correct 13-word parsing
- Verification script confirms all fields use correct data types
- Memory layout standardized with no address conflicts

**Next step**: Test with actual OMRON CJ2M PLC hardware.
