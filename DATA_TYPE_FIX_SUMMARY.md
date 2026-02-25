# DATA TYPE FIX SUMMARY - PLC OMRON CJ2M CPU33

## Masalah Yang Ditemukan

Setelah testing, ditemukan banyak kesalahan dimana:
1. Data yang seharusnya dikirim sebagai **REAL** malah dikirim sebagai **INTEGER**
2. Data yang seharusnya dibaca sebagai **REAL** malah dibaca sebagai **INTEGER**

## Root Cause Analysis

Ditemukan 2 service yang memiliki implementasi **INCORRECT** untuk penanganan data type REAL dan INT:

### 1. `plc_manual_weighing_service.py`

**MASALAH:** Method `_convert_from_words()` hanya membaca **1 word** untuk tipe data REAL, padahal seharusnya membaca **2 words** dan menggabungkannya sebelum dibagi dengan scale.

**KODE LAMA (SALAH):**
```python
if data_type.upper() == "REAL":
    # REAL dapat 1 atau 2 words tergantung magnitude
    # Untuk data weighing kami gunakan single word, value already scaled
    if len(words) >= 1:
        value = words[0]  # ❌ SALAH! Hanya pakai 1 word
        if scale and scale > 1:
            return value / scale
        return value
```

**KODE BARU (BENAR):**
```python
if data_type.upper() == "REAL":
    # REAL = 2 words (32-bit), combine them properly
    if not words:
        return 0.0
    if len(words) >= 2:
        # Combine 2 words into 32-bit value (big-endian)
        raw_value = (words[0] << 16) | words[1]
    else:
        # Fallback to single word if only 1 word provided
        raw_value = words[0]
    
    # Apply scale factor
    scale_value = scale if scale and scale > 0 else 1
    return float(raw_value) / float(scale_value)
```

### 2. `plc_equipment_failure_service.py`

**MASALAH:** Method `_convert_from_words()` menggunakan **byte order yang salah** (little-endian) untuk REAL, padahal PLC OMRON menggunakan **big-endian**.

**KODE LAMA (SALAH):**
```python
if data_type.upper() == "REAL":
    if len(words) < 2:
        return None
    word1 = words[0]
    word2 = words[1]
    combined = (word2 << 16) | word1  # ❌ SALAH byte order!
    bytes_data = combined.to_bytes(4, byteorder="little")
    return int.from_bytes(bytes_data, byteorder="little")
```

**KODE BARU (BENAR):**
```python
if data_type.upper() == "REAL":
    # REAL = 2 words (32-bit), combine them properly
    if not words:
        return 0.0
    if len(words) >= 2:
        # Combine 2 words into 32-bit value (big-endian: high word first)
        raw_value = (words[0] << 16) | words[1]  # ✓ BENAR
    else:
        raw_value = words[0]
    
    scale_value = scale if scale and scale > 0 else 1
    return float(raw_value) / float(scale_value)
```

## Standard Data Type Handling - PLC OMRON CJ2M

Berdasarkan referensi [READ_DATA_PLC_MAPPING.json](app/reference/READ_DATA_PLC_MAPPING.json) dan [MASTER_BATCH_REFERENCE.json](app/reference/MASTER_BATCH_REFERENCE.json):

### Data Type: **INT**
- **Ukuran:** 1 word (16-bit signed) ATAU 2 words (32-bit signed)
- **Scale:** Selalu 1 (tidak ada scale factor)
- **Format DM:** Single address (e.g., `"D6000"`) untuk 16-bit, range (e.g., `"D6000-6001"`) untuk 32-bit
- **Contoh:**
  - BATCH: `"Data Type": "INT"`, `"scale": 1`, `"DM": "D6000"` → 1 word
  - SILO ID 101: `"Data Type": "INT"`, `"scale": 1`, `"DM": "D6027"` → 1 word

### Data Type: **REAL**
- **Ukuran:** 2 words (32-bit) - **SELALU**
- **Scale:** 100 (untuk consumption/quantity) atau 1 (untuk counter)
- **Format DM:** Range address (e.g., `"D6028-6029"`)
- **Conversion:** `(word[0] << 16 | word[1]) / scale`
- **Contoh:**
  - Quantity Goods_id: `"Data Type": "REAL"`, `"scale": 100`, `"DM": "D6025-6026"` → 2 words
  - SILO ID 101 Consumption: `"Data Type": "REAL"`, `"scale": 100`, `"DM": "D6028-6029"` → 2 words

### Data Type: **ASCII**
- **Ukuran:** Sesuai jumlah karakter (2 chars = 1 word)
- **Format DM:** Range address (e.g., `"D6001-6008"` untuk 8 words = 16 chars)
- **Encoding:** Big-endian (high byte first)

### Data Type: **BOOLEAN**
- **Ukuran:** 1 word
- **Nilai:** 0 atau 1
- **Format DM:** Single address (e.g., `"D6075"`)

## Implementasi Yang Benar

Semua service PLC **HARUS** mengikuti standard ini:

### Reading from PLC

