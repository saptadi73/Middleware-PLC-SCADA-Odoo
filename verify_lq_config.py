#!/usr/bin/env python
import json

# Verify LQ114 and LQ115 configuration
data = json.load(open('app/reference/silo_data.json'))

print("✓ Verification - Liquid Tanks Configuration:")
for item in data['raw_list']:
    if item['id'] in (114, 115):
        print(f"  ID {item['id']}: equipment_code={item['equipment_code']}, scada_tag={item['scada_tag']}")

# Check model fields
print("\n✓ Expected Table Fields:")
print("  mo_batch & mo_histories tables should have:")
print("    - consumption_lq_tetes, actual_consumption_lq_tetes")
print("    - consumption_lq_fml, actual_consumption_lq_fml")
