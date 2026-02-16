"""
PLC Equipment Failure Service
Membaca data equipment failure dari PLC menggunakan EQUIPMENT_FAILURE_REFERENCE.json sebagai mapping.
"""
import json
import logging
import re
from datetime import datetime
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


class PLCEquipmentFailureService:
    """Service untuk read data equipment failure dari PLC menggunakan FINS protocol."""
    
    def __init__(self):
        self.settings = get_settings()
        self.mapping: List[Dict[str, Any]] = []
        self.mapping_structure: Dict[str, Any] = {}
        self._load_reference()
    
    def _load_reference(self):
        """Load EQUIPMENT_FAILURE_REFERENCE.json sebagai mapping reference."""
        reference_path = Path(__file__).parent.parent / "reference" / "EQUIPMENT_FAILURE_REFERENCE.json"
        
        if not reference_path.exists():
            logger.warning(f"EQUIPMENT_FAILURE_REFERENCE.json not found at {reference_path}")
            return
        
        try:
            with open(reference_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.mapping = data.get("raw_list", [])
                self.mapping_structure = data.get("mapping_structure", {})
            
            logger.info(f"Loaded PLC equipment failure mapping: {len(self.mapping)} fields")
        except Exception as e:
            logger.error(f"Error loading equipment failure reference: {e}")
    
    def _parse_dm_address(self, dm_str: str) -> tuple[int, int]:
        """
        Parse DM address string menjadi (start_address, word_count).
        
        Examples:
            "D6001" -> (6001, 1)
            "D6001-6008" -> (6001, 8)
        """
        dm_str = dm_str.strip().upper().replace(" ", "")
        
        # Single address: D6001
        if "-" not in dm_str:
            match = re.match(r"D(\d+)", dm_str)
            if not match:
                raise ValueError(f"Invalid DM address format: {dm_str}")
            address = int(match.group(1))
            return (address, 1)
        
        # Range address: D6001-6008
        match = re.match(r"D(\d+)-(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM range format: {dm_str}")
        
        start = int(match.group(1))
        end = int(match.group(2))
        count = end - start + 1
        
        if count <= 0:
            raise ValueError(f"Invalid DM range: {dm_str} (count={count})")
        
        return (start, count)
    
    def _convert_bcd_to_number(self, word: int, digits: int = 2) -> int:
        """
        Convert BCD (Binary Coded Decimal) format to number.
        BCD format stores digits in nibbles: 0x23 = 23 (decimal)
        Supports 2-digit (MM/DD/HH/MM/SS) and 4-digit (YYYY) values.
        """
        if digits == 4:
            thousands = (word >> 12) & 0x0F
            hundreds = (word >> 8) & 0x0F
            tens = (word >> 4) & 0x0F
            ones = word & 0x0F
            return thousands * 1000 + hundreds * 100 + tens * 10 + ones

        high_nibble = (word >> 4) & 0x0F
        low_nibble = word & 0x0F
        return high_nibble * 10 + low_nibble
    
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
        length: Optional[int] = None,
    ) -> Any:
        """Convert word list berdasarkan data type."""
        if not words:
            return None
        
        if data_type.upper() == "REAL":
            # REAL 32-bit float dari 2 words
            if len(words) < 2:
                return None
            word1 = words[0]
            word2 = words[1]
            # Combine words untuk floating point
            combined = (word2 << 16) | word1
            bytes_data = combined.to_bytes(4, byteorder="little")
            return int.from_bytes(bytes_data, byteorder="little")
        
        elif data_type.upper() == "ASCII":
            return self._parse_ascii(words, length or 16)
        
        elif data_type.upper() == "BCD":
            # BCD 2-digit number
            if len(words) < 1:
                return None
            digits = 4 if (length or 0) >= 4 else 2
            return self._convert_bcd_to_number(words[0], digits=digits)
        
        return None
    
    async def read_equipment_failure_data(self) -> Optional[Dict[str, Any]]:
        """
        Read equipment failure data dari PLC secara lengkap.
        
        Returns:
            Dict dengan struktur:
            {
                "equipment_code": "silo101",
                "failure_info": "START_FAILURE",
                "failure_timestamp": "2026-02-23 20:22:35",
                "raw_data": {...}
            }
            atau None jika gagal membaca.
        """
        if not self.mapping:
            logger.error("Equipment failure mapping not loaded")
            return None
        
        try:
            result = {}
            raw_data = {}

            with FinsUdpClient(
                ip=self.settings.plc_ip,
                port=self.settings.plc_port,
                timeout_sec=self.settings.plc_timeout_sec,
            ) as client:
                # Read all addresses dari mapping
                for field in self.mapping:
                    field_name = field.get("Informasi", "")
                    dm_address = field.get("DM - Memory", "")
                    data_type = field.get("Data Type", "")
                    length = field.get("length")

                    if not dm_address:
                        continue

                    try:
                        start_addr, word_count = self._parse_dm_address(dm_address)

                        # Build dan send FINS read request
                        request = MemoryReadRequest(
                            area="DM",
                            address=start_addr,
                            count=word_count,
                        )

                        frame = build_memory_read_frame(
                            request,
                            client_node=self.settings.client_node,
                            plc_node=self.settings.plc_node,
                        )

                        client.send_raw_hex(frame.hex())
                        response = client.recv()

                        # Parse response
                        words = parse_memory_read_response(response.raw, word_count)
                        if not words:
                            logger.warning(f"Failed to parse response for {field_name}")
                            continue

                        # Convert to appropriate data type
                        value = self._convert_from_words(words, data_type, length)

                        # Store di result
                        if field_name:
                            result[field_name] = value
                            raw_data[field_name] = {
                                "value": value,
                                "data_type": data_type,
                                "raw_words": words,
                            }

                        logger.debug(f"✓ Read {field_name}: {value}")

                    except Exception as e:
                        logger.error(f"Error reading {field_name}: {e}")
                        continue
            
            # Combine timestamp fields
            equipment_failure_data = {
                "equipment_code": result.get("equipment_code"),
                "failure_info": result.get("INFO"),
                "failure_timestamp": self._build_timestamp(result),
                "raw_data": raw_data,
            }
            
            logger.info(f"✓ Successfully read equipment failure data: {equipment_failure_data['equipment_code']}")
            return equipment_failure_data
        
        except Exception as e:
            logger.error(f"Error reading equipment failure from PLC: {e}")
            return None
    
    def _build_timestamp(self, data: Dict[str, Any]) -> Optional[str]:
        """Build timestamp dari BCD fields."""
        try:
            year = data.get("Year")
            month = data.get("Month")
            day = data.get("Day")
            hour = data.get("Hour")
            minute = data.get("Minute")
            second = data.get("Second")
            
            if all(v is not None for v in [year, month, day, hour, minute, second]):
                return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
        except Exception as e:
            logger.error(f"Error building timestamp: {e}")
        
        return None
    
    def get_mapping_info(self) -> Dict[str, Any]:
        """Get mapping reference info."""
        return {
            "total_fields": len(self.mapping),
            "fields": [f.get("Informasi") for f in self.mapping],
            "structure": self.mapping_structure,
        }


def get_equipment_failure_service() -> PLCEquipmentFailureService:
    """Factory function untuk get equipment failure service instance."""
    return PLCEquipmentFailureService()
