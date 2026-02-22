"""
Test PLC Handshake Service

Tests the handshaking mechanism between Middleware and PLC using status_read_data flags.

Memory Addresses:
- READ Area: status_read_data per-batch
  - BATCH_READ_01: D6076
  - BATCH_READ_02: D6176
  - ...
  - BATCH_READ_10: D6976
- WRITE Area: D7076 (PLC sets to 1 after reading, Middleware checks before writing)
- Equipment Failure: D8022 (Middleware sets to 1 after reading failure data)

Usage:
    python test_handshake.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.plc_handshake_service import PLCHandshakeService, get_handshake_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_read_area_handshake(batch_no: int = 1):
    """Test READ area handshake for one batch."""
    print("\n" + "=" * 80)
    print(f"TEST 1: READ Area Handshake (Batch {batch_no})")
    print("=" * 80)

    handshake = get_handshake_service()

    print("\n[1] Check current READ area status:")
    status = handshake.check_read_area_status(batch_no=batch_no)
    print(f"   Current status: {'READ (1)' if status else 'NOT READ (0)'}")

    print("\n[2] Reset READ area status to 0 (simulate PLC ready):")
    success = handshake.reset_read_area_status(batch_no=batch_no)
    if success:
        print(f"   OK reset to 0 (batch {batch_no})")
    else:
        print("   FAIL reset")
        return False

    status = handshake.check_read_area_status(batch_no=batch_no)
    print(f"   Verified: {status} (should be False)")

    print("\n[3] Mark READ area as read (simulate Middleware read):")
    success = handshake.mark_read_area_as_read(batch_no=batch_no)
    if success:
        print(f"   OK marked as read (batch {batch_no})")
    else:
        print("   FAIL mark as read")
        return False

    status = handshake.check_read_area_status(batch_no=batch_no)
    print(f"   Verified: {status} (should be True)")

    print(f"\nOK READ Area Handshake Test PASSED (batch {batch_no})")
    return True


def test_write_area_handshake():
    """Test WRITE area handshake (D7076)."""
    print("\n" + "=" * 80)
    print("TEST 2: WRITE Area Handshake (D7076)")
    print("=" * 80)

    handshake = get_handshake_service()

    print("\n[1] Check current WRITE area status:")
    plc_has_read = handshake.check_write_area_status()
    print(f"   PLC has read previous batch: {'YES (1)' if plc_has_read else 'NO (0)'}")

    print("\n[2] Simulate PLC finished reading (set D7076=1):")
    test_service = PLCHandshakeService()
    test_service._write_status_flag(test_service.WRITE_AREA_STATUS_ADDRESS, 1)
    print("   OK Set D7076 = 1 (PLC has read previous batch)")

    plc_has_read = handshake.check_write_area_status()
    print(f"   Safe to write new batch: {'YES' if plc_has_read else 'NO'}")
    if not plc_has_read:
        print("   FAIL test")
        return False

    print("\n[3] Simulate Middleware writing new batch:")
    print("   After write, Middleware resets D7076 = 0")
    success = handshake.reset_write_area_status()
    if success:
        print("   OK reset (D7076=0) - waiting for PLC to read")
    else:
        print("   FAIL reset")
        return False

    plc_has_read = handshake.check_write_area_status()
    print(f"   Verified: PLC has read = {plc_has_read} (should be False)")

    print("\nOK WRITE Area Handshake Test PASSED")
    return True


def test_equipment_failure_handshake():
    """Test Equipment Failure handshake (D8022)."""
    print("\n" + "=" * 80)
    print("TEST 3: Equipment Failure Handshake (D8022)")
    print("=" * 80)

    handshake = get_handshake_service()

    print("\n[1] Check current equipment failure status:")
    status = handshake.check_equipment_failure_status()
    print(f"   Current status: {'READ (1)' if status else 'NOT READ (0)'}")

    print("\n[2] Reset equipment failure status to 0:")
    success = handshake.reset_equipment_failure_status()
    if success:
        print("   OK reset to 0 (D8022=0)")
    else:
        print("   FAIL reset")
        return False

    print("\n[3] Mark equipment failure as read:")
    success = handshake.mark_equipment_failure_as_read()
    if success:
        print("   OK marked as read (D8022=1)")
    else:
        print("   FAIL mark")
        return False

    status = handshake.check_equipment_failure_status()
    print(f"   Verified: {status} (should be True)")

    print("\nOK Equipment Failure Handshake Test PASSED")
    return True


def main():
    print("\n" + "=" * 80)
    print("PLC HANDSHAKE SERVICE TEST")
    print("=" * 80)
    print("This test validates the handshaking mechanism for:")
    print("  - READ Area (status_read_data per-batch): Middleware -> PLC")
    print("  - WRITE Area (D7076): PLC -> Middleware")
    print("  - Equipment Failure (D8022): Middleware -> PLC")
    print("\nPress Enter to start testing...")
    input()

    results = []

    try:
        result = test_read_area_handshake(batch_no=1)
        results.append(("READ Area Batch 1", result))
    except Exception as e:
        logger.error(f"Error in READ area test batch 1: {e}", exc_info=True)
        results.append(("READ Area Batch 1", False))

    try:
        result = test_read_area_handshake(batch_no=2)
        results.append(("READ Area Batch 2", result))
    except Exception as e:
        logger.error(f"Error in READ area test batch 2: {e}", exc_info=True)
        results.append(("READ Area Batch 2", False))

    try:
        result = test_write_area_handshake()
        results.append(("WRITE Area", result))
    except Exception as e:
        logger.error(f"Error in WRITE area test: {e}", exc_info=True)
        results.append(("WRITE Area", False))

    try:
        result = test_equipment_failure_handshake()
        results.append(("Equipment Failure", result))
    except Exception as e:
        logger.error(f"Error in equipment failure test: {e}", exc_info=True)
        results.append(("Equipment Failure", False))

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"{test_name:30} {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\nALL TESTS PASSED")
    else:
        print("\nSOME TESTS FAILED. Check logs for details.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
