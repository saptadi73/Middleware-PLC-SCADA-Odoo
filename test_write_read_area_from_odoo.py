"""
Write PLC READ area from Odoo MO list.

Use this script to simulate PLC READ memory (D6001-D6076) without editing
app/reference/read_data_plc_input.csv manually.
Supports 15 equipment: 13 Silos (101-113) + 2 Liquid Tanks (114-115)
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import build_memory_write_frame, parse_memory_write_response
from app.services.odoo_auth_service import fetch_mo_list_detailed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_SILO_NUMBER_TO_LETTER = {
    101: "a",
    102: "b",
    103: "c",
    104: "d",
    105: "e",
    106: "f",
    107: "g",
    108: "h",
    109: "i",
    110: "j",
    111: "k",
    112: "l",
    113: "m",
}

_SILO_LETTER_TO_NUMBER = {letter: number for number, letter in _SILO_NUMBER_TO_LETTER.items()}
FORCED_STATUS_MANUFACTURING = 1
FORCED_STATUS_OPERATION = 0


class OdooReadAreaWriter:
    def __init__(self, write_retries: int = 2, retry_delay_sec: float = 0.2) -> None:
        self.settings = get_settings()
        self.write_retries = max(0, int(write_retries))
        self.retry_delay_sec = max(0.0, float(retry_delay_sec))
        mapping_path = (
            Path(__file__).parent / "app" / "reference" / "READ_DATA_PLC_MAPPING.json"
        )
        with mapping_path.open("r", encoding="utf-8") as handle:
            self.mapping = json.load(handle).get("raw_list", [])

    def _parse_dm_address(self, dm_str: str) -> tuple[int, int]:
        dm_str = dm_str.strip().upper().replace(" ", "")
        if "-" not in dm_str:
            match = re.match(r"D(\d+)", dm_str)
            if not match:
                raise ValueError(f"Invalid DM address format: {dm_str}")
            return (int(match.group(1)), 1)

        match = re.match(r"D(\d+)-(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM range format: {dm_str}")
        start = int(match.group(1))
        end = int(match.group(2))
        count = end - start + 1
        if count <= 0:
            raise ValueError(f"Invalid DM range: {dm_str}")
        return (start, count)

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _convert_to_words(
        self,
        value: Any,
        data_type: str,
        length: Optional[int],
        scale: Optional[float],
        word_count: int,
    ) -> List[int]:
        data_type = data_type.upper()

        if data_type == "BOOLEAN":
            return [1 if self._to_bool(value) else 0]

        if data_type == "ASCII":
            text_value = str(value) if value is not None else ""
            expected_words = int((length or len(text_value) + 1) / 2)
            padded = text_value.ljust(expected_words * 2, "\x00")
            words: List[int] = []
            for i in range(0, len(padded), 2):
                char1 = ord(padded[i]) if i < len(padded) else 0
                char2 = ord(padded[i + 1]) if i + 1 < len(padded) else 0
                words.append((char1 << 8) | char2)
            return words[:expected_words]

        if data_type == "REAL":
            scale_value = scale if scale else 1.0
            scaled_value = int(float(value or 0) * scale_value)
            if word_count >= 2:
                unsigned_value = scaled_value & 0xFFFFFFFF
                return [(unsigned_value >> 16) & 0xFFFF, unsigned_value & 0xFFFF]
            return [scaled_value & 0xFFFF]

        raise ValueError(f"Unsupported data type: {data_type}")

    def _write_words(self, address: int, words: List[int]) -> None:
        attempts = self.write_retries + 1
        last_exc: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                frame = build_memory_write_frame(
                    area="DM",
                    address=address,
                    values=words,
                    client_node=self.settings.client_node,
                    plc_node=self.settings.plc_node,
                    sid=0x00,
                )

                with FinsUdpClient(
                    ip=self.settings.plc_ip,
                    port=self.settings.plc_port,
                    timeout_sec=self.settings.plc_timeout_sec,
                ) as client:
                    client.send_raw_hex(frame.hex())
                    response = client.recv()

                parse_memory_write_response(response.raw)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    time.sleep(self.retry_delay_sec)
                else:
                    raise

        if last_exc:
            raise last_exc

    def write_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        results = {"success": 0, "failed": 0, "errors": []}

        for field_def in self.mapping:
            field_name = str(field_def.get("Informasi") or "").strip()
            if not field_name or field_name not in payload:
                continue

            dm_address = str(field_def.get("DM - Memory") or "").strip()
            data_type = str(field_def.get("Data Type") or "").strip()
            length = field_def.get("length")
            scale = field_def.get("scale")

            try:
                address, word_count = self._parse_dm_address(dm_address)
                words = self._convert_to_words(
                    payload[field_name],
                    data_type=data_type,
                    length=int(length) if length not in (None, "") else None,
                    scale=float(scale) if scale not in (None, "") else None,
                    word_count=word_count,
                )
                if len(words) < word_count:
                    words.extend([0] * (word_count - len(words)))
                elif len(words) > word_count:
                    words = words[:word_count]

                self._write_words(address, words)
                results["success"] += 1
            except Exception as exc:
                results["failed"] += 1
                err = f"{field_name}: {exc}"
                results["errors"].append(err)
                logger.error("Failed writing %s", err)

        return results


def _extract_silo_number(equipment: Optional[Dict[str, Any]]) -> Optional[int]:
    if not equipment:
        return None

    code = str(equipment.get("code") or "")
    name = str(equipment.get("name") or "")
    combined = f"{code} {name}".lower()

    match_3digits = re.search(r"(\d{3})", combined)
    if match_3digits:
        number = int(match_3digits.group(1))
        if number in _SILO_NUMBER_TO_LETTER:
            return number

    match_letter = re.search(r"\bsilo[_\s-]*([a-m])\b", combined)
    if match_letter:
        return _SILO_LETTER_TO_NUMBER.get(match_letter.group(1))

    return None


def _build_read_payload(
    mo_data: Dict[str, Any],
    weight_finished_good: float,
) -> Dict[str, Any]:
    mo_id = str(mo_data.get("mo_id") or "")
    finished_goods = str(mo_data.get("product_name") or mo_id)
    quantity = float(mo_data.get("quantity") or 0)

    payload: Dict[str, Any] = {
        "NO-MO": mo_id,
        "NO-BoM": finished_goods,
        "finished_goods": finished_goods,
        "Quantity Goods_id": quantity,
        # Force test status for READ area simulation.
        "status manufaturing": bool(FORCED_STATUS_MANUFACTURING),
        "Status Operation": bool(FORCED_STATUS_OPERATION),
        "weight_finished_good": float(weight_finished_good),
    }

    for silo_number in range(101, 114):
        silo_key = (
            f"SILO ID {silo_number} (SILO BESAR)"
            if silo_number in {101, 102, 103}
            else f"SILO ID {silo_number}"
        )
        payload[silo_key] = float(silo_number)
        payload[f"SILO ID {silo_number} Consumption"] = 0.0

    for component in mo_data.get("components_consumption", []):
        silo_number = _extract_silo_number(component.get("equipment"))
        if not silo_number:
            continue
        value = component.get("to_consume")
        if value is None:
            value = component.get("consumed")
        payload[f"SILO ID {silo_number} Consumption"] = float(value or 0)

    return payload


async def _fetch_mo_list(limit: int, offset: int) -> List[Dict[str, Any]]:
    response = await fetch_mo_list_detailed(limit=limit, offset=offset)
    return (response.get("result") or {}).get("data", []) or []


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write PLC READ area automatically from Odoo MO list"
    )
    parser.add_argument("--limit", type=int, default=10, help="MO fetch limit")
    parser.add_argument("--offset", type=int, default=0, help="MO fetch offset")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=5.0,
        help="Delay between MO writes when cycling list",
    )
    parser.add_argument(
        "--single-mo-id",
        type=str,
        default="",
        help="Write only this MO ID (exact match)",
    )
    parser.add_argument(
        "--weight-finished-good",
        type=float,
        default=0.0,
        help="Value for field 'weight_finished_good'",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continuously refetch Odoo list and keep writing",
    )
    parser.add_argument(
        "--write-retries",
        type=int,
        default=2,
        help="Retry count per PLC field write",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=0.2,
        help="Delay between write retries",
    )
    args = parser.parse_args()

    writer = OdooReadAreaWriter(
        write_retries=args.write_retries,
        retry_delay_sec=args.retry_delay_seconds,
    )

    while True:
        mo_list = await _fetch_mo_list(limit=args.limit, offset=args.offset)
        if args.single_mo_id:
            mo_list = [mo for mo in mo_list if str(mo.get("mo_id") or "") == args.single_mo_id]

        if not mo_list:
            logger.warning("No MO found from Odoo for given filter")
            if args.loop:
                await asyncio.sleep(max(args.interval_seconds, 1.0))
                continue
            return

        logger.info("Fetched %s MO from Odoo", len(mo_list))

        for index, mo_data in enumerate(mo_list, start=1):
            payload = _build_read_payload(
                mo_data=mo_data,
                weight_finished_good=args.weight_finished_good,
            )
            results = writer.write_payload(payload)
            logger.info(
                "[%s/%s] Wrote MO=%s to READ area | success=%s failed=%s",
                index,
                len(mo_list),
                payload.get("NO-MO"),
                results["success"],
                results["failed"],
            )
            if results["errors"]:
                for err in results["errors"]:
                    logger.error("  %s", err)

            if index < len(mo_list):
                await asyncio.sleep(max(args.interval_seconds, 0.0))

        if not args.loop:
            return
        await asyncio.sleep(max(args.interval_seconds, 1.0))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
