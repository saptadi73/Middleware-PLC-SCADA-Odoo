"""
Verify ADDITIONAL_EQUIPMENT_REFERENCE.json after REAL 2-words update
"""
import json

print("=" * 80)
print("VERIFIKASI ADDITIONAL_EQUIPMENT_REFERENCE.json - UPDATED LAYOUT")
print("=" * 80)

data = json.load(open('app/reference/ADDITIONAL_EQUIPMENT_REFERENCE.json', 'r', encoding='utf-8'))

print("\n📋 META INFORMATION:")
print(f"  Memory Area: {data['meta']['memory_area']}")
print(f"  Layout: {data['meta']['memory_layout']}")
print(f"  Version: {data['meta']['version']}")

print("\n📊 FIELD MAPPING:")
print(f"{'No':<4} {'Field Name':<32} {'Data Type':<10} {'DM Address':<16} {'Scale':<8}")
print("-" * 80)

total_words = 0
for item in data['ADDITIONAL']:
    no = item['No']
    name = item['Informasi']
    dtype = item['Data Type']
    dm = item['DM']
    scale = item.get('scale', 'N/A')
    
    # Calculate word count from DM address
    if '-' in dm:
        parts = dm.replace('D', '').split('-')
        start = int(parts[0])
        end = int(parts[1])
        words = end - start + 1
    else:
        words = 1
    
    total_words += words if no < 5 else 0  # Don't count handshake in total calculation
    
    print(f"{no:<4} {name:<32} {dtype:<10} {dm:<16} {scale:<8} ({words} word{'s' if words > 1 else ''})")

print("-" * 80)
print(f"Total words (data fields): {total_words} words")
print(f"Total with handshake: {total_words + 1} words")

print("\n✅ VALIDATION:")
errors = []

# Check BATCH
batch = data['ADDITIONAL'][0]
if batch['Data Type'] != 'REAL':
    errors.append(f"❌ BATCH should be REAL, got {batch['Data Type']}")
if batch['DM'] != 'D9000-D9001':
    errors.append(f"❌ BATCH DM should be D9000-D9001, got {batch['DM']}")
else:
    print("✓ BATCH: REAL, 2 words (D9000-D9001)")

# Check NO-MO
nomo = data['ADDITIONAL'][1]
if nomo['Data Type'] != 'ASCII':
    errors.append(f"❌ NO-MO should be ASCII, got {nomo['Data Type']}")
if nomo['DM'] != 'D9002-D9005':
    errors.append(f"❌ NO-MO DM should be D9002-D9005, got {nomo['DM']}")
else:
    print("✓ NO-MO: ASCII, 4 words (D9002-D9005)")

# Check NO-Product
noprod = data['ADDITIONAL'][2]
if noprod['Data Type'] != 'REAL':
    errors.append(f"❌ NO-Product should be REAL, got {noprod['Data Type']}")
if noprod['DM'] != 'D9006-D9007':
    errors.append(f"❌ NO-Product DM should be D9006-D9007, got {noprod['DM']}")
else:
    print("✓ NO-Product: REAL, 2 words (D9006-D9007)")

# Check Consumption
cons = data['ADDITIONAL'][3]
if cons['Data Type'] != 'REAL':
    errors.append(f"❌ Consumption should be REAL, got {cons['Data Type']}")
if cons['DM'] != 'D9008-D9009':
    errors.append(f"❌ Consumption DM should be D9008-D9009, got {cons['DM']}")
if cons.get('scale') != 100:
    errors.append(f"❌ Consumption scale should be 100, got {cons.get('scale')}")
else:
    print("✓ Consumption: REAL, 2 words, scale=100 (D9008-D9009)")

# Check Handshake
hs = data['ADDITIONAL'][4]
if hs['Data Type'] != 'BOOLEAN':
    errors.append(f"❌ Handshake should be BOOLEAN, got {hs['Data Type']}")
if hs['DM'] != 'D9012':
    errors.append(f"❌ Handshake DM should be D9012, got {hs['DM']}")
else:
    print("✓ Handshake: BOOLEAN, 1 word (D9012)")

if errors:
    print("\n❌ ERRORS FOUND:")
    for err in errors:
        print(f"  {err}")
else:
    print("\n🎉 ALL VALIDATIONS PASSED!")

print("\n📝 MEMORY LAYOUT SUMMARY:")
print("  D9000-D9001: BATCH (REAL, 2 words, scale=1)")
print("  D9002-D9005: NO-MO (ASCII, 4 words)")
print("  D9006-D9007: NO-Product (REAL, 2 words, scale=1)")
print("  D9008-D9009: Consumption (REAL, 2 words, scale=100)")
print("  D9010-D9011: Reserved (2 words)")
print("  D9012:       Handshake flag (BOOLEAN, 1 word)")
print("\n  Total: 13 words (D9000-D9012)")

print("\n📌 DATA TYPE NOTES:")
print("  • All numeric fields use REAL (32-bit, 2 words)")
print("  • REAL supports values >65535 for large batch/product IDs")
print("  • BATCH & NO-Product: scale=1 (no decimals needed)")
print("  • Consumption: scale=100 (for decimal precision)")
print("=" * 80)
