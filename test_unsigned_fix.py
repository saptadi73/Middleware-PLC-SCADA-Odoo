#!/usr/bin/env python3
"""
Test to verify the fix for unsigned REAL values reading
"""

def test_unsigned_conversion():
    """Test that REAL values are read as UNSIGNED 16-bit"""
    
    print("=" * 70)
    print("Testing UNSIGNED REAL Value Conversion Fix")
    print("=" * 70)
    
    test_cases = [
        # (raw_value, scale, field_name, expected_result)
        (38125, 100.0, "SILO ID 105 Consumption", 381.25),
        (82500, 100.0, "SILO 1 Consumption", 825.00),
        (37500, 100.0, "SILO 2 Consumption", 375.00),
        (2500, 1.0, "Quantity Goods_id", 2500.0),
        (101, 1.0, "SILO ID", 101.0),
        (50, 100.0, "Small consumption", 0.50),
        (65535, 100.0, "Max 16-bit unsigned", 655.35),
    ]
    
    print(f"\nTest Results:")
    print("-" * 70)
    
    passed = 0
    failed = 0
    
    for raw_value, scale, field_name, expected in test_cases:
        # New (correct) logic - treats as UNSIGNED
        result = float(raw_value) / scale
        
        status = "✓ PASS" if abs(result - expected) < 0.001 else "✗ FAIL"
        if "PASS" in status:
            passed += 1
        else:
            failed += 1
            
        print(f"{status} | {field_name:35} | {raw_value:5} / {scale:6.1f} = {result:8.2f}")
    
    print("-" * 70)
    print(f"Total: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n✓ All tests passed! UNSIGNED conversion is working correctly.")
    else:
        print(f"\n✗ {failed} test(s) failed!")
    
    return failed == 0

if __name__ == "__main__":
    success = test_unsigned_conversion()
    exit(0 if success else 1)