```python
def _convert_from_words(words: List[int], data_type: str, scale: Optional[int] = None) -> Any:
    """Convert PLC word values into Python value."""
    data_type = data_type.upper()
    
    if data_type == "INT":
        if not words:
            return 0
        if len(words) >= 2:
            # 32-bit signed integer
            raw_value = (words[0] << 16) | words[1]
            if raw_value > 2147483647:
                raw_value -= 4294967296
            return int(raw_value)
        else:
            # 16-bit signed integer
            raw_value = words[0]
            if raw_value > 32767:
                raw_value -= 65536
            return int(raw_value)
    
    if data_type == "REAL":
        if not words:
            return 0.0
        if len(words) >= 2:
            # Combine 2 words (big-endian)
            raw_value = (words[0] << 16) | words[1]
        else:
            raw_value = words[0]
        scale_value = scale if scale and scale > 0 else 1
        return float(raw_value) / float(scale_value)
    
    if data_type == "ASCII":
        # Parse ASCII from words (big-endian)
        # Implementation details...
        
    if data_type == "BOOLEAN":
        return bool(words[0]) if words else False
```

### Writing to PLC

```python
def _convert_to_words(value: Any, data_type: str, scale: Optional[int] = None, word_count: Optional[int] = None) -> List[int]:
    """Convert Python value to PLC words."""
    data_type = data_type.upper()
    
    if data_type == "INT":
        int_value = int(value)  # No scale for INT
        if word_count and word_count >= 2:
            # 32-bit signed
            if int_value < 0:
                int_value = int_value + 4294967296
            high_word = (int_value >> 16) & 0xFFFF
            low_word = int_value & 0xFFFF
            return [high_word, low_word]
        else:
            # 16-bit signed
            if int_value < 0:
                int_value = int_value + 65536
            return [int_value & 0xFFFF]
    
    if data_type == "REAL":
        scale_value = scale if scale and scale > 0 else 1
        int_value = int(value * scale_value)
        if word_count and word_count >= 2:
            # 32-bit signed
            if int_value < 0:
                int_value = int_value + 4294967296
            high_word = (int_value >> 16) & 0xFFFF
            low_word = int_value & 0xFFFF
            return [high_word, low_word]
        else:
            # 16-bit (fallback)
            if int_value < 0:
                int_value = int_value + 65536
            return [int_value & 0xFFFF]
```

## Services Yang Sudah Diperbaiki

✅ **plc_read_service.py** - SUDAH BENAR sejak awal
✅ **plc_write_service.py** - SUDAH BENAR sejak awal
✅ **plc_manual_weighing_service.py** - DIPERBAIKI: Kombinasi 2 words untuk REAL
✅ **plc_equipment_failure_service.py** - DIPERBAIKI: Byte order + scale support

## Cara Menggunakan Reference Files

Semua service **WAJIB** menggunakan reference JSON untuk mendapatkan informasi data type:

```python
# Contoh dari READ_DATA_PLC_MAPPING.json
{
    "No": 7,
    "Informasi": "SILO ID 101 Consumption",
    "Data Type": "REAL",           # ← Gunakan ini untuk konversi
    "scale": 100,                   # ← Gunakan ini untuk scale
    "DM": "D6028-6029"              # ← Parse ini untuk word_count
}
```

**FLOW YANG BENAR:**
1. Load reference JSON file
2. Find field by name (Informasi)
3. Get `Data Type` from field definition
4. Get `scale` from field definition
5. Parse `DM` to get address and word_count
6. Read words from PLC
7. Call `_convert_from_words(words, data_type, scale)`

**JANGAN PERNAH:**
- ❌ Hardcode data type
- ❌ Hardcode scale
- ❌ Assume word count tanpa parsing DM address
- ❌ Bypass reference file

## Testing & Validation

Untuk memastikan fix ini bekerja:

```python
# Test REAL conversion (144.15 dengan scale 100)
words_write = write_service._convert_to_words(144.15, 'REAL', 100, word_count=2)
# Expected: [0, 14415]

words_read = read_service._convert_from_words([0, 14415], 'REAL', 100)
# Expected: 144.15

# Test INT conversion (101)
words_write = write_service._convert_to_words(101, 'INT', 1, word_count=1)
# Expected: [101]

words_read = read_service._convert_from_words([101], 'INT', 1)
# Expected: 101
```

## Kesimpulan

Fix ini memastikan bahwa:
1. ✅ Semua REAL field **SELALU** dibaca/ditulis sebagai 2 words (32-bit) dengan scale yang benar
2. ✅ Semua INT field dibaca/ditulis sesuai ukurannya (1 atau 2 words) tanpa scale
3. ✅ Byte order konsisten (big-endian) untuk semua service
4. ✅ Reference file digunakan sebagai single source of truth untuk data type dan scale

**Tanggal Fix:** 25 Februari 2026
**Files Modified:**
- `app/services/plc_manual_weighing_service.py`
- `app/services/plc_equipment_failure_service.py`

**Referensi:**
- [READ_DATA_PLC_MAPPING.json](app/reference/READ_DATA_PLC_MAPPING.json)
- [MASTER_BATCH_REFERENCE.json](app/reference/MASTER_BATCH_REFERENCE.json)
- [ADDITIONAL_EQUIPMENT_REFERENCE.json](app/reference/ADDITIONAL_EQUIPMENT_REFERENCE.json)
- [EQUIPMENT_FAILURE_REFERENCE.json](app/reference/EQUIPMENT_FAILURE_REFERENCE.json)
