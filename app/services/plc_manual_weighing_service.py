"""
PLC Manual Weighing Service
Membaca data penimbangan material manual dari PLC menggunakan MANUAL_REFERENCE.json.
Includes handshake logic dan sync ke Odoo material consumption API.
"""
import json
import hashlib
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.manual_weighing_sync import ManualWeighingSync
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)
from app.services.plc_handshake_service import get_handshake_service
from sqlalchemy import select

logger = logging.getLogger(__name__)


class PLCManualWeighingService:
    """
    Service untuk read data manual material weighing dari PLC menggunakan FINS protocol.
    Memory area: D9000-D9011 (TASK 5)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._manual_reference_key = str(
            getattr(self.settings, "manual_weighing_reference_key", "ALL")
        ).strip().upper()
        self.mapping: List[Dict[str, Any]] = []
        self.layouts: List[Dict[str, Any]] = []
        self.mapping_structure: Dict[str, Any] = {}
        self._field_by_info: Dict[str, Dict[str, Any]] = {}
        self._manual_start_addr = 9000
        self._manual_word_count = 14
        self._batch_slice = (0, 1)
        self._mo_slice = (1, 9)
        self._product_slice = (9, 11)
        self._consumption_slice = (11, 13)
        self._handshake_index = 13
        self._batch_type = "INT"
        self._batch_scale = 1
        self._product_type = "REAL"
        self._product_scale = 1
        self._consumption_type = "REAL"
        self._consumption_scale = 100
        self.reference_status: Dict[str, Any] = {}
        self._load_reference()
        self.base_url = self.settings.odoo_base_url
        self.handshake_service = get_handshake_service()

    def _reset_reference_state(self) -> None:
        self.mapping = []
        self.layouts = []
        self.mapping_structure = {}
        self.reference_status = {
            "requested_key": self._manual_reference_key,
            "active_source": None,
            "active_format": None,
            "legacy_fallback_used": False,
            "reference_path": None,
            "loaded_keys": [],
            "layout_count": 0,
            "error": None,
        }

    def _finalize_reference_status(self) -> None:
        self.reference_status["loaded_keys"] = [
            str(layout.get("reference_key"))
            for layout in self.layouts
            if layout.get("reference_key") is not None
        ]
        self.reference_status["layout_count"] = len(self.layouts)

    def _load_reference(self):
        """Load MANUAL_REFERENCE.json dan build layout untuk semua slot manual weighing."""
        self._reset_reference_state()
        reference_dir = Path(__file__).parent.parent / "reference"
        manual_reference_path = reference_dir / "MANUAL_REFERENCE.json"
        self.reference_status["reference_path"] = str(manual_reference_path)

        try:
            if manual_reference_path.exists():
                with open(manual_reference_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # New structure: MANUAL_WEIGHING with shared header + multiple item slots
                manual_weighing = data.get("MANUAL_WEIGHING")
                if isinstance(manual_weighing, dict):
                    self.layouts = self._build_layouts_from_manual_weighing(manual_weighing)
                    if self.layouts:
                        self.mapping = list(self.layouts[0].get("fields", []))
                        self.mapping_structure = {
                            "source": "MANUAL_REFERENCE",
                            "key": self._manual_reference_key,
                            "loaded_keys": [layout.get("reference_key") for layout in self.layouts],
                            "format": "MANUAL_WEIGHING",
                        }
                        self.reference_status["active_source"] = "MANUAL_REFERENCE"
                        self.reference_status["active_format"] = "MANUAL_WEIGHING"
                        self._finalize_reference_status()
                        logger.info(
                            "Loaded PLC manual weighing layouts from MANUAL_REFERENCE.json (MANUAL_WEIGHING): mode=%s loaded=%s",
                            self._manual_reference_key,
                            ",".join(str(layout.get("reference_key")) for layout in self.layouts),
                        )
                        return

                manual_keys = sorted(
                    key for key in data.keys() if re.fullmatch(r"MANUAL\d{2}", str(key).upper())
                )

                selected_keys: List[str]
                if self._manual_reference_key == "ALL":
                    selected_keys = manual_keys
                elif self._manual_reference_key in manual_keys:
                    selected_keys = [self._manual_reference_key]
                else:
                    selected_keys = []

                self.layouts = []
                for key in selected_keys:
                    fields = data.get(key)
                    if not isinstance(fields, list) or not fields:
                        continue
                    layout = self._build_layout_from_fields(fields, key)
                    if layout is not None:
                        self.layouts.append(layout)

                if self.layouts:
                    self.mapping = list(self.layouts[0].get("fields", []))
                    self.mapping_structure = {
                        "source": "MANUAL_REFERENCE",
                        "key": self._manual_reference_key,
                        "loaded_keys": [layout.get("reference_key") for layout in self.layouts],
                    }
                    self.reference_status["active_source"] = "MANUAL_REFERENCE"
                    self.reference_status["active_format"] = "LEGACY_MANUAL_KEYS"
                    self._finalize_reference_status()
                    logger.info(
                        "Loaded PLC manual weighing layouts from MANUAL_REFERENCE.json: mode=%s loaded=%s",
                        self._manual_reference_key,
                        ",".join(str(layout.get("reference_key")) for layout in self.layouts),
                    )
                    return

                error_message = (
                    f"MANUAL_REFERENCE.json exists but no valid layout for mode "
                    f"{self._manual_reference_key}. Legacy fallback is blocked; fix the manual reference file."
                )
                self.reference_status["error"] = error_message
                self._finalize_reference_status()
                logger.error(error_message)
                return

            logger.warning(
                "MANUAL_REFERENCE.json not found at %s. Falling back to legacy reference.",
                manual_reference_path,
            )

            legacy_path = reference_dir / "ADDITIONAL_EQUIPMENT_REFERENCE.json"
            self.reference_status["reference_path"] = str(legacy_path)
            if not legacy_path.exists():
                error_message = (
                    f"ADDITIONAL_EQUIPMENT_REFERENCE.json not found at {legacy_path}"
                )
                self.reference_status["error"] = error_message
                self._finalize_reference_status()
                logger.warning(error_message)
                return

            with open(legacy_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.mapping = data.get("ADDITIONAL", [])
                self.mapping_structure = data.get("mapping_structure", {})

            legacy_layout = self._build_layout_from_fields(self.mapping, "LEGACY")
            self.layouts = [legacy_layout] if legacy_layout is not None else []

            if self.layouts:
                self._apply_layout(self.layouts[0])
                self.reference_status["active_source"] = "ADDITIONAL_EQUIPMENT_REFERENCE"
                self.reference_status["active_format"] = "LEGACY_ADDITIONAL"
                self.reference_status["legacy_fallback_used"] = True
                self._finalize_reference_status()
            else:
                self.reference_status["legacy_fallback_used"] = True
                self.reference_status["error"] = (
                    "Legacy manual weighing reference loaded but produced no valid layout"
                )
                self._finalize_reference_status()

            logger.info(
                "Loaded PLC manual weighing mapping from ADDITIONAL_EQUIPMENT_REFERENCE.json: fields=%s layouts=%s",
                len(self.mapping),
                len(self.layouts),
            )
        except Exception as e:
            self.reference_status["error"] = str(e)
            self._finalize_reference_status()
            logger.error(f"Error loading manual weighing reference: {e}")

    def reload_reference(self) -> Dict[str, Any]:
        self._load_reference()
        return self.get_reference_status()

    def get_reference_status(self) -> Dict[str, Any]:
        status = dict(self.reference_status)
        if self.layouts:
            status["layouts"] = [
                {
                    "reference_key": str(layout.get("reference_key") or ""),
                    "manual_start_addr": int(layout.get("manual_start_addr") or 0),
                    "manual_word_count": int(layout.get("manual_word_count") or 0),
                    "handshake_address": int(layout.get("handshake_address") or 0),
                }
                for layout in self.layouts
            ]
        else:
            status["layouts"] = []
        return status

    def _build_layouts_from_manual_weighing(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build per-slot layout from MANUAL_WEIGHING structure (shared header + item slots)."""
        header = section.get("header")
        items = section.get("items")

        if not isinstance(header, dict) or not isinstance(items, list):
            logger.warning("MANUAL_WEIGHING format invalid (header/items), skipping")
            return []

        batch_field = header.get("batch")
        mo_field = header.get("no_mo")
        if not isinstance(batch_field, dict) or not isinstance(mo_field, dict):
            logger.warning("MANUAL_WEIGHING header incomplete (batch/no_mo), skipping")
            return []

        layouts: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            product_field = item.get("product_id")
            consumption_field = item.get("consumption")
            handshake_field = item.get("status_manual_weigh_read")
            if not isinstance(product_field, dict) or not isinstance(consumption_field, dict) or not isinstance(handshake_field, dict):
                continue

            slot_raw = item.get("slot")
            try:
                slot = int(str(slot_raw))
            except (TypeError, ValueError):
                slot = len(layouts) + 1

            if self._manual_reference_key != "ALL":
                expected_key = f"MANUAL{slot:02d}"
                if self._manual_reference_key != expected_key:
                    continue

            try:
                parsed: Dict[str, Tuple[int, int]] = {}
                parsed["batch"] = self._parse_dm_address(str(batch_field.get("DM") or ""))
                parsed["mo"] = self._parse_dm_address(str(mo_field.get("DM") or ""))
                parsed["product"] = self._parse_dm_address(str(product_field.get("DM") or ""))
                parsed["consumption"] = self._parse_dm_address(str(consumption_field.get("DM") or ""))
                parsed["handshake"] = self._parse_dm_address(str(handshake_field.get("DM") or ""))

                min_addr = min(start for start, _ in parsed.values())
                max_addr = max((start + count - 1) for start, count in parsed.values())

                def _slice_for(name: str) -> Tuple[int, int]:
                    start, count = parsed[name]
                    offset = start - min_addr
                    return (offset, offset + count)

                handshake_index = _slice_for("handshake")[0]
                reference_key = f"MANUAL{slot:02d}"
                layout = {
                    "reference_key": reference_key,
                    "fields": [batch_field, mo_field, product_field, consumption_field, handshake_field],
                    "manual_start_addr": min_addr,
                    "manual_word_count": (max_addr - min_addr) + 1,
                    "batch_slice": _slice_for("batch"),
                    "mo_slice": _slice_for("mo"),
                    "product_slice": _slice_for("product"),
                    "consumption_slice": _slice_for("consumption"),
                    "handshake_index": handshake_index,
                    "handshake_address": min_addr + handshake_index,
                    "batch_type": str(batch_field.get("Data Type") or "INT"),
                    "batch_scale": int(batch_field.get("scale") or 1),
                    "product_type": str(product_field.get("Data Type") or "INT"),
                    "product_scale": int(product_field.get("scale") or 1),
                    "consumption_type": str(consumption_field.get("Data Type") or "REAL"),
                    "consumption_scale": int(consumption_field.get("scale") or 100),
                }
                layouts.append(layout)
            except Exception as exc:
                logger.warning(
                    "Failed parsing MANUAL_WEIGHING slot %s: %s",
                    slot_raw,
                    exc,
                )

        return layouts

    def _build_layout_from_fields(
        self,
        fields: List[Dict[str, Any]],
        reference_key: str,
    ) -> Optional[Dict[str, Any]]:
        field_by_info = {
            str(item.get("Informasi") or "").strip().lower(): item
            for item in fields
        }

        batch_field = field_by_info.get("batch")
        mo_field = field_by_info.get("no-mo")
        product_field = field_by_info.get("no-product")
        consumption_field = field_by_info.get("consumption")
        handshake_field = field_by_info.get("status_manual_weigh_read")

        required_fields = [batch_field, mo_field, product_field, consumption_field, handshake_field]
        if not all(required_fields):
            logger.warning(
                "Manual weighing reference %s incomplete; skipping this layout",
                reference_key,
            )
            return None

        try:
            batch = cast(Dict[str, Any], batch_field)
            mo = cast(Dict[str, Any], mo_field)
            product = cast(Dict[str, Any], product_field)
            consumption = cast(Dict[str, Any], consumption_field)
            handshake = cast(Dict[str, Any], handshake_field)

            parsed: Dict[str, Tuple[int, int]] = {}
            parsed["batch"] = self._parse_dm_address(str(batch.get("DM") or ""))
            parsed["mo"] = self._parse_dm_address(str(mo.get("DM") or ""))
            parsed["product"] = self._parse_dm_address(str(product.get("DM") or ""))
            parsed["consumption"] = self._parse_dm_address(str(consumption.get("DM") or ""))
            parsed["handshake"] = self._parse_dm_address(str(handshake.get("DM") or ""))

            min_addr = min(start for start, _ in parsed.values())
            max_addr = max((start + count - 1) for start, count in parsed.values())

            def _slice_for(name: str) -> Tuple[int, int]:
                start, count = parsed[name]
                offset = start - min_addr
                return (offset, offset + count)

            handshake_index = _slice_for("handshake")[0]
            layout = {
                "reference_key": reference_key,
                "fields": fields,
                "manual_start_addr": min_addr,
                "manual_word_count": (max_addr - min_addr) + 1,
                "batch_slice": _slice_for("batch"),
                "mo_slice": _slice_for("mo"),
                "product_slice": _slice_for("product"),
                "consumption_slice": _slice_for("consumption"),
                "handshake_index": handshake_index,
                "handshake_address": min_addr + handshake_index,
                "batch_type": str(batch.get("Data Type") or "INT"),
                "batch_scale": int(batch.get("scale") or 1),
                "product_type": str(product.get("Data Type") or "INT"),
                "product_scale": int(product.get("scale") or 1),
                "consumption_type": str(consumption.get("Data Type") or "REAL"),
                "consumption_scale": int(consumption.get("scale") or 100),
            }

            logger.info(
                "Manual weighing layout %s loaded: D%s-D%s (handshake D%s)",
                reference_key,
                layout["manual_start_addr"],
                layout["manual_start_addr"] + layout["manual_word_count"] - 1,
                layout["handshake_address"],
            )
            return layout
        except Exception as exc:
            logger.warning(
                "Failed parsing manual weighing layout for %s: %s",
                reference_key,
                exc,
            )
            return None

    def _apply_layout(self, layout: Dict[str, Any]) -> None:
        self._manual_start_addr = int(layout["manual_start_addr"])
        self._manual_word_count = int(layout["manual_word_count"])
        self._batch_slice = cast(Tuple[int, int], layout["batch_slice"])
        self._mo_slice = cast(Tuple[int, int], layout["mo_slice"])
        self._product_slice = cast(Tuple[int, int], layout["product_slice"])
        self._consumption_slice = cast(Tuple[int, int], layout["consumption_slice"])
        self._handshake_index = int(layout["handshake_index"])
        self._batch_type = str(layout["batch_type"])
        self._batch_scale = int(layout["batch_scale"])
        self._product_type = str(layout["product_type"])
        self._product_scale = int(layout["product_scale"])
        self._consumption_type = str(layout["consumption_type"])
        self._consumption_scale = int(layout["consumption_scale"])

    def _get_field(self, info_name: str) -> Optional[Dict[str, Any]]:
        return self._field_by_info.get(info_name.strip().lower())

    def _configure_manual_layout_from_reference(self) -> None:
        """Build manual weighing memory layout dynamically from reference file."""
        batch_field = self._get_field("BATCH")
        mo_field = self._get_field("NO-MO")
        product_field = self._get_field("NO-Product")
        consumption_field = self._get_field("Consumption")
        handshake_field = self._get_field("status_manual_weigh_read")

        required_fields = [batch_field, mo_field, product_field, consumption_field, handshake_field]
        if not all(required_fields):
            logger.warning(
                "Manual weighing reference incomplete; using fallback hardcoded layout"
            )
            return

        try:
            batch = cast(Dict[str, Any], batch_field)
            mo = cast(Dict[str, Any], mo_field)
            product = cast(Dict[str, Any], product_field)
            consumption = cast(Dict[str, Any], consumption_field)
            handshake = cast(Dict[str, Any], handshake_field)

            parsed: Dict[str, Tuple[int, int]] = {}
            parsed["batch"] = self._parse_dm_address(str(batch.get("DM") or ""))
            parsed["mo"] = self._parse_dm_address(str(mo.get("DM") or ""))
            parsed["product"] = self._parse_dm_address(str(product.get("DM") or ""))
            parsed["consumption"] = self._parse_dm_address(str(consumption.get("DM") or ""))
            parsed["handshake"] = self._parse_dm_address(str(handshake.get("DM") or ""))

            min_addr = min(start for start, _ in parsed.values())
            max_addr = max((start + count - 1) for start, count in parsed.values())

            def _slice_for(name: str) -> Tuple[int, int]:
                start, count = parsed[name]
                offset = start - min_addr
                return (offset, offset + count)

            self._manual_start_addr = min_addr
            self._manual_word_count = (max_addr - min_addr) + 1
            self._batch_slice = _slice_for("batch")
            self._mo_slice = _slice_for("mo")
            self._product_slice = _slice_for("product")
            self._consumption_slice = _slice_for("consumption")
            self._handshake_index = _slice_for("handshake")[0]

            self._batch_type = str(batch.get("Data Type") or "INT")
            self._batch_scale = int(batch.get("scale") or 1)
            self._product_type = str(product.get("Data Type") or "INT")
            self._product_scale = int(product.get("scale") or 1)
            self._consumption_type = str(consumption.get("Data Type") or "REAL")
            self._consumption_scale = int(consumption.get("scale") or 100)

            logger.info(
                "Manual weighing layout loaded from reference: D%s-D%s (handshake index=%s, addr=D%s)",
                self._manual_start_addr,
                self._manual_start_addr + self._manual_word_count - 1,
                self._handshake_index,
                self._manual_start_addr + self._handshake_index,
            )
        except Exception as exc:
            logger.warning(
                "Failed parsing manual weighing layout from reference; using fallback layout: %s",
                exc,
            )
    
    def _parse_dm_address(self, dm_str: str) -> Tuple[int, int]:
        """
        Parse DM address string menjadi (start_address, word_count).
        
        Examples:
            "D9000" -> (9000, 1)
            "D9001-D9008" -> (9001, 8)
        """
        dm_str = dm_str.strip().upper().replace(" ", "")
        
        # Single address: D9000
        if "-" not in dm_str:
            match = re.match(r"D(\d+)", dm_str)
            if not match:
                raise ValueError(f"Invalid DM address format: {dm_str}")
            address = int(match.group(1))
            return (address, 1)
        
        # Range address: D9001-D9008
        match = re.match(r"D(\d+)-D*(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM range format: {dm_str}")
        
        start = int(match.group(1))
        end = int(match.group(2))
        count = end - start + 1
        
        if count <= 0:
            raise ValueError(f"Invalid DM range: {dm_str} (count={count})")
        
        return (start, count)
    
    def _parse_ascii(self, words: List[int], length: int) -> str:
        """Parse ASCII text dari word list."""
        if not words:
            return ""
        
        chars: List[str] = []
        byte_count = 0
        
        for word in words:
            if byte_count >= length:
                break
            # Big-endian: high byte first
            char1 = (word >> 8) & 0xFF
            char2 = word & 0xFF
            
            if byte_count < length:
                if char1 != 0:
                    chars.append(chr(char1))
                byte_count += 1
            if byte_count < length:
                if char2 != 0:
                    chars.append(chr(char2))
                byte_count += 1
        
        return "".join(chars).replace("\x00", "").strip()
    
    def _convert_from_words(
        self, 
        words: List[int], 
        data_type: str, 
        scale: int = 1,
    ) -> Any:
        """Convert word list berdasarkan data type."""
        if not words:
            return None
        
        if data_type.upper() == "REAL":
            # REAL = 2 words (32-bit), combine them properly
            # Format: high_word << 16 | low_word, then divide by scale
            if not words:
                return 0.0
            if len(words) >= 2:
                # Combine 2 words into 32-bit value (big-endian)
                raw_value = (words[0] << 16) | words[1]
            else:
                # Fallback to single word if only 1 word provided
                raw_value = words[0]
            
            # Apply scale factor
            scale_value = scale if scale and scale > 0 else 1
            return float(raw_value) / float(scale_value)
        
        elif data_type.upper() == "INT":
            # INT = 1 word (16-bit signed) atau 2 words (32-bit signed)
            if not words:
                return 0
            if len(words) >= 2:
                # 32-bit signed integer
                raw_value = (words[0] << 16) | words[1]
                # Handle signed values
                if raw_value > 2147483647:
                    raw_value -= 4294967296
                return int(raw_value)
            else:
                # 16-bit signed integer
                raw_value = words[0]
                # Handle signed values
                if raw_value > 32767:
                    raw_value -= 65536
                return int(raw_value)
        
        elif data_type.upper() == "ASCII":
            # ASCII: 2 chars per word, big-endian
            # Para "NO-MO" yang 8 chars = 4 words (D9001-D9008 berarti 8 addresses total)
            return self._parse_ascii(words, 16)  # Max 16 chars
        
        elif data_type.upper() == "BOOLEAN":
            # BOOLEAN: 1 word, value 0 or 1
            return bool(words[0]) if words else False
        
        return None
    
    def read_manual_weighing_data(self, layout: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Read manual weighing data dari PLC memory area (dynamic from reference).
        
        Returns dict dengan structure:
        {
            "batch": int,
            "mo_id": str,
            "product_id": int,
            "product_tmpl_id": int,
            "consumption": float,
            "handshake_flag": int (0 or 1),
            "timestamp": str
        }
        
        Returns None jika read gagal atau tidak ada data baru.
        """
        try:
            current_layout = layout or {
                "reference_key": self._manual_reference_key,
                "manual_start_addr": self._manual_start_addr,
                "manual_word_count": self._manual_word_count,
                "batch_slice": self._batch_slice,
                "mo_slice": self._mo_slice,
                "product_slice": self._product_slice,
                "consumption_slice": self._consumption_slice,
                "handshake_index": self._handshake_index,
                "handshake_address": self._manual_start_addr + self._handshake_index,
                "batch_type": self._batch_type,
                "batch_scale": self._batch_scale,
                "product_type": self._product_type,
                "product_scale": self._product_scale,
                "consumption_type": self._consumption_type,
                "consumption_scale": self._consumption_scale,
            }

            # Read memory area from reference layout
            start_addr = int(current_layout["manual_start_addr"])
            word_count = int(current_layout["manual_word_count"])
            batch_slice = cast(Tuple[int, int], current_layout["batch_slice"])
            mo_slice = cast(Tuple[int, int], current_layout["mo_slice"])
            product_slice = cast(Tuple[int, int], current_layout["product_slice"])
            consumption_slice = cast(Tuple[int, int], current_layout["consumption_slice"])
            handshake_index = int(current_layout["handshake_index"])
            batch_type = str(current_layout["batch_type"])
            batch_scale = int(current_layout["batch_scale"])
            product_type = str(current_layout["product_type"])
            product_scale = int(current_layout["product_scale"])
            consumption_type = str(current_layout["consumption_type"])
            consumption_scale = int(current_layout["consumption_scale"])
            
            with FinsUdpClient(
                ip=self.settings.plc_ip,
                port=self.settings.plc_port,
                timeout_sec=self.settings.plc_timeout_sec,
            ) as client:
                read_request = MemoryReadRequest(
                    area="DM",
                    address=start_addr,
                    count=word_count,
                )
                
                frame = build_memory_read_frame(
                    req=read_request,
                    client_node=self.settings.client_node,
                    plc_node=self.settings.plc_node,
                )
                
                client.send_raw_hex(frame.hex())
                response = client.recv()
                
                data_words = parse_memory_read_response(response.raw, word_count)
            
            # Check handshake flag first (dynamic index from reference)
            handshake_flag = data_words[handshake_index]
            if handshake_flag != 0:
                logger.debug(
                    "[%s] D%s handshake flag = 1 (already read), skipping",
                    str(current_layout.get("reference_key") or "MANUAL"),
                    start_addr + handshake_index,
                )
                return None  # Data sudah dibaca, tidak ada data baru
            
            # Parse fields using dynamic layout from reference
            batch_words = data_words[batch_slice[0]:batch_slice[1]]
            mo_words = data_words[mo_slice[0]:mo_slice[1]]
            product_words = data_words[product_slice[0]:product_slice[1]]
            consumption_words = data_words[consumption_slice[0]:consumption_slice[1]]

            batch = self._convert_from_words(batch_words, batch_type, scale=batch_scale)
            mo_id_raw = self._convert_from_words(mo_words, "ASCII")
            mo_id = str(mo_id_raw) if mo_id_raw else ""
            
            product_tmpl_id_raw = self._convert_from_words(
                product_words,
                product_type,
                scale=product_scale,
            )
            consumption_raw = self._convert_from_words(
                consumption_words,
                consumption_type,
                scale=consumption_scale,
            )
            
            # Validation
            if not mo_id or len(mo_id.strip()) == 0:
                logger.warning("NO-MO is empty, skipping")
                return None
            
            try:
                product_tmpl_id = float(product_tmpl_id_raw) if product_tmpl_id_raw is not None else 0.0
                consumption = float(consumption_raw) if consumption_raw is not None else 0.0
            except (ValueError, TypeError):
                logger.warning(f"Invalid numeric data: product={product_tmpl_id_raw}, consumption={consumption_raw}")
                return None
            
            if product_tmpl_id <= 0:
                logger.warning(f"NO-Product is invalid ({product_tmpl_id} <= 0), skipping")
                return None
            
            if consumption <= 0:
                logger.warning(f"Consumption is invalid ({consumption} <= 0), skipping")
                return None
            
            result = {
                "batch": int(batch) if batch else 0,
                "mo_id": mo_id.strip(),
                "product_id": int(product_tmpl_id),
                "product_tmpl_id": int(product_tmpl_id),
                "consumption": float(consumption),
                "handshake_flag": handshake_flag,
                "handshake_address": int(current_layout.get("handshake_address") or (start_addr + handshake_index)),
                "reference_key": str(current_layout.get("reference_key") or "MANUAL"),
                "timestamp": datetime.now().isoformat(),
            }
            
            logger.info(f"Read manual weighing data: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error reading manual weighing data from PLC: {e}")
            return None
    
    def validate_weighing_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate manual weighing data sebelum sync ke Odoo.
        
        Returns: (is_valid, error_message)
        """
        if not data:
            return False, "No weighing data provided"
        
        # Validate MO ID format
        mo_id = data.get("mo_id", "").strip()
        if not mo_id:
            return False, "MO ID is empty"
        
        # Validate Product ID (primary: product_id, fallback: product_tmpl_id)
        product_id = data.get("product_id", data.get("product_tmpl_id", 0))
        if not isinstance(product_id, int) or product_id <= 0:
            return False, f"Invalid product_id: {product_id}"
        
        # Validate Consumption quantity
        consumption = data.get("consumption", 0)
        if not isinstance(consumption, (int, float)) or consumption <= 0:
            return False, f"Invalid consumption quantity: {consumption}"
        
        return True, None
    
    def sync_to_odoo(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Sync manual weighing data ke Odoo material consumption API.
        
        Uses endpoint: POST /api/scada/material-consumption
        
        Returns: (sync_success, error_message)
        """
        try:
            mo_id = data.get("mo_id", "").strip()
            product_id = data.get("product_id", data.get("product_tmpl_id", 0))
            consumption = data.get("consumption", 0)
            
            payload = {
                "mo_id": mo_id,
                "product_id": product_id,
                "product_tmpl_id": product_id,
                "quantity": consumption,
                "equipment_id": "WEIGH_SCALE_01",  # Manual weighing station ID
                "timestamp": data.get("timestamp", datetime.now().isoformat()),
            }
            
            # Get session cookies if needed
            cookies = None
            session_id = getattr(self.settings, "ODOO_SESSION_ID", None)
            if session_id:
                cookies = {"session_id": session_id}
            
            # POST to Odoo API
            endpoint = f"{self.base_url}/api/scada/material-consumption"
            body = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if cookies:
                headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

            req = urllib.request.Request(
                endpoint,
                data=body,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read().decode("utf-8")
                status_code = int(getattr(response, "status", 200))

            try:
                result = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                result = {"message": raw}

            if status_code != 200:
                error = str(result.get("message") or raw or "Unknown error")
                logger.error(f"Odoo API error: {error}")
                return False, f"Odoo sync failed: {error}"

            if result.get("status") != "success":
                error = result.get("message", "Unknown error")
                logger.error(f"Odoo API returned error: {error}")
                return False, error
            
            logger.info(f"Successfully synced weighing data to Odoo for MO: {mo_id}")
            return True, None
        
        except urllib.error.URLError as e:
            error = f"Request error: {str(e)}"
            logger.error(error)
            return False, error
        except Exception as e:
            error = f"Unexpected error: {str(e)}"
            logger.error(error)
            return False, error
    
    def mark_handshake(self, handshake_address: Optional[int] = None) -> bool:
        """
        Mark handshake flag manual weighing = 1 setelah successful sync ke Odoo.
        
        Returns True jika berhasil, False jika gagal.
        """
        try:
            target_address = int(handshake_address) if handshake_address is not None else None
            if target_address is not None:
                result = self.handshake_service.mark_manual_weighing_address_as_read(target_address)
            else:
                result = self.handshake_service.mark_manual_weighing_as_read()
            if result:
                logger.info("Marked manual weighing handshake as read")
            else:
                logger.warning("Failed to mark manual weighing handshake as read")
            return result
        except Exception as e:
            logger.error(f"Error marking handshake: {e}")
            return False

    def _build_retry_payload_hash(self, data: Dict[str, Any]) -> str:
        payload = {
            "reference_key": str(data.get("reference_key") or ""),
            "handshake_address": int(data.get("handshake_address") or 0),
            "batch": int(data.get("batch") or 0),
            "mo_id": str(data.get("mo_id") or "").strip(),
            "product_id": int(data.get("product_id") or data.get("product_tmpl_id") or 0),
            "consumption": round(float(data.get("consumption") or 0.0), 6),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _find_pending_retry_record(self, data: Dict[str, Any]) -> Optional[ManualWeighingSync]:
        payload_hash = self._build_retry_payload_hash(data)
        reference_key = str(data.get("reference_key") or "")
        handshake_address = int(data.get("handshake_address") or 0)

        session = SessionLocal()
        try:
            stmt = (
                select(ManualWeighingSync)
                .where(
                    ManualWeighingSync.payload_hash == payload_hash,
                    ManualWeighingSync.reference_key == reference_key,
                    ManualWeighingSync.handshake_address == handshake_address,
                    ManualWeighingSync.handshake_marked_at.is_(None),
                )
                .order_by(ManualWeighingSync.odoo_synced_at.desc())
            )
            return session.execute(stmt).scalars().first()
        except Exception as exc:
            logger.error("Failed checking manual weighing retry record: %s", exc)
            return None
        finally:
            session.close()

    def _record_successful_sync(self, data: Dict[str, Any]) -> Any:
        session = SessionLocal()
        try:
            record = ManualWeighingSync(
                reference_key=str(data.get("reference_key") or ""),
                handshake_address=int(data.get("handshake_address") or 0),
                batch_no=int(data.get("batch") or 0),
                mo_id=str(data.get("mo_id") or "").strip(),
                product_id=int(data.get("product_id") or data.get("product_tmpl_id") or 0),
                consumption=float(data.get("consumption") or 0.0),
                payload_hash=self._build_retry_payload_hash(data),
                status="pending_handshake",
                odoo_synced_at=datetime.now(timezone.utc),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id
        except Exception as exc:
            session.rollback()
            logger.error("Failed recording successful manual weighing sync: %s", exc)
            return None
        finally:
            session.close()

    def _mark_retry_completed(self, record_id: Any) -> None:
        if not record_id:
            return

        session = SessionLocal()
        try:
            record = session.get(ManualWeighingSync, record_id)
            if record is None:
                return
            record.status = "completed"
            record.handshake_marked_at = datetime.now(timezone.utc)
            record.last_error = None
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Failed marking manual weighing retry completed: %s", exc)
        finally:
            session.close()

    def _update_retry_error(self, record_id: Any, error: str) -> None:
        if not record_id:
            return

        session = SessionLocal()
        try:
            record = session.get(ManualWeighingSync, record_id)
            if record is None:
                return
            record.last_error = error
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Failed updating manual weighing retry error: %s", exc)
        finally:
            session.close()
    
    def read_and_sync(self) -> bool:
        """
        Main workflow: Read all configured slots → Validate → Sync → Mark Handshake.
        
        This is the primary method called by TASK 7 scheduler.
        
        Returns True jika operation sukses, False jika ada error.
        """
        try:
            layouts = self.layouts or [
                {
                    "reference_key": self._manual_reference_key,
                    "manual_start_addr": self._manual_start_addr,
                    "manual_word_count": self._manual_word_count,
                    "batch_slice": self._batch_slice,
                    "mo_slice": self._mo_slice,
                    "product_slice": self._product_slice,
                    "consumption_slice": self._consumption_slice,
                    "handshake_index": self._handshake_index,
                    "handshake_address": self._manual_start_addr + self._handshake_index,
                    "batch_type": self._batch_type,
                    "batch_scale": self._batch_scale,
                    "product_type": self._product_type,
                    "product_scale": self._product_scale,
                    "consumption_type": self._consumption_type,
                    "consumption_scale": self._consumption_scale,
                }
            ]

            has_failure = False
            processed_count = 0

            for layout in layouts:
                slot_key = str(layout.get("reference_key") or "MANUAL")

                weighing_data = self.read_manual_weighing_data(layout=layout)
                if not weighing_data:
                    continue

                is_valid, error = self.validate_weighing_data(weighing_data)
                if not is_valid:
                    logger.warning("[%s] Validation failed: %s", slot_key, error)
                    has_failure = True
                    continue

                pending_retry = self._find_pending_retry_record(weighing_data)
                if pending_retry is not None:
                    logger.warning(
                        "[%s] Found pending retry after prior Odoo success; skipping Odoo re-sync and retrying handshake only",
                        slot_key,
                    )
                    handshake_address = weighing_data.get("handshake_address")
                    if not self.mark_handshake(
                        int(handshake_address) if isinstance(handshake_address, (int, float)) else None
                    ):
                        self._update_retry_error(
                            pending_retry.id,
                            "Handshake retry failed after prior Odoo success",
                        )
                        has_failure = True
                        continue

                    self._mark_retry_completed(pending_retry.id)
                    processed_count += 1
                    continue

                sync_ok, sync_error = self.sync_to_odoo(weighing_data)
                if not sync_ok:
                    logger.error("[%s] Sync failed: %s", slot_key, sync_error)
                    has_failure = True
                    continue

                retry_record_id = self._record_successful_sync(weighing_data)
                if retry_record_id is None:
                    logger.error(
                        "[%s] Odoo sync succeeded but retry marker could not be persisted; duplicate protection is unavailable if handshake fails",
                        slot_key,
                    )

                handshake_address = weighing_data.get("handshake_address")
                if not self.mark_handshake(
                    int(handshake_address) if isinstance(handshake_address, (int, float)) else None
                ):
                    self._update_retry_error(
                        retry_record_id,
                        "Odoo sync succeeded but handshake write failed",
                    )
                    logger.error(
                        "[%s] Odoo sync succeeded but failed to mark handshake; this slot may be retried and can duplicate downstream processing",
                        slot_key,
                    )
                    has_failure = True
                    continue

                self._mark_retry_completed(retry_record_id)
                processed_count += 1

            logger.info(
                "Manual weighing read and sync cycle finished: processed=%s slots=%s failure=%s",
                processed_count,
                len(layouts),
                has_failure,
            )
            return not has_failure
        
        except Exception as e:
            logger.error(f"Unexpected error in read_and_sync: {e}")
            return False


# Global instance
_manual_weighing_service: Optional[PLCManualWeighingService] = None


def get_manual_weighing_service() -> PLCManualWeighingService:
    """Get or create global manual weighing service instance."""
    global _manual_weighing_service
    if _manual_weighing_service is None:
        _manual_weighing_service = PLCManualWeighingService()
    return _manual_weighing_service
