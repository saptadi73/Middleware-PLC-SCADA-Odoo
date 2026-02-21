"""
Write PLC READ area (D6001-D6076) from CSV input.
CSV file: app/reference/read_data_plc_input.csv
Supports 15 equipment: 13 Silos (101-113) + 2 Liquid Tanks (114-115)
"""

import csv
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import build_memory_write_frame, parse_memory_write_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReadAreaCsvWriter:
    """Write CSV values to PLC READ area (D6001-D6076)."""

    def __init__(self, csv_path: Path):
        self.settings = get_settings()
        self.csv_path = csv_path
        self.rows: List[Dict[str, str]] = []
        self._load_csv()

    def _load_csv(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV not found at {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self.rows = [row for row in reader]

        logger.info("Loaded CSV rows: %s", len(self.rows))

    def _parse_dm_address(self, dm_str: str) -> tuple[int, int]:
        dm_str = dm_str.strip().upper().replace(" ", "")

        if "-" not in dm_str:
            match = re.match(r"D(\d+)", dm_str)
            if not match:
                raise ValueError(f"Invalid DM address format: {dm_str}")
            address = int(match.group(1))
            return (address, 1)

        match = re.match(r"D(\d+)-(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM range format: {dm_str}")

        start = int(match.group(1))
        end = int(match.group(2))
        count = end - start + 1
        if count <= 0:
            raise ValueError(f"Invalid DM range: {dm_str} (count={count})")

        return (start, count)

    def _convert_to_words(
        self,
        value: Any,
        data_type: str,
        length: Optional[int],
        scale: Optional[float],
        word_count: Optional[int],
    ) -> List[int]:
        data_type = data_type.upper()

        if data_type == "BOOLEAN":
            return [1 if self._to_bool(value) else 0]

        if data_type == "REAL":
            if value is None or value == "":
                return [0]

            scale_value = scale if scale else 1.0
            scaled_value = int(float(value) * scale_value)

            # If mapping uses 2 words, always write 32-bit value
            if word_count and word_count >= 2:
                unsigned_value = scaled_value & 0xFFFFFFFF
                upper = (unsigned_value >> 16) & 0xFFFF
                lower = unsigned_value & 0xFFFF
                return [upper, lower]

            # 1-word fallback
            if scaled_value < 0:
                scaled_value = 65536 + scaled_value
            elif scaled_value > 65535:
                scaled_value = 65535

            return [scaled_value]

        if data_type == "ASCII":
            text_value = str(value) if value is not None else ""
            expected_words = int((length or len(text_value) + 1) / 2)
            padded = text_value.ljust(expected_words * 2, "\x00")

            words = []
            for i in range(0, len(padded), 2):
                char1 = ord(padded[i]) if i < len(padded) else 0
                char2 = ord(padded[i + 1]) if i + 1 < len(padded) else 0
                words.append((char1 << 8) | char2)

            return words[:expected_words]

        raise ValueError(f"Unsupported data type: {data_type}")

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value

        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "y", "on"}

    def _write_to_plc(self, address: int, words: List[int]) -> None:
        frame = build_memory_write_frame(
            area="DM",
            address=address,
            values=words,
            client_node=self.settings.client_node,
            plc_node=self.settings.plc_node,
            sid=0x00,
        )

        with FinsUdpClient(
            ip=self.settings.plc_ip,
            port=self.settings.plc_port,
            timeout_sec=self.settings.plc_timeout_sec,
        ) as client:
            client.send_raw_hex(frame.hex())
            response = client.recv()

        parse_memory_write_response(response.raw)

    def write_from_csv(self) -> Dict[str, Any]:
        results = {"success": 0, "failed": 0, "errors": []}

        for row in self.rows:
            field_name = (row.get("Informasi") or "").strip()
            dm_address = (row.get("DM - Memory") or "").strip()
            data_type = (row.get("Data Type") or "").strip()
            length = row.get("length")
            scale = row.get("scale")
            value = row.get("Value")

            if not field_name or not dm_address or not data_type:
                continue

            if value is None or str(value).strip() == "":
                logger.debug("Skip field (no value): %s", field_name)
                continue

            try:
                length_value = int(length) if length else None
                scale_value = float(scale) if scale else None
                address, word_count = self._parse_dm_address(dm_address)
                words = self._convert_to_words(
                    value, data_type, length_value, scale_value, word_count
                )

                if len(words) != word_count:
                    if len(words) < word_count:
                        words.extend([0] * (word_count - len(words)))
                    else:
                        words = words[:word_count]

                self._write_to_plc(address, words)
                results["success"] += 1
                logger.info("✓ Written: %s = %s → D%s", field_name, value, address)

            except Exception as exc:
                results["failed"] += 1
                error_msg = f"Error writing {field_name}: {exc}"
                results["errors"].append(error_msg)
                logger.error(error_msg)

        return results


def main() -> None:
    csv_path = Path(__file__).parent / "app" / "reference" / "read_data_plc_input.csv"

    print("\n" + "=" * 80)
    print("WRITE PLC READ AREA FROM CSV")
    print("=" * 80)
    print(f"CSV path: {csv_path}")
    print("This will write values into D6001-D6076 using CSV Value column.")
    print("\nPress Ctrl+C to cancel or Enter to continue...")
    input()

    writer = ReadAreaCsvWriter(csv_path)
    results = writer.write_from_csv()

    print("\n" + "=" * 80)
    print("WRITE RESULTS")
    print("=" * 80)
    print(f"✓ Success: {results['success']} fields")
    print(f"✗ Failed: {results['failed']} fields")

    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - {error}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
