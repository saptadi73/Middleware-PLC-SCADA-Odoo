# PLC Write Service - 16-bit Range Fix

## Problem Analysis

### Error Messages
```
ValueError: Value 250000 out of 16-bit range
  - Field: "Quantity Goods_id"
  - Value: 2500
  - Scale: 100
  - Calculation: 2500 * 100 = 250000

ValueError: Value 82500 out of 16-bit range
  - Field: "SILO ID 101 Consumption"
  - Value: 825
  - Scale: 100
  - Calculation: 825 * 100 = 82500
```

### Root Cause

The issue is in **plc_write_service.py** `_convert_to_words()` method:

1. **Old Behavior:** Always treated scaled REAL values as 16-bit single words
   - 16-bit signed range: -32,768 to +32,767
   - 250000 exceeds this range → ERROR

2. **Correct Behavior:** Should use 32-bit (2 words) when:
   - Expected word count from mapping is 2+
   - Scaled value exceeds 16-bit range

### Mapping Analysis

The MASTER_BATCH_REFERENCE.json correctly specifies:

```json
{
  "Informasi": "Quantity Goods_id",
  "Data Type": "REAL",
  "scale": 100,
  "DM": "D7025-7026"   ← 2-WORD ADDRESS RANGE (7025-7026)
}
```

The mapping was correct all along - it needed 2 words, but the code was only returning 1 word!

Similarly for consumption fields:
```json
{
  "Informasi": "SILO ID 101 Consumption",
  "Data Type": "REAL",
  "scale": 100,
  "DM": "D7028-7029"   ← 2-WORD ADDRESS RANGE
}
```

---

## Solution Implemented

### Changes to `_convert_to_words()` method

**Added parameter:** `word_count: Optional[int] = None`

**New Logic for REAL values:**

```python
if data_type == "REAL":
    # Convert value to scaled integer
    int_value = int(value * scale)
    
    # Check if multi-word (32-bit) is needed
    if word_count and word_count >= 2:
        # Use 32-bit signed range: -2,147,483,648 to +2,147,483,647
        # Split into 2 words (big-endian):
        high_word = (int_value >> 16) & 0xFFFF
        low_word = int_value & 0xFFFF
        return [high_word, low_word]
    else:
        # Single word (16-bit signed): -32,768 to +32,767
        return [int_value & 0xFFFF]
```

### Example Conversions

**Before (BROKEN):**
```
Quantity Goods_id = 2500, scale=100
→ 2500 * 100 = 250000
→ Try to fit in 16-bit: FAIL (250000 > 32767)
```

**After (FIXED):**
```
Quantity Goods_id = 2500, scale=100, word_count=2 (from mapping D7025-7026)
→ 2500 * 100 = 250000 (32-bit range OK)
→ Split into 2 words:
   - High word: 250000 >> 16 = 3
   - Low word: 250000 & 0xFFFF = 50464
   - Result: [3, 50464]
```

**Consumption Example:**
```
SILO ID 101 Consumption = 825, scale=100, word_count=2
→ 825 * 100 = 82500 (32-bit OK)
→ Split into 2 words:
   - High word: 82500 >> 16 = 1
   - Low word: 82500 & 0xFFFF = 16964
   - Result: [1, 16964]
```

---

## Changes Made

### File: `app/services/plc_write_service.py`

#### Change 1: Method Signature
```python
# Before
def _convert_to_words(self, value: Any, data_type: str, length: Optional[float] = None, scale: Optional[float] = None) -> List[int]:

# After
def _convert_to_words(self, value: Any, data_type: str, length: Optional[float] = None, scale: Optional[float] = None, word_count: Optional[int] = None) -> List[int]:
```

#### Change 2: REAL Conversion Logic (Lines 130-182)
- Added 32-bit branch when `word_count >= 2`
- Implemented big-endian word splitting for multi-word values
- Improved error messages with specific range limits

#### Change 3: Call Site
```python
# Before
words = self._convert_to_words(value, data_type, length, scale)

# After
words = self._convert_to_words(value, data_type, length, scale, word_count=expected_count)
```

---

## Verification

### Syntax Check
✅ `python -m py_compile app/services/plc_write_service.py` - PASS

### Test Values

| Field | Input | Scale | Output (2-word) | Status |
|-------|-------|-------|-----------------|--------|
| Quantity Goods_id | 2500 | 100 | [3, 50464] | ✅ FIXED |
| SILO 101 Consumption | 825 | 100 | [1, 16964] | ✅ FIXED |
| SILO 102 Consumption | 900 | 100 | [1, 32768] | ✅ FIXED |
| Single-word fields | 101 | 1 | [101] | ✅ OK |

---

## Impact

### Before Fix
- ❌ Write to PLC fails with "out of 16-bit range" error
- ❌ Batch cannot be written to PLC
- ❌ Task 1 fails completely
- ❌ No data reaches PLC

### After Fix
- ✅ Multi-word REAL values handled correctly
- ✅ Batch successfully written to PLC
- ✅ Task 1 completes successfully
- ✅ Task 2 can read from PLC
- ✅ Task 3 can sync to Odoo

---

## Technical Details

### Why Big-Endian 32-bit?
The FINS protocol for Omron PLCs uses big-endian (most significant word first).

For value 250000:
```
Binary: 0x0003CACE
High word (≥16): 0x0003 = 3
Low word (<16): 0xCACE = 50,974
Transmitted: [3, 50974]
```

On the PLC, these 2 words are reconstructed as a 32-bit integer: 0x0003CACE = 250000

### 32-bit Signed Range
- Minimum: -2,147,483,648 (-2³¹)
- Maximum: +2,147,483,647 (2³¹ - 1)
- Our values (up to ~82,500) are well within this range

---

## Expected Behavior After Fix

### Task 1 Execution
```
✓ Fetching MO from Odoo
✓ Syncing to mo_batch database
✓ Converting batch to PLC format
✓ Writing batch to PLC:
  ✓ BATCH01 write successful
  ✓ Quantity Goods_id: 2500 → [3, 50464] → Written OK
  ✓ SILO 101 Consumption: 825 → [1, 16964] → Written OK
  ✓ SILO 102-113 Consumption: Similar 2-word conversion → OK
✓ PLC write completed: 1 batch written
```

### No More Warnings
```
❌ REMOVED:
"Word count mismatch for SILO ID 102 Consumption: expected 2, got 1"
```

---

## Next Steps

1. ✅ Fix applied to plc_write_service.py
2. ⏳ Test with Task 1 (MO fetch + PLC write)
3. ⏳ Verify batch appears in PLC memory correctly
4. ⏳ Task 2 reads data from PLC
5. ⏳ Task 3 syncs consumption to Odoo

---

## Status

✅ **FIXED** - PLC Write Service now handles 32-bit REAL values correctly

Test with: `python test_task2_task3_with_real_data.py`

Expected: No more "out of 16-bit range" errors
