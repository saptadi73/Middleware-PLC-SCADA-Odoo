#!/usr/bin/env python3
"""
FINS UDP diagnostic helper.

Tujuan:
- Mencoba beberapa kombinasi CLIENT_NODE, PLC_NODE, DA2 (unit), dan mode bind socket.
- Membantu isolasi kenapa PLC ping reply tapi FINS UDP timeout.

Catatan:
- Script ini read-only (memory area read).
- Tidak menulis ke PLC/Odoo/database.
"""

from __future__ import annotations

import argparse
import socket
from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.core.config import get_settings
from app.services.fins_frames import MemoryReadRequest, build_memory_read_command


@dataclass
class ProbeResult:
    bind_mode: str
    client_node: int
    plc_node: int
    da2: int
    ok: bool
    detail: str


def _parse_csv_int(value: str) -> List[int]:
    values: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    return values


def _dedup(items: Iterable[int]) -> List[int]:
    seen = set()
    out: List[int] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _local_ip_for_target(target_ip: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((target_ip, 9600))
        return str(sock.getsockname()[0])
    finally:
        sock.close()


def _build_frame(address: int, count: int, client_node: int, plc_node: int, da2: int, sid: int) -> bytes:
    req = MemoryReadRequest(area="DM", address=address, count=count)
    command = build_memory_read_command(req)

    # FINS header (10 bytes)
    # ICF RSV GCT DNA DA1 DA2 SNA SA1 SA2 SID
    header = bytes([
        0x80,
        0x00,
        0x02,
        0x00,
        plc_node & 0xFF,
        da2 & 0xFF,
        0x00,
        client_node & 0xFF,
        0x00,
        sid & 0xFF,
    ])
    return header + command


def _probe_once(
    target_ip: str,
    target_port: int,
    timeout: float,
    frame: bytes,
    bind_mode: str,
    local_ip: str,
) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        if bind_mode == "bind_ip":
            sock.bind((local_ip, 0))
        elif bind_mode == "bind_ip_port":
            sock.bind((local_ip, 9600))

        sock.sendto(frame, (target_ip, target_port))
        raw, addr = sock.recvfrom(2048)

        if len(raw) < 14:
            return True, f"response-too-short len={len(raw)} from={addr}"

        end_code = raw[12:14].hex()
        return True, f"response len={len(raw)} end_code=0x{end_code} from={addr}"
    except socket.timeout:
        return False, "timeout"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"
    finally:
        sock.close()


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="FINS UDP diagnostic matrix (read-only)")
    parser.add_argument("--target-ip", default=settings.plc_ip, help="PLC IP target")
    parser.add_argument("--target-port", type=int, default=settings.plc_port, help="PLC UDP port")
    parser.add_argument("--address", type=int, default=6001, help="DM address to read")
    parser.add_argument("--count", type=int, default=1, help="Word count to read")
    parser.add_argument("--timeout", type=float, default=2.0, help="Timeout per probe (seconds)")
    parser.add_argument(
        "--client-nodes",
        default="",
        help="Comma separated client nodes, example: 1,5,99",
    )
    parser.add_argument(
        "--plc-nodes",
        default="",
        help="Comma separated PLC nodes, example: 2,1",
    )
    parser.add_argument(
        "--da2-values",
        default="0,1",
        help="Comma separated DA2 values, example: 0,1,2",
    )
    parser.add_argument(
        "--bind-modes",
        default="auto,bind_ip,bind_ip_port",
        help="Comma separated bind modes: auto,bind_ip,bind_ip_port",
    )
    parser.add_argument(
        "--local-ip",
        default="",
        help="Override local source IP for bind modes (default auto-detect by route)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    local_ip = args.local_ip.strip() or _local_ip_for_target(args.target_ip)
    local_last_octet = int(local_ip.split(".")[-1])

    client_nodes = _parse_csv_int(args.client_nodes) if args.client_nodes.strip() else [
        get_settings().client_node,
        local_last_octet,
        1,
        5,
        99,
    ]
    plc_nodes = _parse_csv_int(args.plc_nodes) if args.plc_nodes.strip() else [get_settings().plc_node, 2, 1]
    da2_values = _parse_csv_int(args.da2_values)
    bind_modes = [item.strip() for item in args.bind_modes.split(",") if item.strip()]

    client_nodes = _dedup(client_nodes)
    plc_nodes = _dedup(plc_nodes)

    print("=" * 90)
    print("FINS UDP DIAGNOSTIC MATRIX")
    print("=" * 90)
    print(f"Target      : {args.target_ip}:{args.target_port}")
    print(f"Local IP    : {local_ip}")
    print(f"Address     : D{args.address} x {args.count} word")
    print(f"Timeout     : {args.timeout}s")
    print(f"Bind modes  : {bind_modes}")
    print(f"Client nodes: {client_nodes}")
    print(f"PLC nodes   : {plc_nodes}")
    print(f"DA2 values  : {da2_values}")

    results: List[ProbeResult] = []
    sid = 0

    for bind_mode in bind_modes:
        for client_node in client_nodes:
            for plc_node in plc_nodes:
                for da2 in da2_values:
                    sid = (sid + 1) & 0xFF
                    frame = _build_frame(
                        address=args.address,
                        count=args.count,
                        client_node=client_node,
                        plc_node=plc_node,
                        da2=da2,
                        sid=sid,
                    )
                    ok, detail = _probe_once(
                        target_ip=args.target_ip,
                        target_port=args.target_port,
                        timeout=args.timeout,
                        frame=frame,
                        bind_mode=bind_mode,
                        local_ip=local_ip,
                    )
                    results.append(
                        ProbeResult(
                            bind_mode=bind_mode,
                            client_node=client_node,
                            plc_node=plc_node,
                            da2=da2,
                            ok=ok,
                            detail=detail,
                        )
                    )
                    status = "OK" if ok else "FAIL"
                    print(
                        f"[{status:4}] bind={bind_mode:12} client={client_node:3} "
                        f"plc={plc_node:3} da2={da2:2} -> {detail}"
                    )

    success = [item for item in results if item.ok]

    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)
    print(f"Total probes : {len(results)}")
    print(f"Success count: {len(success)}")

    if success:
        print("\nSuccessful combinations:")
        for item in success:
            print(
                f"- bind={item.bind_mode} client={item.client_node} "
                f"plc={item.plc_node} da2={item.da2} ({item.detail})"
            )
        return 0

    print("\nNo response for all combinations.")
    print("Kemungkinan besar issue ada di PLC FINS setting atau filter UDP di jaringan/PLC.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
