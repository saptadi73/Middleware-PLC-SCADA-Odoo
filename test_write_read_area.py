"""
Test Write to READ_DATA_PLC_MAPPING Area (D6001-D6058)
Script untuk write data dari mo_batch ke PLC area yang dibaca oleh READ service.
Tujuan: Simulasi data PLC untuk testing read dan sync functionality.
"""

import json
import logging
import re
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import build_memory_write_frame, parse_memory_write_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReadAreaWriter:
    """Write data to READ_DATA_PLC_MAPPING area (D6001-D6058)"""

    def __init__(self):
        self.settings = get_settings()
        self.mapping: List[Dict[str, Any]] = []
        self._load_read_mapping()

    def _load_read_mapping(self):
        """Load READ_DATA_PLC_MAPPING.json"""
        reference_path = (
            Path(__file__).parent / "app" / "reference" / "READ_DATA_PLC_MAPPING.json"
        )

        if not reference_path.exists():
            raise FileNotFoundError(f"READ_DATA_PLC_MAPPING.json not found at {reference_path}")

        with open(reference_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.mapping = data.get("raw_list", [])

        logger.info(f"Loaded READ_DATA_PLC_MAPPING: {len(self.mapping)} fields")

    def _parse_dm_address(self, dm_str: str) -> tuple[int, int]:
        """
        Parse DM address string menjadi (start_address, word_count).

        Examples:
            "D6001" -> (6001, 1)
            "D6001-6008" -> (6001, 8)
        """
        dm_str = dm_str.strip().upper()

        # Single address: D6001
        if "-" not in dm_str:
            match = re.match(r"D(\d+)", dm_str)
            if not match:
                raise ValueError(f"Invalid DM address format: {dm_str}")
            address = int(match.group(1))
            return (address, 1)

        # Range address: D6001-6008
        match = re.match(r"D(\d+)-(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM range format: {dm_str}")

        start = int(match.group(1))
        end = int(match.group(2))
        count = end - start + 1

        if count <= 0:
            raise ValueError(f"Invalid DM range: {dm_str} (count={count})")

        return (start, count)

    def _convert_to_words(self, value: Any, data_type: str, scale: float = 1.0) -> List[int]:
        """
        Convert Python value to PLC words.

        Args:
            value: Python value
            data_type: "ASCII", "REAL", "boolean"
            scale: Scale factor for REAL values

        Returns:
            List of 16-bit words
        """
        if data_type == "ASCII":
            # Convert string to ASCII bytes (2 chars per word, big-endian)
            text = str(value)[:16].ljust(16, "\x00")  # Max 16 chars, pad with null
            words = []
            for i in range(0, len(text), 2):
                char1 = ord(text[i]) if i < len(text) else 0
                char2 = ord(text[i + 1]) if i + 1 < len(text) else 0
                word = (char1 << 8) | char2  # Big-endian
                words.append(word)
            return words

        elif data_type == "REAL":
            # Convert to scaled integer (apply scale factor)
            scaled_value = int(float(value) * scale)

            # Handle signed 16-bit integer
            if scaled_value < 0:
                scaled_value = 65536 + scaled_value  # Convert to unsigned
            elif scaled_value > 65535:
                scaled_value = 65535  # Cap at max

            return [scaled_value]

        elif data_type == "boolean":
            # Boolean: 0 or 1
            return [1 if value else 0]

        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _write_to_plc(self, address: int, words: List[int]) -> bool:
        """
        Write words to PLC memory using FINS protocol.

        Args:
            address: DM address (e.g., 6001)
            words: List of 16-bit words to write

        Returns:
            True if successful
        """
        try:
            # Build FINS write frame
            frame = build_memory_write_frame(
                sa=self.settings.client_node,  # Source node
                da=self.settings.plc_node,  # Destination node
                memory_area=0x82,  # DM area
                address=address,
                words=words,
            )

            # Send via UDP
            client = FinsUdpClient(
                plc_ip=self.settings.plc_ip,
                plc_port=self.settings.plc_port,
                timeout=self.settings.plc_timeout_sec,
            )

            response = client.send(frame)

            # Parse response
            result = parse_memory_write_response(response)

            if result.get("success"):
                logger.debug(f"Write success: D{address}, {len(words)} words")
                return True
            else:
                logger.error(f"Write failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"Error writing to PLC: {e}", exc_info=True)
            return False

    def write_batch_data(self, batch: TableSmoBatch) -> Dict[str, Any]:
        """
        Write mo_batch data to PLC READ area (D6001-D6058).

        Args:
            batch: mo_batch record from database

        Returns:
            Dict with write results
        """
        results = {
            "success": 0,
            "failed": 0,
            "errors": [],
        }

        # Silo mapping letter to consumption field name in READ_DATA_PLC_MAPPING
        silo_mapping = {
            "a": ("SILO ID 101 (SILO BESAR)", "SILO 1 Consumption"),
            "b": ("SILO ID 102 (SILO BESAR)", "SILO 2 Consumption"),
            "c": ("SILO ID 3 (SILO BESAR)", "SILO ID 103 Consumption"),
            "d": ("SILO ID 104", "SILO ID 104 Consumption"),
            "e": ("SILO ID 105", "SILO ID 105 Consumption"),
            "f": ("SILO ID 106", "SILO ID 106  Consumption"),
            "g": ("SILO ID 107", "SILO ID 107 Consumption"),
            "h": ("SILO ID 108", "SILO 108 Consumption"),
            "i": ("SILO ID 109", "SILO ID 109 Consumption"),
            "j": ("SILO ID 110", "SILO ID 110 Consumption"),
            "k": ("SILO ID 111", "SILO ID 111 Consumption"),
            "l": ("SILO ID 112", "SILO ID 112 Consumption"),
            "m": ("SILO ID 113", "SILO ID 113 Consumption"),
        }

        # Write each field
        for field_def in self.mapping:
            field_name = field_def.get("Informasi", "")
            dm_address = field_def.get("DM - Memory", "")
            data_type = field_def.get("Data Type", "")
            scale = float(field_def.get("scale", 1.0))

            try:
                # Get value from batch
                value = None

                if field_name == "NO-MO":
                    value = batch.mo_id

                elif field_name == "NO-BoM":
                    value = batch.finished_goods or batch.mo_id

                elif field_name == "finished_goods":
                    value = batch.finished_goods or "Unknown"

                elif field_name == "Quantity Goods_id":
                    value = float(batch.consumption) if batch.consumption else 0.0

                elif field_name == "status manufaturing":
                    value = batch.status_manufacturing

                elif field_name == "Status Operation":
                    value = batch.status_operation

                elif field_name == "weight_finished_good":
                    value = (
                        float(batch.actual_weight_quantity_finished_goods)
                        if batch.actual_weight_quantity_finished_goods
                        else 0.0
                    )

                else:
                    # Check silo fields
                    for letter, (id_field, consumption_field) in silo_mapping.items():
                        if field_name == id_field:
                            # Silo ID
                            value = getattr(batch, f"silo_{letter}", None)
                            break
                        elif field_name == consumption_field:
                            # Silo Consumption
                            value = getattr(batch, f"consumption_silo_{letter}", None)
                            break

                # Skip if no value
                if value is None:
                    logger.debug(f"Skip field (no value): {field_name}")
                    continue

                # Parse address
                address, word_count = self._parse_dm_address(dm_address)

                # Convert to words
                words = self._convert_to_words(value, data_type, scale)

                # Write to PLC
                if self._write_to_plc(address, words):
                    results["success"] += 1
                    logger.info(f"✓ Written: {field_name} = {value} → D{address}")
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to write {field_name}")

            except Exception as e:
                results["failed"] += 1
                error_msg = f"Error writing {field_name}: {e}"
                results["errors"].append(error_msg)
                logger.error(error_msg)

        return results


def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("TEST WRITE TO READ_DATA_PLC_MAPPING AREA (D6001-D6058)")
    print("=" * 80)
    print("\nThis script will:")
    print("1. Read batch_no=1 from mo_batch table")
    print("2. Write data to PLC READ area (D6001-D6058)")
    print("3. You can then test read and sync functionality")
    print("\nPrerequisites:")
    print("✓ Database has at least one record (batch_no=1)")
    print("✓ PLC is accessible at configured IP")
    print("✓ READ_DATA_PLC_MAPPING.json exists")
    print("\nPress Ctrl+C to cancel or Enter to continue...")
    input()

    try:
        # Get batch from database
        print("\n[1] Reading batch_no=1 from database...")
        with SessionLocal() as session:
            batch = session.query(TableSmoBatch).filter(TableSmoBatch.batch_no == 1).first()

            if not batch:
                print("✗ Batch not found! Please ensure batch_no=1 exists in mo_batch table.")
                return

            print(f"✓ Found batch: {batch.mo_id}")
            print(f"  Product: {batch.finished_goods}")
            print(f"  Consumption: {batch.consumption}")

            # Write to PLC
            print("\n[2] Writing data to PLC READ area...")
            writer = ReadAreaWriter()
            results = writer.write_batch_data(batch)

            print("\n" + "=" * 80)
            print("WRITE RESULTS")
            print("=" * 80)
            print(f"✓ Success: {results['success']} fields")
            print(f"✗ Failed: {results['failed']} fields")

            if results["errors"]:
                print("\nErrors:")
                for error in results["errors"]:
                    print(f"  - {error}")

            print("\n" + "=" * 80)
            print("NEXT STEPS")
            print("=" * 80)
            print("\n1. Test read from PLC:")
            print("   python test_plc_read.py")
            print("\n2. Test sync to database:")
            print("   python test_plc_sync.py")
            print("\n3. Test full workflow:")
            print("   python test_plc_workflow.py")
            print("\n" + "=" * 80)

    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
