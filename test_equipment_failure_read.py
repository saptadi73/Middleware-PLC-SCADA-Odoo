"""
Test script untuk read data equipment failure dari PLC memory.
Menggunakan mapping dari equipment_failure_input.csv.
"""
import csv
import re
from pathlib import Path
from typing import List, Tuple

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)

CSV_PATH = Path("app/reference/equipment_failure_input.csv")


def parse_dm_address(dm_str: str) -> Tuple[int, int]:
    dm_str = dm_str.strip().upper().replace(" ", "")
    if "-" not in dm_str:
        match = re.match(r"D(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM address format: {dm_str}")
        address = int(match.group(1))
        return address, 1

    match = re.match(r"D(\d+)-(\d+)", dm_str)
    if not match:
        raise ValueError(f"Invalid DM range format: {dm_str}")

    start = int(match.group(1))
    end = int(match.group(2))
    count = end - start + 1
    if count <= 0:
        raise ValueError(f"Invalid DM range: {dm_str} (count={count})")

    return start, count


def decode_ascii(words: List[int]) -> str:
    chars = []
    for word in words:
        char1 = (word >> 8) & 0xFF
        char2 = word & 0xFF
        if char1 != 0:
            chars.append(chr(char1))
        if char2 != 0:
            chars.append(chr(char2))
    return "".join(chars).rstrip("\x00")


def decode_real_32(words: List[int], scale: str) -> float:
    if len(words) < 2:
        return 0.0
    raw_value = (words[0] << 16) | words[1]
    scale_val = float(scale) if scale not in (None, "") else 1.0
    return float(raw_value) / scale_val


def decode_bcd(word: int) -> int:
    digits = []
    for shift in (12, 8, 4, 0):
        digits.append(str((word >> shift) & 0x0F))
    return int("".join(digits))


def read_words(address: int, count: int) -> List[int]:
    settings = get_settings()
    req = MemoryReadRequest(area="DM", address=address, count=count)
    frame = build_memory_read_frame(
        req,
        client_node=settings.client_node,
        plc_node=settings.plc_node,
    )

    with FinsUdpClient(
        ip=settings.plc_ip,
        port=settings.plc_port,
        timeout_sec=settings.plc_timeout_sec,
    ) as client:
        client.send_raw_hex(frame.hex())
        response = client.recv()
        return parse_memory_read_response(response.raw, count)


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    print("=" * 70)
    print("EQUIPMENT FAILURE READ TEST")
    print("=" * 70)

    decoded = {}

    for row in rows:
        field_name = row.get("Informasi", "")
        data_type = (row.get("Data Type", "") or "").upper()
        scale = row.get("scale", "")
        dm_address = row.get("DM - Memory", "")

        address, word_count = parse_dm_address(dm_address)
        words = read_words(address, word_count)

        if data_type == "ASCII":
            value = decode_ascii(words)
        elif data_type == "REAL":
            value = decode_real_32(words, scale)
        elif data_type == "BCD":
            value = decode_bcd(words[0]) if words else None
        else:
            value = None

        decoded[field_name] = value
        print(f"✓ Read {field_name} from {dm_address}: {value}")

    if all(k in decoded for k in ("Year", "Month", "Day", "Hour", "Minute", "Second")):
        timestamp = (
            f"{decoded['Year']:04d}-{decoded['Month']:02d}-{decoded['Day']:02d} "
            f"{decoded['Hour']:02d}:{decoded['Minute']:02d}:{decoded['Second']:02d}"
        )
        print(f"\nCombined timestamp: {timestamp}")

    print("\nRead test completed.")


if __name__ == "__main__":
    main()
