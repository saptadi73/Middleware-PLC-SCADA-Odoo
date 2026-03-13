"""
PLC Manual Weighing Service
Membaca data penimbangan material manual dari PLC menggunakan ADDITIONAL_EQUIPMENT_REFERENCE.json.
Includes handshake logic dan sync ke Odoo material consumption API.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)
from app.services.plc_handshake_service import get_handshake_service

logger = logging.getLogger(__name__)


class PLCManualWeighingService:
    """
    Service untuk read data manual material weighing dari PLC menggunakan FINS protocol.
    Memory area: D9000-D9011 (TASK 5)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.mapping: List[Dict[str, Any]] = []
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
        self._load_reference()
        self.base_url = self.settings.odoo_base_url
        self.handshake_service = get_handshake_service()
    
    def _load_reference(self):
        """Load ADDITIONAL_EQUIPMENT_REFERENCE.json sebagai mapping reference."""
        reference_path = Path(__file__).parent.parent / "reference" / "ADDITIONAL_EQUIPMENT_REFERENCE.json"
        
        if not reference_path.exists():
            logger.warning(f"ADDITIONAL_EQUIPMENT_REFERENCE.json not found at {reference_path}")
            return
        
        try:
            with open(reference_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.mapping = data.get("ADDITIONAL", [])
                self.mapping_structure = data.get("mapping_structure", {})

            self._field_by_info = {
                str(item.get("Informasi") or "").strip().lower(): item
                for item in self.mapping
            }
            self._configure_manual_layout_from_reference()
            
            logger.info(f"Loaded PLC manual weighing mapping: {len(self.mapping)} fields")
        except Exception as e:
            logger.error(f"Error loading additional equipment reference: {e}")

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

            self._manual_start_addr = min_addr
            self._manual_word_count = (max_addr - min_addr) + 1
            self._batch_slice = _slice_for("batch")
            self._mo_slice = _slice_for("mo")
            self._product_slice = _slice_for("product")
            self._consumption_slice = _slice_for("consumption")
            self._handshake_index = _slice_for("handshake")[0]

            self._batch_type = str(batch_field.get("Data Type") or "INT")
            self._batch_scale = int(batch_field.get("scale") or 1)
            self._product_type = str(product_field.get("Data Type") or "INT")
            self._product_scale = int(product_field.get("scale") or 1)
            self._consumption_type = str(consumption_field.get("Data Type") or "REAL")
            self._consumption_scale = int(consumption_field.get("scale") or 100)

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
    
    def read_manual_weighing_data(self) -> Optional[Dict[str, Any]]:
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
            # Read memory area from reference layout
            start_addr = self._manual_start_addr
            word_count = self._manual_word_count
            
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
            handshake_flag = data_words[self._handshake_index]
            if handshake_flag != 0:
                logger.debug(
                    "D%s handshake flag = 1 (already read), skipping",
                    start_addr + self._handshake_index,
                )
                return None  # Data sudah dibaca, tidak ada data baru
            
            # Parse fields using dynamic layout from reference
            batch_words = data_words[self._batch_slice[0]:self._batch_slice[1]]
            mo_words = data_words[self._mo_slice[0]:self._mo_slice[1]]
            product_words = data_words[self._product_slice[0]:self._product_slice[1]]
            consumption_words = data_words[self._consumption_slice[0]:self._consumption_slice[1]]

            batch = self._convert_from_words(batch_words, self._batch_type, scale=self._batch_scale)
            mo_id_raw = self._convert_from_words(mo_words, "ASCII")
            mo_id = str(mo_id_raw) if mo_id_raw else ""
            
            product_tmpl_id_raw = self._convert_from_words(
                product_words,
                self._product_type,
                scale=self._product_scale,
            )
            consumption_raw = self._convert_from_words(
                consumption_words,
                self._consumption_type,
                scale=self._consumption_scale,
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
            response = requests.post(
                endpoint,
                json=payload,
                cookies=cookies,
                timeout=10,
            )
            
            if response.status_code != 200:
                error = response.json().get("message", response.text)
                logger.error(f"Odoo API error: {error}")
                return False, f"Odoo sync failed: {error}"
            
            result = response.json()
            if result.get("status") != "success":
                error = result.get("message", "Unknown error")
                logger.error(f"Odoo API returned error: {error}")
                return False, error
            
            logger.info(f"Successfully synced weighing data to Odoo for MO: {mo_id}")
            return True, None
        
        except requests.RequestException as e:
            error = f"Request error: {str(e)}"
            logger.error(error)
            return False, error
        except Exception as e:
            error = f"Unexpected error: {str(e)}"
            logger.error(error)
            return False, error
    
    def mark_handshake(self) -> bool:
        """
        Mark handshake flag manual weighing = 1 setelah successful sync ke Odoo.
        
        Returns True jika berhasil, False jika gagal.
        """
        try:
            # Use handshake service to set configured manual weighing flag = 1
            result = self.handshake_service.mark_manual_weighing_as_read()
            if result:
                logger.info("Marked manual weighing handshake as read")
            else:
                logger.warning("Failed to mark manual weighing handshake as read")
            return result
        except Exception as e:
            logger.error(f"Error marking handshake: {e}")
            return False
    
    def read_and_sync(self) -> bool:
        """
        Main workflow: Read → Validate → Sync → Mark Handshake.
        
        This is the primary method called by TASK 5 scheduler.
        
        Returns True jika operation sukses, False jika ada error.
        """
        try:
            # Step 1: Read data dari PLC
            weighing_data = self.read_manual_weighing_data()
            if not weighing_data:
                # No new data or already read
                return True  # Not an error, just no action needed
            
            # Step 2: Validate data
            is_valid, error = self.validate_weighing_data(weighing_data)
            if not is_valid:
                logger.warning(f"Validation failed: {error}")
                # Don't mark handshake, keep D9013=0 for retry
                return False
            
            # Step 3: Sync to Odoo
            sync_ok, sync_error = self.sync_to_odoo(weighing_data)
            if not sync_ok:
                logger.error(f"Sync failed: {sync_error}")
                # Don't mark handshake, keep D9013=0 for retry
                return False
            
            # Step 4: Mark handshake (only after successful sync)
            if not self.mark_handshake():
                logger.warning("Failed to mark handshake, but Odoo sync was successful")
                # Even if handshake fails, operation is considered successful
                # (Odoo has the data, retrying handshake next cycle)
            
            logger.info("Manual weighing read and sync cycle completed successfully")
            return True
        
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
