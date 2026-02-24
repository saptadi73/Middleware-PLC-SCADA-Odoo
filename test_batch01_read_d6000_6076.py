#!/usr/bin/env python3
"""
Test script: Read PLC BATCH01 area D6000-D6076.

What it does:
1. Read 77 words directly from PLC (single FINS memory read).
2. Print raw word table for quick memory inspection.
3. Decode fields using BATCH_READ_01 mapping from READ_DATA_PLC_MAPPING.json.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)
from app.services.plc_read_service import get_plc_read_service


START_DM = 6000
END_DM = 6076
WORD_COUNT = END_DM - START_DM + 1


def print_header() -> None:
    print("\n" + "=" * 80)
    print("TEST READ BATCH01 D6000-D6076")
    print("=" * 80)


def read_raw_words() -> List[int]:
    read_service = get_plc_read_service()
    words = read_service._read_batch_snapshot_words(batch_no=1)
    if not words:
        raise RuntimeError(
            f"Failed to read D{START_DM}-D{END_DM} with quality snapshot"
        )
    return words


def print_raw_table(words: List[int]) -> None:
    print("\nRAW WORDS")
    print("-" * 80)
    print(f"Total words: {len(words)}")
    print("Address     Dec       Hex")
    print("-" * 80)

    for index, word in enumerate(words):
        address = START_DM + index
        print(f"D{address:<6} {word:<9} 0x{word:04X}")


def decode_fields(words: List[int]) -> Dict[str, Any]:
    read_service = get_plc_read_service()
    mapping = read_service.batch_mappings.get(1, [])
    decoded: Dict[str, Any] = {}

    for field_def in mapping:
        field_name = str(field_def.get("Informasi") or "")
        if not field_name:
            continue
        try:
            decoded[field_name] = read_service._decode_field_from_snapshot(
                words=words,
                field_def=field_def,
                batch_no=1,
            )
        except Exception:
            decoded[field_name] = None

    return decoded


def print_decoded(decoded: Dict[str, Any]) -> None:
    print("\nDECODED FIELDS (BATCH_READ_01)")
    print("-" * 80)

    key_fields = [
        "BATCH",
        "NO-MO",
        "NO-BoM",
        "finished_goods",
        "Quantity Goods_id",
        "SILO ID 101 Consumption",
        "SILO ID 102 Consumption",
        "SILO ID 103 Consumption",
        "status manufaturing",
        "Status Operation",
        "weight_finished_good",
        "status_read_data",
    ]

    for key in key_fields:
        print(f"{key:30}: {decoded.get(key)}")


def print_d6000_diagnostics(words: List[int]) -> None:
    if not words:
        return

    raw = words[0]
    signed16 = raw if raw <= 32767 else raw - 65536
    unsigned16 = raw
    swapped = ((raw & 0x00FF) << 8) | ((raw & 0xFF00) >> 8)
    swapped_signed16 = swapped if swapped <= 32767 else swapped - 65536

    print("\nD6000 DIAGNOSTICS")
    print("-" * 80)
    print(f"Raw word                : {raw} (0x{raw:04X})")
    print(f"INT16 signed            : {signed16}")
    print(f"INT16 unsigned          : {unsigned16}")
    print(f"Byte-swapped unsigned   : {swapped}")
    print(f"Byte-swapped signed     : {swapped_signed16}")
    if signed16 < 1 or signed16 > 10:
        print("[WARN] D6000 tidak berada di rentang batch normal (1..10).")


def main() -> int:
    print_header()
    print(f"Reading DM range: D{START_DM}-D{END_DM} ({WORD_COUNT} words)")

    try:
        words = read_raw_words()
    except Exception as exc:
        print(f"\n[ERROR] Failed reading D{START_DM}-D{END_DM}: {exc}")
        return 1

    print_raw_table(words)
    print_d6000_diagnostics(words)
    decoded = decode_fields(words)
    print_decoded(decoded)

    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
