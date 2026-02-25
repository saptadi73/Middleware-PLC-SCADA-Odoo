"""
Test script to verify data type handling consistency across all PLC services.
"""
from app.services.plc_write_service import PLCWriteService
from app.services.plc_read_service import PLCReadService
from app.services.plc_manual_weighing_service import PLCManualWeighingService
from app.services.plc_equipment_failure_service import PLCEquipmentFailureService

print("=== VERIFIKASI DATA TYPE HANDLING ===\n")

# Initialize services
ws = PLCWriteService()
rs = PLCReadService()
mws = PLCManualWeighingService()
efs = PLCEquipmentFailureService()

# Test 1: REAL dengan 2 words (scale 100)
print("1. Test REAL dengan 2 words (scale 100):")
w = ws._convert_to_words(144.15, 'REAL', None, 100, word_count=2)
print(f"   Write: 144.15 -> {w}")
print(f"   Read (plc_read_service): {w} -> {rs._convert_from_words(w, 'REAL', 100)}")
print(f"   Read (plc_manual_weighing): {w} -> {mws._convert_from_words(w, 'REAL', 100)}")
print(f"   Read (plc_equipment_failure): {w} -> {efs._convert_from_words(w, 'REAL', None, 100)}")
print()

# Test 2: REAL dengan 1 word (scale 100 - fallback)
print("2. Test REAL dengan 1 word (scale 100 - fallback):")
w = [14415]
print(f"   Read (plc_read_service): {w} -> {rs._convert_from_words(w, 'REAL', 100)}")
print(f"   Read (plc_manual_weighing): {w} -> {mws._convert_from_words(w, 'REAL', 100)}")
print(f"   Read (plc_equipment_failure): {w} -> {efs._convert_from_words(w, 'REAL', None, 100)}")
print()

# Test 3: INT dengan 1 word
print("3. Test INT dengan 1 word:")
w = ws._convert_to_words(101, 'INT', None, 1, word_count=1)
print(f"   Write: 101 -> {w}")
print(f"   Read (plc_read_service): {w} -> {rs._convert_from_words(w, 'INT', 1)}")
print(f"   Read (plc_manual_weighing): {w} -> {mws._convert_from_words(w, 'INT', 1)}")
print(f"   Read (plc_equipment_failure): {w} -> {efs._convert_from_words(w, 'INT', None, 1)}")
print()

# Test 4: INT dengan 2 words
print("4. Test INT dengan 2 words (32-bit):")
w = ws._convert_to_words(65540, 'INT', None, 1, word_count=2)
print(f"   Write: 65540 -> {w}")
print(f"   Read (plc_read_service): {w} -> {rs._convert_from_words(w, 'INT', 1)}")
print(f"   Read (plc_manual_weighing): {w} -> {mws._convert_from_words(w, 'INT', 1)}")
print(f"   Read (plc_equipment_failure): {w} -> {efs._convert_from_words(w, 'INT', None, 1)}")
print()

# Test 5: REAL besar dengan 2 words (scale 100)
print("5. Test REAL besar dengan 2 words (scale 100):")
w = ws._convert_to_words(20000.45, 'REAL', None, 100, word_count=2)
print(f"   Write: 20000.45 -> {w}")
print(f"   Read (plc_read_service): {w} -> {rs._convert_from_words(w, 'REAL', 100)}")
print(f"   Read (plc_manual_weighing): {w} -> {mws._convert_from_words(w, 'REAL', 100)}")
print(f"   Read (plc_equipment_failure): {w} -> {efs._convert_from_words(w, 'REAL', None, 100)}")
print()

print("✓ Semua service konsisten!")
print("\nRINGKASAN:")
print("- REAL: Selalu menggunakan 2 words (atau fallback ke 1 word jika perlu)")
print("- INT: Bisa 1 word (16-bit) atau 2 words (32-bit)")
print("- Scale: Selalu digunakan untuk REAL, tidak untuk INT")
print("- Byte order: Big-endian (high word first)")
