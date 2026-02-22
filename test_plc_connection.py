#!/usr/bin/env python3
"""
Test koneksi PLC via FINS UDP (read-only).

Default behavior:
- Connect ke PLC berdasarkan .env (PLC_IP, PLC_PORT, PLC_TIMEOUT_SEC, CLIENT_NODE, PLC_NODE)
- Read 1 word dari DM address 6001
- Menampilkan raw response + nilai words
"""

import argparse
import socket
from typing import List

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PLC connection test (FINS UDP, read-only)")
    parser.add_argument("--address", type=int, default=6001, help="DM address to read (default: 6001)")
    parser.add_argument("--count", type=int, default=1, help="Number of words to read (default: 1)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Override timeout (seconds). Default uses PLC_TIMEOUT_SEC from .env",
    )
    parser.add_argument(
        "--client-node",
        type=int,
        default=None,
        help="Override CLIENT_NODE from .env",
    )
    parser.add_argument(
        "--plc-node",
        type=int,
        default=None,
        help="Override PLC_NODE from .env",
    )
    return parser.parse_args()


def _print_words(words: List[int]) -> None:
    print("\nRead result words:")
    for index, word in enumerate(words):
        print(f"  word[{index}] = {word} (0x{word:04X})")


def main() -> int:
    args = _parse_args()
    settings = get_settings()

    timeout = args.timeout if args.timeout is not None else settings.plc_timeout_sec
    client_node = args.client_node if args.client_node is not None else settings.client_node
    plc_node = args.plc_node if args.plc_node is not None else settings.plc_node

    print("=" * 80)
    print("PLC CONNECTION TEST (FINS UDP - READ ONLY)")
    print("=" * 80)
    print(f"PLC IP      : {settings.plc_ip}")
    print(f"PLC PORT    : {settings.plc_port}")
    print(f"TIMEOUT     : {timeout}s")
    print(f"CLIENT NODE : {client_node}")
    print(f"PLC NODE    : {plc_node}")
    print(f"READ DM     : D{args.address}")
    print(f"WORD COUNT  : {args.count}")

    request = MemoryReadRequest(area="DM", address=args.address, count=args.count)
    frame = build_memory_read_frame(
        req=request,
        client_node=client_node,
        plc_node=plc_node,
        sid=0x00,
    )

    try:
        with FinsUdpClient(
            ip=settings.plc_ip,
            port=settings.plc_port,
            timeout_sec=timeout,
        ) as client:
            client.send_raw_hex(frame.hex())
            response = client.recv(max_bytes=2048)

        print("\nRaw response hex:")
        print(response.hex)

        words = parse_memory_read_response(response.raw, expected_count=args.count)
        _print_words(words)

        print("\n✅ SUCCESS: PLC reachable and memory read succeeded.")
        return 0

    except socket.timeout:
        print("\n❌ FAILED: Timeout waiting response from PLC.")
        print("Check PLC IP/PORT, network path, firewall, and node settings.")
        return 1
    except Exception as error:
        print("\n❌ FAILED: PLC test error.")
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
