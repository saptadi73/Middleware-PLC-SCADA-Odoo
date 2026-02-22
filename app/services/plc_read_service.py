"""
PLC Read Service
Uses READ_DATA_PLC_MAPPING.json as PLC memory mapping reference.
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)

logger = logging.getLogger(__name__)


class PLCReadService:
    """Service for reading data from PLC using FINS protocol."""

    BATCH_MIN = 1
    BATCH_MAX = 10

    def __init__(self):
        self.settings = get_settings()
        # Keep this for backward compatibility (default points to BATCH_READ_01 mapping).
        self.mapping: List[Dict[str, Any]] = []
        self.batch_mappings: Dict[int, List[Dict[str, Any]]] = {}
        self._load_reference()

    def _load_reference(self):
        """Load READ_DATA_PLC_MAPPING.json (BATCH_READ_01..BATCH_READ_10)."""
        reference_path = (
            Path(__file__).parent.parent
            / "reference"
            / "READ_DATA_PLC_MAPPING.json"
        )

        if not reference_path.exists():
            logger.warning("READ_DATA_PLC_MAPPING.json not found at %s", reference_path)
            return

        with open(reference_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.batch_mappings = {}
        for batch_no in range(self.BATCH_MIN, self.BATCH_MAX + 1):
            key = f"BATCH_READ_{batch_no:02d}"
            fields = data.get(key, [])
            if isinstance(fields, list):
                self.batch_mappings[batch_no] = fields
            else:
                self.batch_mappings[batch_no] = []

        self.mapping = self.batch_mappings.get(1, [])
        logger.info(
            "Loaded PLC read mapping: batches=%s, fields_per_batch=%s",
            len(self.batch_mappings),
            len(self.mapping),
        )

    def _validate_batch_no(self, batch_no: int) -> int:
        if batch_no < self.BATCH_MIN or batch_no > self.BATCH_MAX:
            raise ValueError(
                f"batch_no must be {self.BATCH_MIN}..{self.BATCH_MAX}, got {batch_no}"
            )
        return batch_no

    def _get_batch_mapping(self, batch_no: int) -> List[Dict[str, Any]]:
        batch_no = self._validate_batch_no(batch_no)
        mapping = self.batch_mappings.get(batch_no, [])
        if not mapping:
            raise ValueError(f"Mapping for batch_no={batch_no} is empty or missing")
        return mapping

    def _parse_dm_address(self, dm_str: str) -> tuple[int, int]:
        """Parse DM address string into (start_address, word_count)."""
        dm_str = dm_str.strip().upper().replace(" ", "")

        if "-" not in dm_str:
            match = re.match(r"D(\d+)", dm_str)
            if not match:
                raise ValueError(f"Invalid DM address format: {dm_str}")
            address = int(match.group(1))
            return (address, 1)

        match = re.match(r"D(\d+)-D?(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM range format: {dm_str}")

        start = int(match.group(1))
        end = int(match.group(2))
        count = end - start + 1
        if count <= 0:
            raise ValueError(f"Invalid DM range: {dm_str} (count={count})")

        return (start, count)

    def _convert_from_words(
        self,
        words: List[int],
        data_type: str,
        scale: Optional[float] = None,
    ) -> Any:
        """Convert PLC word values into Python value."""
        data_type = data_type.upper()

        if data_type == "BOOLEAN":
            return bool(words[0]) if words else False

        if data_type == "INT":
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

        if data_type == "REAL":
            if not words:
                return 0.0
            if len(words) >= 2:
                raw_value = (words[0] << 16) | words[1]
            else:
                raw_value = words[0]
            scale = scale if scale else 1.0
            return float(raw_value) / scale

        if data_type == "ASCII":
            chars = []
            for word in words:
                high = (word >> 8) & 0xFF
                low = word & 0xFF
                if high != 0:
                    chars.append(chr(high))
                if low != 0:
                    chars.append(chr(low))
            return "".join(chars).rstrip("\x00")

        raise ValueError(f"Unsupported data type: {data_type}")

    def _resolve_dm_string(self, field_def: Dict[str, Any]) -> str:
        dm_str = field_def.get("DM") or field_def.get("DM - Memory")
        if not isinstance(dm_str, str) or not dm_str.strip():
            raise ValueError(f"Missing DM address in field definition: {field_def}")
        return dm_str

    def _read_from_plc(self, address: int, count: int) -> List[int]:
        """Low-level PLC read via FINS protocol."""
        with FinsUdpClient(
            ip=self.settings.plc_ip,
            port=self.settings.plc_port,
            timeout_sec=self.settings.plc_timeout_sec,
        ) as client:
            req = MemoryReadRequest(area="DM", address=address, count=count)
            frame = build_memory_read_frame(
                req=req,
                client_node=self.settings.client_node,
                plc_node=self.settings.plc_node,
                sid=0x00,
            )
            client.send_raw_hex(frame.hex())
            response = client.recv()
            return parse_memory_read_response(response.raw, expected_count=count)

    def read_field(self, field_name: str, batch_no: int = 1) -> Any:
        """Read one field from a specific READ batch area."""
        mapping = self._get_batch_mapping(batch_no)

        field_def: Optional[Dict[str, Any]] = None
        for item in mapping:
            if item.get("Informasi") == field_name:
                field_def = item
                break

        if not field_def:
            raise ValueError(
                f"Field '{field_name}' not found in mapping for batch_no={batch_no}"
            )

        dm_str = self._resolve_dm_string(field_def)
        address, word_count = self._parse_dm_address(dm_str)
        words = self._read_from_plc(address, word_count)

        data_type = str(field_def.get("Data Type", ""))
        scale = field_def.get("scale")
        value = self._convert_from_words(words, data_type, scale)

        logger.debug(
            "Read batch=%s field=%s DM=%s words=%s value=%s",
            batch_no,
            field_name,
            dm_str,
            words,
            value,
        )
        return value

    def read_all_fields(self, batch_no: int = 1) -> Dict[str, Any]:
        """Read all fields for one batch."""
        mapping = self._get_batch_mapping(batch_no)
        result: Dict[str, Any] = {}

        for field_def in mapping:
            field_name = field_def.get("Informasi")
            if not field_name:
                continue
            try:
                result[field_name] = self.read_field(str(field_name), batch_no=batch_no)
            except Exception as exc:
                logger.error(
                    "Error reading field '%s' for batch %s: %s",
                    field_name,
                    batch_no,
                    exc,
                )
                result[str(field_name)] = None

        return result

    def read_batch_data(self, batch_no: int = 1) -> Dict[str, Any]:
        """Read and format one batch payload from PLC."""
        all_fields = self.read_all_fields(batch_no=batch_no)

        parsed_batch_no = all_fields.get("BATCH", batch_no)
        try:
            parsed_batch_no = int(parsed_batch_no) if parsed_batch_no is not None else batch_no
        except (TypeError, ValueError):
            parsed_batch_no = batch_no

        batch_data: Dict[str, Any] = {
            "batch_no": parsed_batch_no,
            "mo_id": all_fields.get("NO-MO", ""),
            "product_name": all_fields.get("finished_goods", ""),
            "bom_name": all_fields.get("NO-BoM", ""),
            "quantity": all_fields.get("Quantity Goods_id", 0),
            "silos": {},
            "status": {
                "manufacturing": all_fields.get("status manufaturing", False),
                "operation": all_fields.get("Status Operation", False),
                "read": all_fields.get("status_read_data", False),
            },
            "weight_finished_good": all_fields.get("weight_finished_good", 0),
        }

        silo_mapping = {
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

        for silo_num, letter in silo_mapping.items():
            id_key = f"SILO ID {silo_num}" if silo_num >= 104 else f"SILO ID {silo_num} (SILO BESAR)"
            consumption_key = f"SILO ID {silo_num} Consumption"
            batch_data["silos"][letter] = {
                "id": all_fields.get(id_key, silo_num),
                "consumption": all_fields.get(consumption_key, 0),
            }

        # Liquid tanks
        batch_data["liquids"] = {
            "lq114": {
                "id": all_fields.get("LQ ID 114", 114),
                "consumption": all_fields.get("LQ ID 114 Consumption", 0),
            },
            "lq115": {
                "id": all_fields.get("LQ ID 115", 115),
                "consumption": all_fields.get("LQ ID 115 Consumption", 0),
            },
        }

        return batch_data

    def read_all_batches_data(self) -> Dict[int, Dict[str, Any]]:
        """Read and format all batch payloads (1..10)."""
        result: Dict[int, Dict[str, Any]] = {}
        for batch_no in range(self.BATCH_MIN, self.BATCH_MAX + 1):
            result[batch_no] = self.read_batch_data(batch_no=batch_no)
        return result


_plc_read_service: Optional[PLCReadService] = None


def get_plc_read_service() -> PLCReadService:
    """Get singleton instance of PLCReadService."""
    global _plc_read_service
    if _plc_read_service is None:
        _plc_read_service = PLCReadService()
    return _plc_read_service
