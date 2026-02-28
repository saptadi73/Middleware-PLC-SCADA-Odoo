#!/usr/bin/env python3
"""Debug hasil WRITE area PLC untuk BATCH01-BATCH10 (D7000-D7976)."""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)


BATCH_MIN = 1
BATCH_MAX = 10
BATCH_WORD_COUNT = 77
BATCH_START_DM = 7000
BATCH_STEP = 100

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def load_write_reference() -> Dict[str, List[Dict[str, Any]]]:
    reference_path = Path(__file__).parent / "app" / "reference" / "MASTER_BATCH_REFERENCE.json"
    with open(reference_path, "r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    return data


def parse_dm_address(dm_str: str) -> Tuple[int, int]:
    dm_str = dm_str.strip().upper().replace(" ", "")

    if "-" not in dm_str:
        match = re.match(r"D(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM address format: {dm_str}")
        return int(match.group(1)), 1

    match = re.match(r"D(\d+)-D?(\d+)", dm_str)
    if not match:
        raise ValueError(f"Invalid DM range format: {dm_str}")

    start_address = int(match.group(1))
    end_address = int(match.group(2))
    count = end_address - start_address + 1
    if count <= 0:
        raise ValueError(f"Invalid DM range: {dm_str}")

    return start_address, count


def convert_from_words(words: List[int], data_type: str, scale: Any = None) -> Any:
    normalized_type = str(data_type).upper()

    if normalized_type == "BOOLEAN":
        return bool(words[0]) if words else False

    if normalized_type == "INT":
        if not words:
            return 0
        if len(words) >= 2:
            raw_value = (words[0] << 16) | words[1]
            if raw_value > 2147483647:
                raw_value -= 4294967296
            return int(raw_value)
        raw_value = words[0]
        if raw_value > 32767:
            raw_value -= 65536
        return int(raw_value)

    if normalized_type == "REAL":
        if not words:
            return 0.0
        if len(words) >= 2:
            raw_value = (words[0] << 16) | words[1]
            if raw_value > 2147483647:
                raw_value -= 4294967296
        else:
            raw_value = words[0]
            if raw_value > 32767:
                raw_value -= 65536

        scale_value = float(scale) if scale not in (None, 0, "", "None") else 1.0
        return float(raw_value) / scale_value

    if normalized_type == "ASCII":
        chars: List[str] = []
        for word in words:
            high = (word >> 8) & 0xFF
            low = word & 0xFF
            if 32 <= high <= 126:
                chars.append(chr(high))
            if 32 <= low <= 126:
                chars.append(chr(low))
        return "".join(chars).rstrip("\x00")

    return words


def format_hex_words(words: List[int]) -> str:
    return " ".join(f"0x{(word & 0xFFFF):04X}" for word in words)


def read_words(address: int, count: int) -> List[int]:
    settings = get_settings()

    with FinsUdpClient(
        ip=settings.plc_ip,
        port=settings.plc_port,
        timeout_sec=settings.plc_timeout_sec,
    ) as client:
        request = MemoryReadRequest(area="DM", address=address, count=count)
        frame = build_memory_read_frame(
            req=request,
            client_node=settings.client_node,
            plc_node=settings.plc_node,
            sid=0x00,
        )
        client.send_raw_hex(frame.hex())
        response = client.recv()
        return parse_memory_read_response(response.raw, expected_count=count)


def validate_decoded_type(value: Any, data_type: str) -> bool:
    normalized_type = str(data_type).upper()
    if normalized_type == "BOOLEAN":
        return isinstance(value, bool)
    if normalized_type == "ASCII":
        return isinstance(value, str)
    if normalized_type == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if normalized_type == "REAL":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def debug_batch(batch_no: int, fields: List[Dict[str, Any]]) -> None:
    start_dm = BATCH_START_DM + ((batch_no - 1) * BATCH_STEP)
    end_dm = start_dm + BATCH_WORD_COUNT - 1

    print("\n" + "=" * 120)
    print(f"WRITE BATCH{batch_no:02d} DEBUG | DM D{start_dm}-D{end_dm} | words={BATCH_WORD_COUNT}")
    print("=" * 120)

    words = read_words(start_dm, BATCH_WORD_COUNT)

    print("\n[RAW WORD TABLE]")
    print("-" * 120)
    print(f"{'Index':<7} {'Address':<10} {'Unsigned':<10} {'Signed16':<10} {'Hex':<10}")
    print("-" * 120)
    for idx, word in enumerate(words):
        address = start_dm + idx
        unsigned = word & 0xFFFF
        signed_value = unsigned if unsigned <= 32767 else unsigned - 65536
        print(f"{idx:<7} D{address:<9} {unsigned:<10} {signed_value:<10} 0x{unsigned:04X}")

    rows: List[Dict[str, Any]] = []
    type_ok_count = 0

    for field in fields:
        field_name = str(field.get("Informasi") or "")
        if not field_name:
            continue

        dm_string = str(field.get("DM") or "")
        data_type = str(field.get("Data Type") or "")
        scale = field.get("scale")

        start_addr, word_count = parse_dm_address(dm_string)
        start_index = start_addr - start_dm
        end_index = start_index + word_count

        if start_index < 0 or end_index > len(words):
            raw_words: List[int] = []
            decoded: Any = None
            error = f"DM {dm_string} out of batch snapshot range"
            type_valid = False
        else:
            raw_words = words[start_index:end_index]
            try:
                decoded = convert_from_words(raw_words, data_type, scale)
                error = ""
                type_valid = validate_decoded_type(decoded, data_type)
                if type_valid:
                    type_ok_count += 1
            except Exception as exc:
                decoded = None
                error = str(exc)
                type_valid = False

        rows.append(
            {
                "no": field.get("No"),
                "name": field_name,
                "type": data_type,
                "scale": scale,
                "dm": dm_string,
                "raw_words": raw_words,
                "decoded": decoded,
                "type_valid": type_valid,
                "error": error,
            }
        )

    print("\n[SUMMARY - KEY FIELDS]")
    print("-" * 120)
    key_fields = {
        "BATCH",
        "NO-MO",
        "NO-BoM",
        "finished_goods",
        "Quantity Goods_id",
        "SILO ID 101 (SILO BESAR)",
        "SILO ID 101 Consumption",
        "status manufaturing",
        "Status Operation",
        "weight_finished_good",
        "status_read_data",
    }
    for row in rows:
        if row["name"] in key_fields:
            print(f"{row['name']:<35}: {row['decoded']}")

    print("\n[COMPLETE FIELD DEBUG]")
    print("-" * 120)
    for row in rows:
        print(f"No          : {row['no']}")
        print(f"Field       : {row['name']}")
        print(f"Type        : {row['type']}")
        print(f"Type Valid  : {row['type_valid']}")
        print(f"Scale       : {row['scale']}")
        print(f"DM          : {row['dm']}")
        print(f"Raw Dec     : {row['raw_words']}")
        print(f"Raw Hex     : {format_hex_words(row['raw_words'])}")
        print(f"Decoded     : {row['decoded']}")
        if row["error"]:
            print(f"Error       : {row['error']}")
        print("-" * 120)

    print("\n[TYPE CHECK RESULT]")
    print("-" * 120)
    print(f"BATCH{batch_no:02d}: {type_ok_count}/{len(rows)} field(s) decoded with expected data type")


def main() -> int:
    configure_logging()

    print("\n" + "=" * 120)
    print("DEBUG HASIL WRITE PLC - BATCH01 s/d BATCH10")
    print("Reference: MASTER_BATCH_REFERENCE.json")
    print("Range    : D7000-D7976")
    print("=" * 120)

    try:
        reference = load_write_reference()
    except Exception as exc:
        print(f"[ERROR] Failed loading reference mapping: {exc}")
        return 1

    for batch_no in range(BATCH_MIN, BATCH_MAX + 1):
        key = f"WRITE_BATCH{batch_no:02d}"
        fields = reference.get(key, [])
        if not fields:
            print(f"\n[WARNING] Mapping {key} tidak ditemukan, skip")
            continue

        try:
            debug_batch(batch_no, fields)
        except Exception as exc:
            print(f"\n[ERROR] Failed debug {key}: {exc}")

    print("\n" + "=" * 120)
    print("DONE - DEBUG WRITE BATCH01-BATCH10")
    print("=" * 120)
    return 0


if __name__ == "__main__":
    sys.exit(main())
