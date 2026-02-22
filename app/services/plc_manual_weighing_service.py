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
        self._load_reference()
        self.base_url = self.settings.ODOO_BASE_URL
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
            
            logger.info(f"Loaded PLC manual weighing mapping: {len(self.mapping)} fields")
        except Exception as e:
            logger.error(f"Error loading additional equipment reference: {e}")
    
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
            # REAL dapat 1 atau 2 words tergantung magnitude
            # Untuk data weighing kami gunakan single word, value already scaled
            if len(words) >= 1:
                value = words[0]
                # Apply scale factor
                if scale and scale > 1:
                    return value / scale
                return value
            return None
        
        elif data_type.upper() == "ASCII":
            # ASCII: 2 chars per word, big-endian
            # Para "NO-MO" yang 8 chars = 4 words (D9001-D9008 berarti 8 addresses total)
            return self._parse_ascii(words, 16)  # Max 16 chars
        
        elif data_type.upper() == "BOOLEAN":
            # BOOLEAN: 1 word, value 0 or 1
            return words[0] if words else 0
        
        return None
    
    def read_manual_weighing_data(self) -> Optional[Dict[str, Any]]:
        """
        Read manual weighing data dari PLC memory area D9000-D9010.
        
        Returns dict dengan structure:
        {
            "batch": int,
            "mo_id": str,
            "product_tmpl_id": int,
            "consumption": float,
            "handshake_flag": int (0 or 1),
            "timestamp": str
        }
        
        Returns None jika read gagal atau tidak ada data baru.
        """
        try:
            client = FinsUdpClient(
                plc_ip=self.settings.PLC_IP,
                plc_port=self.settings.PLC_PORT,
            )
            
            # Read memory area D9000-D9011 (12 words total)
            start_addr = 9000
            word_count = 12  # D9000-D9011
            
            read_request = MemoryReadRequest(
                dm_address=start_addr,
                word_count=word_count,
            )
            
            frame = build_memory_read_frame(read_request)
            response = client.send_command(frame, timeout=5)
            
            if not response or len(response) < 28:  # Minimum response length
                logger.warning("Invalid response from PLC read manual weighing")
                return None
            
            data_words = parse_memory_read_response(response, word_count)
            if not data_words or len(data_words) < 12:
                logger.warning("Insufficient words in PLC response")
                return None
            
            # Check handshake flag first (D9011 = index 11)
            handshake_flag = data_words[11]
            if handshake_flag != 0:
                logger.debug("D9011 handshake flag = 1 (already read), skipping")
                return None  # Data sudah dibaca, tidak ada data baru
            
            # Parse fields
            batch = self._convert_from_words([data_words[0]], "REAL", scale=1)
            mo_words = data_words[1:5]  # D9001-D9004 (4 words = 8 chars)
            mo_id = self._convert_from_words(mo_words, "ASCII")
            product_tmpl_id = self._convert_from_words([data_words[5]], "REAL", scale=1)
            consumption = self._convert_from_words([data_words[6]], "REAL", scale=100)
            
            # Validation
            if not mo_id or len(mo_id.strip()) == 0:
                logger.warning("NO-MO is empty, skipping")
                return None
            
            if not product_tmpl_id or product_tmpl_id <= 0:
                logger.warning("NO-Product is invalid (<=0), skipping")
                return None
            
            if not consumption or consumption <= 0:
                logger.warning("Consumption is invalid (<=0), skipping")
                return None
            
            result = {
                "batch": int(batch) if batch else 0,
                "mo_id": mo_id.strip(),
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
        
        # Validate Product ID
        product_tmpl_id = data.get("product_tmpl_id", 0)
        if not isinstance(product_tmpl_id, int) or product_tmpl_id <= 0:
            return False, f"Invalid product_tmpl_id: {product_tmpl_id}"
        
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
            product_tmpl_id = data.get("product_tmpl_id", 0)
            consumption = data.get("consumption", 0)
            
            payload = {
                "mo_id": mo_id,
                "product_tmpl_id": product_tmpl_id,
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
        Mark handshake flag D9011 = 1 setelah successful sync ke Odoo.
        
        Returns True jika berhasil, False jika gagal.
        """
        try:
            # Use handshake service to set D9011 = 1
            result = self.handshake_service.mark_manual_weighing_as_read()
            if result:
                logger.info("Marked D9011 (manual weighing read) as read")
            else:
                logger.warning("Failed to mark D9011 as read")
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
                # Don't mark handshake, keep D9011=0 for retry
                return False
            
            # Step 3: Sync to Odoo
            sync_ok, sync_error = self.sync_to_odoo(weighing_data)
            if not sync_ok:
                logger.error(f"Sync failed: {sync_error}")
                # Don't mark handshake, keep D9011=0 for retry
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
