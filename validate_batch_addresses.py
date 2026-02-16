"""
Validate MASTER_BATCH_REFERENCE.json address continuity and weight_finished_good word count.
"""
import json
import re

def parse_dm_address(dm_str):
    """Parse DM address string and return start address and word count."""
    match = re.match(r"D(\d+)(?:-(\d+))?", dm_str)
    if not match:
        return None, None
    
    start = int(match.group(1))
    if match.group(2):
        end = int(match.group(2))
        count = end - start + 1
    else:
        count = 1
    
    return start, count

def validate_batch_reference():
    """Validate batch address mapping."""
    with open('app/reference/MASTER_BATCH_REFERENCE.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=" * 80)
    print("BATCH ADDRESS VALIDATION REPORT")
    print("=" * 80)
    
    batch_keys = sorted([k for k in data.keys() if k.startswith('BATCH')])
    
    issues = []
    prev_batch_end = None
    prev_batch_name = None
    
    for batch_name in batch_keys:
        batch_data = data[batch_name]
        
        # Find start and end addresses
        first_field = batch_data[0]
        last_field = batch_data[-1]
        
        start_addr, _ = parse_dm_address(first_field['DM'])
        end_addr, end_count = parse_dm_address(last_field['DM'])
        
        if end_count > 1:
            actual_end = end_addr + end_count - 1
        else:
            actual_end = end_addr
        
        # Check continuity
        if prev_batch_end is not None:
            expected_start = prev_batch_end + 1
            if start_addr != expected_start:
                gap = start_addr - expected_start
                issues.append(
                    f"⚠️  {prev_batch_name} → {batch_name}: "
                    f"Gap of {gap} words (D{prev_batch_end} → D{start_addr})"
                )
        
        # Check weight_finished_good specifically
        weight_field = None
        for field in batch_data:
            if field['Informasi'] == 'weight_finished_good':
                weight_field = field
                break
        
        if weight_field:
            _, word_count = parse_dm_address(weight_field['DM'])
            if word_count != 2:
                issues.append(
                    f"❌ {batch_name}: weight_finished_good has {word_count} words "
                    f"(expected 2) - Address: {weight_field['DM']}"
                )
            else:
                print(f"✓ {batch_name}: D{start_addr}-D{actual_end} "
                      f"({actual_end - start_addr + 1} words) | "
                      f"weight_finished_good: {weight_field['DM']} ✓")
        else:
            print(f"✓ {batch_name}: D{start_addr}-D{actual_end} "
                  f"({actual_end - start_addr + 1} words)")
        
        prev_batch_end = actual_end
        prev_batch_name = batch_name
    
    print("\n" + "=" * 80)
    if issues:
        print("ISSUES FOUND:")
        print("=" * 80)
        for issue in issues:
            print(issue)
        return False
    else:
        print("✅ ALL VALIDATIONS PASSED")
        print("=" * 80)
        print(f"Total batches: {len(batch_keys)}")
        print(f"All weight_finished_good fields: 2 words ✓")
        print(f"No address gaps or overlaps ✓")
        return True

if __name__ == "__main__":
    success = validate_batch_reference()
    exit(0 if success else 1)
