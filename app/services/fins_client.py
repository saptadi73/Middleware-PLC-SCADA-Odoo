from __future__ import annotations

import binascii
import socket
from dataclasses import dataclass


@dataclass
class FinsResponse:
    raw: bytes

    @property
    def hex(self) -> str:
        return binascii.hexlify(self.raw).decode("ascii")


class FinsUdpClient:
    def __init__(self, ip: str, port: int = 9600, timeout_sec: float = 2.0) -> None:
        self.ip = ip
        self.port = port
        self.timeout_sec = timeout_sec
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout_sec)
        self._sock = sock

    def close(self) -> None:
        if self._sock is None:
            return
        self._sock.close()
        self._sock = None

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def send_raw_hex(self, hex_str: str) -> None:
        if self._sock is None:
            raise RuntimeError("Socket not connected")
        payload = binascii.unhexlify(hex_str)
        self._sock.sendto(payload, (self.ip, self.port))

    def recv(self, max_bytes: int = 2048) -> FinsResponse:
        if self._sock is None:
            raise RuntimeError("Socket not connected")
        data, _ = self._sock.recvfrom(max_bytes)
        return FinsResponse(raw=data)

    def __enter__(self) -> "FinsUdpClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
