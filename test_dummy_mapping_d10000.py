#!/usr/bin/env python3
"""
Write and verify dummy batch payload at D10000 using WRITE_BATCH01 memory structure.

Scope follows MASTER_BATCH_REFERENCE from:
- SILO ID 101 (SILO BESAR)
- ... up to status_read_data

Use case:
- Validate REAL/INT/BOOLEAN memory alignment after address remapping.
- Ensure SILO 101-103 consumption values are >= 1000 kg.
"""

from __future__ import annotations

import json
import csv
import random
import re
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    build_memory_write_frame,
    parse_memory_read_response,
    parse_memory_write_response,
)


REFERENCE_FILE = Path(__file__).parent / "app" / "reference" / "MASTER_BATCH_REFERENCE.json"
REFERENCE_BATCH = "WRITE_BATCH01"
ORIGINAL_START_ADDR = 7027
TARGET_START_ADDR = 10000
RANDOM_SEED = 20260302
REPORT_FILE = Path(__file__).parent / "test_output_dummy_mapping_d10000.csv"


def parse_dm(dm_str: str) -> Tuple[int, int]:
    dm = dm_str.strip().upper().replace(" ", "")
    if "-" not in dm:
        match = re.match(r"D(\d+)", dm)
        if not match:
            raise ValueError(f"Invalid DM address: {dm_str}")
        return int(match.group(1)), 1

    match = re.match(r"D(\d+)-D?(\d+)", dm)
    if not match:
        raise ValueError(f"Invalid DM range: {dm_str}")

    start = int(match.group(1))
    end = int(match.group(2))
    count = end - start + 1
    if count <= 0:
        raise ValueError(f"Invalid DM range count: {dm_str}")
    return start, count


def load_fields() -> List[Dict[str, Any]]:
    with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    fields = data.get(REFERENCE_BATCH, [])

    selected: List[Dict[str, Any]] = []
    for item in fields:
        no = int(item.get("No", 0))
        if no < 6:
            continue
        selected.append(item)

    return selected


def choose_node_combo() -> Tuple[int, int]:
    settings = get_settings()
    client_node = int(settings.client_node)
    plc_node = int(settings.plc_node)
    try:
        words = read_words(7000, 1, client_node, plc_node, timeout_sec=0.7)
        if not words:
            raise RuntimeError("empty probe response")
    except Exception as exc:
        raise RuntimeError(
            f"FINS probe failed using .env nodes client={client_node}, plc={plc_node}: {exc}"
        ) from exc
    return client_node, plc_node


def read_words(
    address: int,
    count: int,
    client_node: int,
    plc_node: int,
    timeout_sec: float = 1.0,
    retries: int = 4,
) -> List[int]:
    settings = get_settings()
    req = MemoryReadRequest(area="DM", address=address, count=count)
    frame = build_memory_read_frame(req=req, client_node=client_node, plc_node=plc_node, sid=0)
    last_exc: Exception | None = None

    for _ in range(retries):
        try:
            with FinsUdpClient(
                ip=settings.plc_ip,
                port=settings.plc_port,
                timeout_sec=timeout_sec,
            ) as client:
                client.send_raw_hex(frame.hex())
                response = client.recv()
                return parse_memory_read_response(response.raw, expected_count=count)
        except (TimeoutError, socket.timeout, ValueError, RuntimeError) as exc:
            last_exc = exc
            time.sleep(0.08)

    raise RuntimeError(f"Read failed at D{address}") from last_exc


def write_words(
    address: int,
    values: List[int],
    client_node: int,
    plc_node: int,
    timeout_sec: float = 1.0,
    retries: int = 4,
) -> None:
    settings = get_settings()
    frame = build_memory_write_frame(
        area="DM",
        address=address,
        values=values,
        client_node=client_node,
        plc_node=plc_node,
        sid=0,
    )
    last_exc: Exception | None = None

    for _ in range(retries):
        try:
            with FinsUdpClient(
                ip=settings.plc_ip,
                port=settings.plc_port,
                timeout_sec=timeout_sec,
            ) as client:
                client.send_raw_hex(frame.hex())
                response = client.recv()
                parse_memory_write_response(response.raw)
                return
        except (TimeoutError, socket.timeout, ValueError, RuntimeError) as exc:
            last_exc = exc
            time.sleep(0.08)

    raise RuntimeError(f"Write failed at D{address}") from last_exc


def gen_dummy_value(field_name: str, data_type: str, rng: random.Random) -> Any:
    upper = field_name.upper()

    id_match = re.match(r"(SILO|LQ)\s+ID\s+(\d+)(?:\s*\(.*\))?$", upper)
    if id_match:
        return int(id_match.group(2))

    cons_match = re.match(r"(SILO|LQ)\s+ID\s+(\d+)\s+CONSUMPTION$", upper)
    if cons_match:
        eq_no = int(cons_match.group(2))
        if eq_no in (101, 102, 103):
            return round(rng.uniform(1000.0, 1800.0), 2)
        return round(rng.uniform(20.0, 900.0), 2)

    if "STATUS MANUFATURING" in upper:
        return 0
    if "STATUS OPERATION" in upper:
        return 0
    if "STATUS_READ_DATA" in upper:
        return 0
    if "WEIGHT_FINISHED_GOOD" in upper:
        return round(rng.uniform(500.0, 2500.0), 2)

    if data_type.upper() == "BOOLEAN":
        return 0
    if data_type.upper() == "INT":
        return 0
    if data_type.upper() == "REAL":
        return 0.0
    return 0


