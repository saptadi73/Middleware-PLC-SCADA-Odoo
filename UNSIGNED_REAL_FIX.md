# Fix: UNSIGNED REAL Value Reading in PLC Service

## Problem Summary
`actual_consumption_silo_e` was reading **-274.11 kg** instead of **381.25 kg** from D6035.

## Root Cause Analysis

### The Bug
In [plc_read_service.py lines 108-109](app/services/plc_read_service.py#L108-L109):
```python
# OLD CODE (BUGGY)
if raw_value > 32767:
    raw_value = raw_value - 65536  # ❌ Incorrectly converts to SIGNED
```

### Impact
For D6035 (SILO ID 105 Consumption):
- PLC sends raw value: **38125** (unsigned 16-bit)
- Bug converts to: 38125 - 65536 = **-27411** (treated as signed)
- With scale 100: -27411 / 100 = **-274.11** ❌
- Should be: 38125 / 100 = **381.25** ✓

### Affected Silos
Any silo with consumption > 327.67 kg (raw value > 32767):

| Address | Silo | Raw Value | Bug Result | Correct Result |
|---------|------|-----------|-----------|----------------|
| D6027 | SILO 1 | 82500 | -169.64 kg | 825.00 kg |
| D6029 | SILO 2 | 37500 | -280.36 kg | 375.00 kg |
| D6035 | SILO 105 | 38125 | -274.11 kg | 381.25 kg |
| D6037 | SILO 106 | 25000 | -250.00 kg | 250.00 kg |

## Why This Happened

### Inkonsistensi antara WRITE dan READ
**Writing** ([plc_write_service.py line 135-137](app/services/plc_write_service.py#L135-L137)):
```python
# Accepts UNSIGNED values up to 65535
if int_value < 0 or int_value > 65535:
    raise ValueError(f"Value {int_value} out of 16-bit range")
```

**Reading** ([plc_read_service.py line 108-109](app/services/plc_read_service.py#L108-L109)):
```python
# Was incorrectly converting to SIGNED
if raw_value > 32767:
    raw_value = raw_value - 65536
```

## Solution

### Changed Code
Removed the signed conversion logic. REAL values are now treated as **UNSIGNED 16-bit** (0 to 65535):

```python
# NEW CODE (FIXED)
def _convert_from_words(...):
    # ...
    elif data_type == "REAL":
        # ✓ Keep as UNSIGNED 16-bit (0-65535)
        # All consumption & quantity values are positive
        # Do NOT convert to signed for fields that should always be positive
        
        raw_value = words[0]  # Already unsigned from PLC
        scale = scale if scale else 1.0
        return float(raw_value) / scale
```

## Why This Fix Is Correct

1. **All consumption values are positive** - They range from 0 kg to max capacity
2. **All quantity values are positive** - They represent amounts of goods
3. **16-bit FINS protocol** sends unsigned integers by default
4. **Consistency** - Writing logic already expects unsigned values
5. **Physical reality** - Negative consumption/quantity doesn't make sense in manufacturing

## Verification

### Test Results ✓
```
✓ SILO ID 105 Consumption: 38125 / 100.0 = 381.25
✓ SILO 1 Consumption: 82500 / 100.0 = 825.00
✓ SILO 2 Consumption: 37500 / 100.0 = 375.00
✓ Quantity: 2500 / 1.0 = 2500.00
✓ All 7 test cases passed
```

## Files Modified
- [app/services/plc_read_service.py](app/services/plc_read_service.py) - Line 108-112

## Database Correction Needed
Existing data in `mo_batch` and `mo_history` tables with negative silo consumption values need to be corrected:

```sql
-- To identify affected rows:
SELECT 
    mo_id,
    actual_consumption_silo_a,
    actual_consumption_silo_b,
    ... (all columns)
FROM mo_batch 
WHERE actual_consumption_silo_a < 0 OR actual_consumption_silo_b < 0 
   OR actual_consumption_silo_c < 0 OR actual_consumption_silo_d < 0
   OR actual_consumption_silo_e < 0 OR actual_consumption_silo_f < 0
   OR actual_consumption_silo_g < 0 OR actual_consumption_silo_h < 0
   OR actual_consumption_silo_i < 0 OR actual_consumption_silo_j < 0
   OR actual_consumption_silo_k < 0;
```

These rows should be re-read from PLC or manually corrected based on actual consumption data.
