"""
PLC Read Service
Uses READ_DATA_PLC_MAPPING.json as PLC memory mapping reference.
"""
import json
import logging
import re
import socket
import time
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
    MAX_READ_ATTEMPTS = 3
    RETRY_DELAY_SEC = 0.1
    BATCH_WORD_COUNT = 77
    MAX_REASONABLE_CONSUMPTION = 100000.0
    MAX_REASONABLE_SILO_CONSUMPTION = 5000.0
    MAX_REASONABLE_QUANTITY = 10000000.0
    MAX_REASONABLE_WEIGHT = 10000000.0

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
                if 32 <= high <= 126:
                    chars.append(chr(high))
                if 32 <= low <= 126:
                    chars.append(chr(low))
            return "".join(chars).rstrip("\x00")

        raise ValueError(f"Unsupported data type: {data_type}")

    def _normalize_real_field_value(
        self,
        words: List[int],
        scale: Optional[float],
        field_name: str,
        decoded_value: Any,
    ) -> Any:
        """Normalize REAL field values for known PLC torn-read/word-order anomalies."""
        if len(words) < 2 or not isinstance(decoded_value, (int, float)):
            return decoded_value

        field_upper = field_name.upper()
        if (
            "CONSUMPTION" not in field_upper
            and "QUANTITY" not in field_upper
            and "WEIGHT" not in field_upper
        ):
            return decoded_value

        field_limit = self._get_real_field_limit(field_upper)

        scale_value = scale if scale not in (None, 0) else 1.0
        swapped_raw = (words[1] << 16) | words[0]
        swapped_value = float(swapped_raw) / float(scale_value)
        low_word_value = float(words[1] & 0xFFFF) / float(scale_value)
        high_word_value = float(words[0] & 0xFFFF) / float(scale_value)

        decoded_abs = abs(float(decoded_value))
        swapped_abs = abs(swapped_value)

        if decoded_abs <= field_limit:
            return decoded_value

        candidates = []
        if swapped_abs <= field_limit:
            candidates.append(("swapped", swapped_value))
        if 0 <= low_word_value <= field_limit:
            candidates.append(("low", low_word_value))
        if 0 <= high_word_value <= field_limit:
            candidates.append(("high", high_word_value))

        if candidates:
            selected_source, selected_value = max(candidates, key=lambda item: item[1])
            logger.warning(
                "Normalized REAL field '%s' using %s candidate (decoded=%s, selected=%s)",
                field_name,
                selected_source,
                decoded_value,
                selected_value,
            )
            return selected_value

        return decoded_value

    def _get_real_field_limit(self, field_upper: str) -> float:
        if "CONSUMPTION" in field_upper and ("SILO ID" in field_upper or "LQ ID" in field_upper):
            return self.MAX_REASONABLE_SILO_CONSUMPTION
        if "WEIGHT" in field_upper:
            return self.MAX_REASONABLE_WEIGHT
        if "QUANTITY" in field_upper:
            return self.MAX_REASONABLE_QUANTITY
        return self.MAX_REASONABLE_CONSUMPTION

    def _normalize_int_field_value(
        self,
        words: List[int],
        field_name: str,
        decoded_value: Any,
    ) -> Any:
        """Normalize INT fields for SILO/LQ IDs when PLC word noise appears."""
        if not words:
            return decoded_value

        field_upper = field_name.upper()
        match = re.search(r"(?:SILO\s+ID|LQ\s+ID)\s*(\d+)", field_upper)
        if not match:
            return decoded_value

        expected_id = int(match.group(1))
        candidate = (
            int(decoded_value)
            if isinstance(decoded_value, (int, float, bool))
            else int(words[0] & 0xFFFF)
        )

        if candidate == expected_id:
            return candidate

        unsigned = int(words[0] & 0xFFFF)
        if unsigned == expected_id:
            return unsigned

        if 1 <= candidate <= 1000:
            return candidate

        logger.warning(
            "Normalized INT ID field '%s' to expected ID %s (raw=%s, decoded=%s)",
            field_name,
            expected_id,
            unsigned,
            decoded_value,
        )
        return expected_id

    def _resolve_dm_string(self, field_def: Dict[str, Any]) -> str:
        dm_str = field_def.get("DM") or field_def.get("DM - Memory")
        if not isinstance(dm_str, str) or not dm_str.strip():
            raise ValueError(f"Missing DM address in field definition: {field_def}")
        return dm_str

    def _extract_mo_id_candidate(self, raw_text: Any) -> str:
        """Extract MO ID pattern from potentially garbled PLC ASCII text."""
        if not isinstance(raw_text, str):
            return ""

        cleaned = raw_text.upper()
        cleaned = re.sub(r"[^A-Z0-9/]+", "", cleaned)
        cleaned = cleaned.replace("HW/", "WH/")
        cleaned = cleaned.replace("/M/O", "/MO/")
        cleaned = cleaned.replace("M/O", "MO/")
        cleaned = re.sub(r"/{2,}", "/", cleaned)

        strict = re.search(r"([A-Z]{2})/MO/(\d{4,8})", cleaned)
        if strict:
            prefix = strict.group(1)
            digits = strict.group(2)
            return f"{prefix}/MO/{digits}"

        loose = re.search(r"([A-Z]{2})/?M/?O/?(\d{4,8})", cleaned)
        if loose:
            prefix = loose.group(1)
            digits = loose.group(2)
            return f"{prefix}/MO/{digits}"

        return ""

    def _extract_mo_id_from_batch_memory(self, batch_no: int) -> str:
        """Fallback: scan full batch read area and try recover MO ID pattern."""
        try:
            batch_no = self._validate_batch_no(batch_no)
            start_address = 6000 + ((batch_no - 1) * 100)
            words = self._read_from_plc(start_address, 77)

            chars_hl: List[str] = []
            chars_lh: List[str] = []

            for word in words:
                high = (word >> 8) & 0xFF
                low = word & 0xFF

                for byte in (high, low):
                    if byte in (0, 0x82):
                        continue
                    if 32 <= byte <= 126:
                        chars_hl.append(chr(byte))

                for byte in (low, high):
                    if byte in (0, 0x82):
                        continue
                    if 32 <= byte <= 126:
                        chars_lh.append(chr(byte))

            for candidate_text in (
                "".join(chars_hl),
                "".join(chars_lh),
            ):
                extracted = self._extract_mo_id_candidate(candidate_text)
                if extracted:
                    return extracted

        except Exception as exc:
            logger.debug(
                "MO_ID batch memory fallback failed for batch=%s: %s",
                batch_no,
                exc,
            )

        return ""

    def _read_from_plc(self, address: int, count: int) -> List[int]:
        """Low-level PLC read via FINS protocol."""
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_READ_ATTEMPTS + 1):
            try:
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
            except (TimeoutError, socket.timeout, ValueError) as exc:
                last_error = exc
                if attempt < self.MAX_READ_ATTEMPTS:
                    logger.warning(
                        "PLC read retry at D%s (attempt %s/%s): %s",
                        address,
                        attempt,
                        self.MAX_READ_ATTEMPTS,
                        exc,
                    )
                    time.sleep(self.RETRY_DELAY_SEC)
                    continue
                break

        raise RuntimeError(
            f"PLC read failed at D{address} after {self.MAX_READ_ATTEMPTS} attempts"
        ) from last_error

    def _get_batch_start_address(self, batch_no: int) -> int:
        batch_no = self._validate_batch_no(batch_no)
        return 6000 + ((batch_no - 1) * 100)

    def _read_batch_snapshot_words(self, batch_no: int) -> List[int]:
        """Read one batch memory block with consistency retry for ASCII fields."""
        start_address = self._get_batch_start_address(batch_no)
        max_snapshot_attempts = max(self.MAX_READ_ATTEMPTS, 4)
        best_words: List[int] = []
        best_score = -1

        previous_words: Optional[List[int]] = None
        for attempt in range(1, max_snapshot_attempts + 1):
            current_words = self._read_from_plc(start_address, self.BATCH_WORD_COUNT)
            current_score = self._score_batch_snapshot(current_words)

            if current_score > best_score:
                best_score = current_score
                best_words = current_words

            if self._is_strict_snapshot_valid(current_words):
                return current_words

            if previous_words is not None:
                current_slice = current_words[:25]
                previous_slice = previous_words[:25]
                if current_slice == previous_slice and current_score >= 2 and self._is_strict_snapshot_valid(current_words):
                    return current_words

            if current_score >= 3:
                if self._is_strict_snapshot_valid(current_words):
                    return current_words

            previous_words = current_words
            if attempt < max_snapshot_attempts:
                logger.debug(
                    "Low-quality batch snapshot for batch=%s (score=%s, attempt %s/%s). Retrying...",
                    batch_no,
                    current_score,
                    attempt,
                    max_snapshot_attempts,
                )
                time.sleep(self.RETRY_DELAY_SEC)

        return best_words if best_words else []

    def _read_batch_snapshot_with_quality(self, batch_no: int) -> tuple[List[int], int, bool]:
        """Read one batch snapshot with quality metadata."""
        snapshot_words = self._read_batch_snapshot_words(batch_no)
        if not snapshot_words:
            return ([], -1, False)

        score = self._score_batch_snapshot(snapshot_words)
        strict_valid = self._is_strict_snapshot_valid(snapshot_words)
        if not strict_valid:
            logger.warning(
                "Batch=%s snapshot best-effort only (score=%s).",
                batch_no,
                score,
            )
        return (snapshot_words, score, strict_valid)

    def _is_valid_product_text(self, raw_text: Any) -> bool:
        if not isinstance(raw_text, str):
            return False
        text = raw_text.strip().upper()
        if len(text) < 6:
            return False
        if any(token in text for token in ("HW/M/O", "PP", "0HW", "@@")):
            return False

        alnum = re.sub(r"[^A-Z0-9]", "", text)
        if len(alnum) < 5:
            return False

        letters = sum(1 for ch in alnum if ch.isalpha())
        digits = sum(1 for ch in alnum if ch.isdigit())
        return letters >= 2 and digits >= 2

    def _is_strict_snapshot_valid(self, words: List[int]) -> bool:
        if len(words) < 25:
            return False

        batch_raw = words[0] & 0xFFFF
        batch_swapped = ((batch_raw & 0x00FF) << 8) | ((batch_raw & 0xFF00) >> 8)
        batch_ok = (
            self.BATCH_MIN <= batch_raw <= self.BATCH_MAX
            or self.BATCH_MIN <= batch_swapped <= self.BATCH_MAX
        )
        if not batch_ok:
            return False

        no_mo = self._convert_from_words(words[1:9], "ASCII")
        mo_ok = bool(self._extract_mo_id_candidate(no_mo))
        if not mo_ok:
            return False

        no_bom = self._convert_from_words(words[9:17], "ASCII")
        finished_goods = self._convert_from_words(words[17:25], "ASCII")
        product_ok = self._is_valid_product_text(no_bom) or self._is_valid_product_text(finished_goods)
        if not product_ok:
            return False

        return True

    def _score_batch_snapshot(self, words: List[int]) -> int:
        """Heuristic score for snapshot quality (higher is better)."""
        if len(words) < 25:
            return -1

        score = 0
        batch_raw = words[0] & 0xFFFF
        batch_swapped = ((batch_raw & 0x00FF) << 8) | ((batch_raw & 0xFF00) >> 8)
        if self.BATCH_MIN <= batch_raw <= self.BATCH_MAX or self.BATCH_MIN <= batch_swapped <= self.BATCH_MAX:
            score += 1

        no_mo = self._convert_from_words(words[1:9], "ASCII")
        if self._extract_mo_id_candidate(no_mo):
            score += 2
        elif isinstance(no_mo, str) and len(no_mo.strip()) >= 6:
            score += 1

        no_bom = self._convert_from_words(words[9:17], "ASCII")
        if isinstance(no_bom, str) and len(no_bom.strip()) >= 4:
            score += 1

        finished_goods = self._convert_from_words(words[17:25], "ASCII")
        if isinstance(finished_goods, str) and len(finished_goods.strip()) >= 4:
            score += 1

        try:
            silo_101 = self._convert_from_words(words[28:30], "REAL", 100)
            silo_101 = self._normalize_real_field_value(
                words[28:30],
                100,
                "SILO ID 101 Consumption",
                silo_101,
            )
            if 0 <= float(silo_101) <= self.MAX_REASONABLE_SILO_CONSUMPTION:
                score += 1
            else:
                score -= 1
        except Exception:
            score -= 1

        try:
            silo_102 = self._convert_from_words(words[31:33], "REAL", 100)
            silo_102 = self._normalize_real_field_value(
                words[31:33],
                100,
                "SILO ID 102 Consumption",
                silo_102,
            )
            if 0 <= float(silo_102) <= self.MAX_REASONABLE_SILO_CONSUMPTION:
                score += 1
            else:
                score -= 1
        except Exception:
            score -= 1

        return score

    def _decode_field_from_snapshot(
        self,
        words: List[int],
        field_def: Dict[str, Any],
        batch_no: int,
    ) -> Any:
        field_name = str(field_def.get("Informasi") or "")
        dm_str = self._resolve_dm_string(field_def)
        address, word_count = self._parse_dm_address(dm_str)

        start_address = self._get_batch_start_address(batch_no)
        start_index = address - start_address
        end_index = start_index + word_count
        if start_index < 0 or end_index > len(words):
            raise ValueError(
                f"Field '{field_name}' DM={dm_str} out of snapshot range for batch {batch_no}"
            )

        slice_words = words[start_index:end_index]
        data_type = str(field_def.get("Data Type", ""))
        scale = field_def.get("scale")
        value = self._convert_from_words(slice_words, data_type, scale)
        if data_type.upper() == "INT" and field_name != "BATCH":
            value = self._normalize_int_field_value(slice_words, field_name, value)
        if data_type.upper() == "REAL":
            value = self._normalize_real_field_value(
                slice_words,
                scale,
                field_name,
                value,
            )

        if field_name == "BATCH" and slice_words:
            raw_word = int(slice_words[0]) & 0xFFFF
            batch_candidate = int(value) if isinstance(value, (int, float, bool)) else raw_word
            if batch_candidate < self.BATCH_MIN or batch_candidate > self.BATCH_MAX:
                swapped = ((raw_word & 0x00FF) << 8) | ((raw_word & 0xFF00) >> 8)
                if self.BATCH_MIN <= swapped <= self.BATCH_MAX:
                    value = swapped
                elif self.BATCH_MIN <= raw_word <= self.BATCH_MAX:
                    value = raw_word
                else:
                    value = batch_no

        if data_type.upper() == "ASCII" and field_name == "NO-MO":
            extracted = self._extract_mo_id_candidate(value)
            if extracted:
                value = extracted

        return value

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
        if data_type.upper() == "INT" and field_name != "BATCH":
            value = self._normalize_int_field_value(words, field_name, value)
        if data_type.upper() == "REAL":
            value = self._normalize_real_field_value(
                words,
                scale,
                field_name,
                value,
            )

        if field_name == "BATCH" and words:
            raw_word = int(words[0]) & 0xFFFF
            batch_candidate = int(value) if isinstance(value, (int, float, bool)) else raw_word
            if batch_candidate < self.BATCH_MIN or batch_candidate > self.BATCH_MAX:
                swapped = ((raw_word & 0x00FF) << 8) | ((raw_word & 0xFF00) >> 8)
                if self.BATCH_MIN <= swapped <= self.BATCH_MAX:
                    value = swapped
                elif self.BATCH_MIN <= raw_word <= self.BATCH_MAX:
                    value = raw_word
                else:
                    value = batch_no

        if data_type.upper() == "ASCII" and field_name == "NO-MO":
            normalized_value = value.strip() if isinstance(value, str) else ""
            if not normalized_value:
                for retry_attempt in range(1, self.MAX_READ_ATTEMPTS):
                    logger.warning(
                        "NO-MO empty at batch=%s D%s. Retrying ASCII read (%s/%s)",
                        batch_no,
                        address,
                        retry_attempt,
                        self.MAX_READ_ATTEMPTS - 1,
                    )
                    time.sleep(self.RETRY_DELAY_SEC)
                    retry_words = self._read_from_plc(address, word_count)
                    retry_value = self._convert_from_words(retry_words, data_type, scale)
                    normalized_retry = (
                        retry_value.strip() if isinstance(retry_value, str) else ""
                    )
                    if normalized_retry:
                        words = retry_words
                        value = retry_value
                        break

            extracted = self._extract_mo_id_candidate(value)
            if not extracted:
                extracted = self._extract_mo_id_from_batch_memory(batch_no)
            if extracted:
                value = extracted

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
        all_fields, _, _ = self._read_all_fields_with_quality(batch_no=batch_no)
        return all_fields

    def _read_all_fields_with_quality(self, batch_no: int = 1) -> tuple[Dict[str, Any], int, bool]:
        """Read all fields plus snapshot quality metadata."""
        mapping = self._get_batch_mapping(batch_no)
        result: Dict[str, Any] = {}
        snapshot_words, snapshot_score, strict_valid = self._read_batch_snapshot_with_quality(batch_no)

        if not snapshot_words:
            return (result, -1, False)

        for field_def in mapping:
            field_name = field_def.get("Informasi")
            if not field_name:
                continue
            try:
                result[field_name] = self._decode_field_from_snapshot(
                    snapshot_words,
                    field_def,
                    batch_no,
                )
            except Exception as exc:
                logger.error(
                    "Error reading field '%s' for batch %s: %s",
                    field_name,
                    batch_no,
                    exc,
                )
                result[str(field_name)] = None

        return (result, snapshot_score, strict_valid)

    def read_batch_data(self, batch_no: int = 1) -> Dict[str, Any]:
        """Read and format one batch payload from PLC."""
        all_fields, snapshot_score, strict_valid = self._read_all_fields_with_quality(batch_no=batch_no)

        parsed_batch_no = all_fields.get("BATCH", batch_no)
        try:
            parsed_batch_no = int(parsed_batch_no) if parsed_batch_no is not None else batch_no
        except (TypeError, ValueError):
            parsed_batch_no = batch_no

        if parsed_batch_no < self.BATCH_MIN or parsed_batch_no > self.BATCH_MAX:
            logger.warning(
                "Invalid BATCH value from PLC for batch_no=%s: %s. Using fallback batch_no.",
                batch_no,
                parsed_batch_no,
            )
            parsed_batch_no = batch_no

        batch_data: Dict[str, Any] = {
            "batch_no": parsed_batch_no,
            "mo_id": all_fields.get("NO-MO", ""),
            "product_name": all_fields.get("finished_goods", ""),
            "bom_name": all_fields.get("NO-BoM", ""),
            "quantity": all_fields.get("Quantity Goods_id", 0),
            "quality": {
                "snapshot_score": snapshot_score,
                "strict_valid": strict_valid,
            },
            "silos": {},
            "status": {
                "manufacturing": all_fields.get("status manufaturing", False),
                "operation": all_fields.get("Status Operation", False),
                "read": all_fields.get("status_read_data", False),
            },
            "weight_finished_good": all_fields.get("weight_finished_good", 0),
        }

        mo_id_candidate = self._extract_mo_id_candidate(batch_data.get("mo_id", ""))
        if not mo_id_candidate:
            fallback_sources = [
                all_fields.get("NO-BoM", ""),
                all_fields.get("finished_goods", ""),
                " ".join(
                    [
                        str(all_fields.get("NO-MO", "") or ""),
                        str(all_fields.get("NO-BoM", "") or ""),
                        str(all_fields.get("finished_goods", "") or ""),
                    ]
                ),
            ]
            for source in fallback_sources:
                mo_id_candidate = self._extract_mo_id_candidate(source)
                if mo_id_candidate:
                    logger.warning(
                        "Recovered MO_ID from fallback ASCII source for batch %s: %s",
                        batch_no,
                        mo_id_candidate,
                    )
                    break

        if mo_id_candidate:
            batch_data["mo_id"] = mo_id_candidate

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