def encode_words(value: Any, data_type: str, scale: float, word_count: int) -> List[int]:
    dt = data_type.upper()

    if dt == "BOOLEAN":
        return [1 if bool(value) else 0]

    if dt == "INT":
        int_val = int(value)
        if word_count >= 2:
            if int_val < -2147483648 or int_val > 2147483647:
                raise ValueError(f"INT32 out of range: {int_val}")
            return [(int_val >> 16) & 0xFFFF, int_val & 0xFFFF]
        if int_val < -32768 or int_val > 32767:
            raise ValueError(f"INT16 out of range: {int_val}")
        return [int_val & 0xFFFF]

    if dt == "REAL":
        raw = int(round(float(value) * (scale or 1.0)))
        if word_count >= 2:
            if raw < -2147483648 or raw > 2147483647:
                raise ValueError(f"REAL(int32) out of range: {raw}")
            return [(raw >> 16) & 0xFFFF, raw & 0xFFFF]
        if raw < -32768 or raw > 32767:
            raise ValueError(f"REAL(int16) out of range: {raw}")
        return [raw & 0xFFFF]

    raise ValueError(f"Unsupported type for this test: {data_type}")


def decode_value(words: List[int], data_type: str, scale: float) -> Any:
    dt = data_type.upper()
    if dt == "BOOLEAN":
        return 1 if words[0] != 0 else 0

    if dt == "INT":
        if len(words) >= 2:
            raw = ((words[0] & 0xFFFF) << 16) | (words[1] & 0xFFFF)
            if raw > 0x7FFFFFFF:
                raw -= 0x100000000
            return int(raw)
        raw = words[0]
        if raw > 32767:
            raw -= 65536
        return int(raw)

    if dt == "REAL":
        if len(words) >= 2:
            raw = ((words[0] & 0xFFFF) << 16) | (words[1] & 0xFFFF)
            if raw > 0x7FFFFFFF:
                raw -= 0x100000000
        else:
            raw = words[0]
            if raw > 32767:
                raw -= 65536
        divisor = scale or 1.0
        return raw / divisor

    raise ValueError(f"Unsupported type for decode: {data_type}")


def main() -> int:
    rng = random.Random(RANDOM_SEED)
    fields = load_fields()
    client_node, plc_node = choose_node_combo()
    print(f"Using FINS nodes client={client_node}, plc={plc_node}")
    print(f"Writing mapped fields from D{ORIGINAL_START_ADDR}..D7076 to start D{TARGET_START_ADDR}")

    failures: List[str] = []
    rows: List[Dict[str, Any]] = []
    writes = 0

    for item in fields:
        name = str(item["Informasi"])
        data_type = str(item["Data Type"])
        scale = float(item.get("scale", 1.0) or 1.0)
        src_addr, word_count = parse_dm(str(item["DM"]))
        dst_addr = TARGET_START_ADDR + (src_addr - ORIGINAL_START_ADDR)

        value = gen_dummy_value(name, data_type, rng)
        words = encode_words(value, data_type, scale, word_count)
        if len(words) < word_count:
            words.extend([0] * (word_count - len(words)))
        elif len(words) > word_count:
            words = words[:word_count]

        write_words(dst_addr, words, client_node, plc_node)
        read_back_words = read_words(dst_addr, word_count, client_node, plc_node)
        decoded = decode_value(read_back_words, data_type, scale)

        writes += 1
        ok = True
        if data_type.upper() in ("INT", "BOOLEAN"):
            ok = int(decoded) == int(value)
        elif data_type.upper() == "REAL":
            ok = abs(float(decoded) - float(value)) <= 0.01

        if not ok:
            failures.append(
                f"{name} @D{dst_addr}: expected={value} decoded={decoded} raw={read_back_words}"
            )

        rows.append(
            {
                "field": name,
                "src_dm": src_addr,
                "dst_dm": dst_addr,
                "data_type": data_type,
                "scale": scale,
                "expected": value,
                "decoded": decoded,
                "raw_words": " ".join(str(w) for w in read_back_words),
                "result": "OK" if ok else "FAIL",
            }
        )

        print(
            f"{name:<28} src=D{src_addr:<4} dst=D{dst_addr:<5} "
            f"value={value} decoded={decoded} raw={read_back_words}"
        )

    with open(REPORT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field",
                "src_dm",
                "dst_dm",
                "data_type",
                "scale",
                "expected",
                "decoded",
                "raw_words",
                "result",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print("-" * 100)
    print(f"Write+verify fields: {writes}")
    print(f"Report CSV: {REPORT_FILE}")
    if failures:
        print(f"FAILED fields: {len(failures)}")
        for msg in failures:
            print("  -", msg)
        return 1

    print("All fields verified OK. Mapping looks aligned (no shift detected).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
