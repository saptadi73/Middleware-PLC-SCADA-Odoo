#!/usr/bin/env python3
"""Debug test reader for READ BATCH01 only (D6000-D6076), complete output."""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from app.services.plc_read_service import get_plc_read_service


START_DM = 6000
END_DM = 6076
WORD_COUNT = END_DM - START_DM + 1
BATCH_NO = 1


def configure_debug_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def print_header() -> None:
    print("\n" + "=" * 110)
    print("DEBUG TEST - READ BATCH01 (KOMPLIT)")
    print("=" * 110)
    print(f"Batch   : {BATCH_NO}")
    print(f"DM Range: D{START_DM}-D{END_DM}")
    print(f"Words   : {WORD_COUNT}")


def read_snapshot_words() -> List[int]:
    read_service = get_plc_read_service()
    words = read_service._read_batch_snapshot_words(batch_no=BATCH_NO)
    if not words:
        raise RuntimeError(f"Failed reading D{START_DM}-D{END_DM} (snapshot empty)")
    if len(words) != WORD_COUNT:
        raise RuntimeError(
            f"Invalid snapshot length. Expected {WORD_COUNT}, got {len(words)}"
        )
    return words


def print_raw_words(words: List[int]) -> None:
    print("\n[RAW WORD TABLE]")
    print("-" * 110)
    print(f"{'Index':<7} {'Address':<10} {'Unsigned':<10} {'Signed16':<10} {'Hex':<10}")
    print("-" * 110)
    for index, word in enumerate(words):
        address = START_DM + index
        unsigned = word & 0xFFFF
        signed16 = unsigned if unsigned <= 32767 else unsigned - 65536
        print(f"{index:<7} D{address:<9} {unsigned:<10} {signed16:<10} 0x{unsigned:04X}")


def _words_to_hex(words: List[int]) -> str:
    return " ".join(f"0x{(word & 0xFFFF):04X}" for word in words)


def decode_complete_fields(words: List[int]) -> List[Dict[str, Any]]:
    read_service = get_plc_read_service()
    mapping = read_service._get_batch_mapping(BATCH_NO)
    rows: List[Dict[str, Any]] = []

    for field_def in mapping:
        field_name = str(field_def.get("Informasi") or "")
        if not field_name:
            continue

        data_type = str(field_def.get("Data Type") or "")
        dm_str = read_service._resolve_dm_string(field_def)
        start_address, word_count = read_service._parse_dm_address(dm_str)
        start_index = start_address - START_DM
        end_index = start_index + word_count

        if start_index < 0 or end_index > len(words):
            raw_words: List[int] = []
            decoded: Any = None
            decode_error = f"DM {dm_str} out of snapshot range"
        else:
            raw_words = words[start_index:end_index]
            try:
                decoded = read_service._decode_field_from_snapshot(
                    words=words,
                    field_def=field_def,
                    batch_no=BATCH_NO,
                )
                decode_error = ""
            except Exception as exc:
                decoded = None
                decode_error = str(exc)

        rows.append(
            {
                "no": field_def.get("No"),
                "name": field_name,
                "type": data_type,
                "scale": field_def.get("scale"),
                "dm": dm_str,
                "raw_words": raw_words,
                "decoded": decoded,
                "error": decode_error,
            }
        )

    return rows


def print_summary(rows: List[Dict[str, Any]]) -> None:
    print("\n[SUMMARY - KEY FIELDS]")
    print("-" * 110)
    key_names = {
        "BATCH",
        "NO-MO",
        "NO-BoM",
        "finished_goods",
        "Quantity Goods_id",
        "SILO ID 101 Consumption",
        "SILO ID 102 Consumption",
        "status manufaturing",
        "Status Operation",
        "weight_finished_good",
        "status_read_data",
    }
    for row in rows:
        if row["name"] in key_names:
            print(f"{row['name']:<35}: {row['decoded']}")


def print_complete_debug(rows: List[Dict[str, Any]]) -> None:
    print("\n[COMPLETE FIELD DEBUG - BATCH_READ_01]")
    print("-" * 110)
    for row in rows:
        print(f"No       : {row['no']}")
        print(f"Field    : {row['name']}")
        print(f"Type     : {row['type']}")
        print(f"Scale    : {row['scale']}")
        print(f"DM       : {row['dm']}")
        print(f"Raw Dec  : {row['raw_words']}")
        print(f"Raw Hex  : {_words_to_hex(row['raw_words'])}")
        print(f"Decoded  : {row['decoded']}")
        if row["error"]:
            print(f"Error    : {row['error']}")
        print("-" * 110)


def main() -> int:
    configure_debug_logging()
    print_header()

    try:
        words = read_snapshot_words()
    except Exception as exc:
        print(f"\n[ERROR] Failed reading snapshot: {exc}")
        return 1

    print_raw_words(words)
    rows = decode_complete_fields(words)
    print_summary(rows)
    print_complete_debug(rows)

    print("\n" + "=" * 110)
    print("DONE - READ BATCH01 COMPLETE DEBUG")
    print("=" * 110)
    return 0


if __name__ == "__main__":
    sys.exit(main())
