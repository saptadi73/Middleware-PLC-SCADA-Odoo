from __future__ import annotations

import struct
from dataclasses import dataclass


AREA_CODES = {
    "CIO": 0x30,
    "WR": 0x31,
    "HR": 0x32,
    "DM": 0x82,
}


@dataclass(frozen=True)
class MemoryReadRequest:
    area: str
    address: int
    count: int


def build_fins_header(
    client_node: int,
    plc_node: int,
    sid: int = 0x00,
) -> bytes:
    icf = 0x80  # response required
    rsv = 0x00
    gct = 0x02
    dna = 0x00
    da1 = plc_node & 0xFF
    da2 = 0x00
    sna = 0x00
    sa1 = client_node & 0xFF
    sa2 = 0x00
    sid = sid & 0xFF

    return bytes([icf, rsv, gct, dna, da1, da2, sna, sa1, sa2, sid])


def build_memory_read_command(req: MemoryReadRequest) -> bytes:
    if req.area not in AREA_CODES:
        raise ValueError(f"Unsupported area: {req.area}")

    area_code = AREA_CODES[req.area]
    address = req.address
    if address < 0 or address > 0xFFFF:
        raise ValueError("Address must be 0..65535")

    bit_address = 0x00
    count = req.count
    if count <= 0 or count > 0xFFFF:
        raise ValueError("Count must be 1..65535")

    # FINS command: MRC=0x01, SRC=0x01 (Memory Area Read)
    # Command format: area(1) + address(2) + bit(1) + count(2)
    return bytes([0x01, 0x01, area_code]) + struct.pack(
        ">HBH",
        address,
        bit_address,
        count,
    )


def build_memory_read_frame(
    req: MemoryReadRequest,
    client_node: int,
    plc_node: int,
    sid: int = 0x00,
) -> bytes:
    header = build_fins_header(client_node, plc_node, sid)
    command = build_memory_read_command(req)
    return header + command


def build_memory_write_command(area: str, address: int, values: list[int]) -> bytes:
    if area not in AREA_CODES:
        raise ValueError(f"Unsupported area: {area}")
    if address < 0 or address > 0xFFFF:
        raise ValueError("Address must be 0..65535")
    if not values:
        raise ValueError("Values cannot be empty")
    if len(values) > 0xFFFF:
        raise ValueError("Too many values")

    area_code = AREA_CODES[area]
    bit_address = 0x00
    count = len(values)

    # Convert values to bytes, handling both signed and unsigned integers
    # For values in range -32768 to 32767, use signed=True
    # For values in range 0 to 65535, convert properly
    data_parts = []
    for v in values:
        if -32768 <= v <= 32767:
            # Handle as signed 16-bit integer
            data_parts.append(v.to_bytes(2, byteorder="big", signed=True))
        elif 0 <= v <= 65535:
            # Handle as unsigned 16-bit integer
            data_parts.append(v.to_bytes(2, byteorder="big", signed=False))
        else:
            raise ValueError(f"Value {v} out of range for 16-bit integer")
    
    data = b"".join(data_parts)
    return bytes([0x01, 0x02, area_code]) + struct.pack(
        ">HBH",
        address,
        bit_address,
        count,
    ) + data


def build_memory_write_frame(
    area: str,
    address: int,
    values: list[int],
    client_node: int,
    plc_node: int,
    sid: int = 0x00,
) -> bytes:
    header = build_fins_header(client_node, plc_node, sid)
    command = build_memory_write_command(area, address, values)
    return header + command


def parse_memory_write_response(raw: bytes) -> None:
    if len(raw) < 14:
        raise ValueError(f"Response too short: expected at least 14 bytes, got {len(raw)} bytes. Hex: {raw.hex()}")

    # Check FINS response header
    # Byte 12-13: End code (should be 0x0000 for success)
    end_code = raw[12:14]
    if end_code != b"\x00\x00":
        error_code = int.from_bytes(end_code, byteorder="big")
        error_messages = {
            0x0101: "Local node not in network",
            0x0102: "Token timeout",
            0x0103: "Retries failed",
            0x0104: "Too many send frames",
            0x0105: "Node address range error",
            0x0106: "Node address duplication",
            0x0201: "Destination node not in network",
            0x0202: "Unit missing",
            0x0203: "Third node missing",
            0x0204: "Destination node busy",
            0x0205: "Response timeout",
            0x0301: "Communications controller error",
            0x0302: "CPU Unit error",
            0x0303: "Controller error",
            0x0304: "Unit number error",
            0x0401: "Undefined command",
            0x0402: "Not supported by model/version",
            0x1001: "Command too long",
            0x1002: "Command too short",
            0x1003: "Elements/data don't match",
            0x1004: "Command format error",
            0x1005: "Header error",
            0x1101: "Area classification missing",
            0x1102: "Access size error",
            0x1103: "Address range error",
            0x1104: "Address range exceeded",
            0x1106: "Program missing",
            0x1109: "Relational error",
            0x110A: "Duplicate data access",
            0x110B: "Response too long",
            0x110C: "Parameter error",
            0x2002: "Protected",
            0x2003: "Table missing",
            0x2004: "Data missing",
            0x2005: "Program missing",
            0x2006: "File missing",
            0x2007: "Data mismatch",
        }
        error_msg = error_messages.get(error_code, f"Unknown error code: 0x{error_code:04X}")
        raise ValueError(f"FINS write error: {error_msg} (end code: {end_code.hex()})")


def parse_memory_read_response(raw: bytes, expected_count: int) -> list[int]:
    if len(raw) < 14:
        raise ValueError("Response too short")

    # Header (10) + MRC (1) + SRC (1) + End Code (2)
    end_code = raw[12:14]
    if end_code != b"\x00\x00":
        error_code = int.from_bytes(end_code, byteorder="big")
        error_messages = {
            0x0101: "Local node not in network",
            0x0102: "Token timeout",
            0x0103: "Retries failed",
            0x0104: "Too many send frames",
            0x0105: "Node address range error",
            0x0106: "Node address duplication",
            0x0201: "Destination node not in network",
            0x0202: "Unit missing",
            0x0203: "Third node missing",
            0x0204: "Destination node busy",
            0x0205: "Response timeout",
            0x0301: "Communications controller error",
            0x0302: "CPU Unit error",
            0x0303: "Controller error",
            0x0304: "Unit number error",
            0x0401: "Undefined command",
            0x0402: "Not supported by model/version",
            0x1001: "Command too long",
            0x1002: "Command too short",
            0x1003: "Elements/data don't match",
            0x1004: "Command format error",
            0x1005: "Header error",
            0x1101: "Area classification missing",
            0x1102: "Access size error",
            0x1103: "Address range error",
            0x1104: "Address range exceeded",
            0x1106: "Program missing",
            0x1109: "Relational error",
            0x110A: "Duplicate data access",
            0x110B: "Response too long",
            0x110C: "Parameter error",
            0x2002: "Protected",
            0x2003: "Table missing",
            0x2004: "Data missing",
            0x2005: "Program missing",
            0x2006: "File missing",
            0x2007: "Data mismatch",
            0x9005: "Address/area not available or access denied",
        }
        error_msg = error_messages.get(error_code, f"Unknown error code: 0x{error_code:04X}")
        raise ValueError(f"FINS error: {error_msg} (end code: {end_code.hex()})")

    data = raw[14:]
    if len(data) < expected_count * 2:
        raise ValueError("Not enough data words in response")

    values: list[int] = []
    for i in range(expected_count):
        word = data[i * 2 : i * 2 + 2]
        values.append(int.from_bytes(word, byteorder="big"))

    return values
