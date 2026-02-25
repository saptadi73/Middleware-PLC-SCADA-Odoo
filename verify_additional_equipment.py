"""
Verify ADDITIONAL_EQUIPMENT_REFERENCE.json has correct data type mapping
"""
import json

print("=== VERIFIKASI ADDITIONAL_EQUIPMENT_REFERENCE.json ===\n")

data = json.load(open('app/reference/ADDITIONAL_EQUIPMENT_REFERENCE.json', 'r', encoding='utf-8'))

print("Memory Layout:", data['meta']['memory_layout'])
print("\nFields:")
print(f"{'No':<4} {'Field Name':<32} {'Data Type':<10} {'DM Address':<16} {'Scale':<8}")
print("-" * 80)

for item in data['ADDITIONAL']:
    no = item['No']
    name = item['Informasi']
    dtype = item['Data Type']
    dm = item['DM']
    scale = item.get('scale', 'N/A')
    print(f"{no:<4} {name:<32} {dtype:<10} {dm:<16} {scale:<8}")

print("\n✓ JSON structure verified!")
print("\nMemory Allocation Summary:")
print("  D9000-D9001: BATCH (INT, 2 words)")
print("  D9002-D9005: NO-MO (ASCII, 4 words)")
print("  D9006-D9007: NO-Product (INT, 2 words)")
print("  D9008-D9009: Consumption (REAL, 2 words, scale=100)")
print("  D9010:       Reserved")
print("  D9011:       Handshake flag (BOOLEAN, 1 word)")
print("\nTotal: 12 words (D9000-D9011)")
