"""
Test script untuk write data equipment failure ke PLC memory.
Menggunakan mapping dari equipment_failure_input.csv.
"""
import csv
import logging
import re
from pathlib import Path
from typing import List, Tuple

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    build_memory_write_frame,
    parse_memory_write_response,
)

logger = logging.getLogger(__name__)

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


def encode_ascii(value: str, length: int) -> List[int]:
    value = value or ""
    expected_words = int((length + 1) / 2)
    padded = value.ljust(expected_words * 2, "\x00")

    words = []
    for i in range(0, len(padded), 2):
        char1 = ord(padded[i]) if i < len(padded) else 0
        char2 = ord(padded[i + 1]) if i + 1 < len(padded) else 0
        word = (char1 << 8) | char2
        words.append(word)

    return words[:expected_words]


def encode_real_32(value: str, scale: str) -> List[int]:
    scale_val = float(scale) if scale not in (None, "") else 1.0
    int_value = int(float(value) * scale_val)
    if int_value < 0 or int_value > 0xFFFFFFFF:
        raise ValueError(f"Value out of 32-bit range: {int_value}")
    high = (int_value >> 16) & 0xFFFF
    low = int_value & 0xFFFF
    return [high, low]


def encode_bcd(value: str) -> int:
    number = int(value)
    if number < 0 or number > 9999:
        raise ValueError(f"BCD out of range (0-9999): {number}")
    digits = f"{number:04d}"
    bcd = 0
    for i, digit in enumerate(digits):
        bcd = (bcd << 4) | int(digit)
    return bcd


def write_words(address: int, words: List[int]) -> None:
    settings = get_settings()
    frame = build_memory_write_frame(
        area="DM",
        address=address,
        values=words,
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
        parse_memory_write_response(response.raw)


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    print("=" * 70)
    print("EQUIPMENT FAILURE WRITE TEST")
    print("=" * 70)

    for row in rows:
        field_name = row.get("Informasi", "")
        data_type = (row.get("Data Type", "") or "").upper()
        length = int(row.get("length") or 0)
        scale = row.get("scale", "")
        dm_address = row.get("DM - Memory", "")
        value = row.get("Value", "")

        address, expected_count = parse_dm_address(dm_address)

        if data_type == "ASCII":
            words = encode_ascii(str(value), length)
        elif data_type == "REAL":
            words = encode_real_32(str(value), scale)
        elif data_type == "BCD":
            words = [encode_bcd(str(value))]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

        if len(words) != expected_count:
            if len(words) < expected_count:
                words.extend([0] * (expected_count - len(words)))
            else:
                words = words[:expected_count]

        write_words(address, words)
        print(f"✓ Written {field_name} to {dm_address}: {value}")

    print("\nAll equipment failure test data written successfully.")


if __name__ == "__main__":
    main()
