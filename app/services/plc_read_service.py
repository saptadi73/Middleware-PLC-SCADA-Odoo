"""
PLC Read Service
Menggunakan READ_DATA_PLC_MAPPING.json sebagai mapping memory PLC untuk read.
"""
import json
import logging
import math
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
    """Service untuk read data dari PLC menggunakan FINS protocol."""
    
    def __init__(self):
        self.settings = get_settings()
        self.mapping: List[Dict[str, Any]] = []
        self._load_reference()
    
    def _load_reference(self):
        """Load READ_DATA_PLC_MAPPING.json sebagai mapping reference."""
        reference_path = Path(__file__).parent.parent / "reference" / "READ_DATA_PLC_MAPPING.json"
        
        if not reference_path.exists():
            logger.warning(f"READ_DATA_PLC_MAPPING.json not found at {reference_path}")
            return
        
        with open(reference_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.mapping = data.get("raw_list", [])
        
        logger.info(f"Loaded PLC read mapping: {len(self.mapping)} fields")
    
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
    
    def _convert_from_words(
        self, 
        words: List[int], 
        data_type: str, 
        scale: Optional[float] = None
    ) -> Any:
        """
        Convert list of 16-bit words dari PLC ke Python value.
        
        Args:
            words: List of 16-bit integer values from PLC
            data_type: "REAL", "ASCII", atau "boolean"
            scale: Scale factor (untuk REAL)
        
        Returns:
            Python value (int, float, str, bool)
        """
        data_type = data_type.upper()
        
        if data_type == "BOOLEAN":
            # Boolean -> 0 atau 1
            return bool(words[0]) if words else False
        
        elif data_type == "REAL":
            # REAL -> integer dengan scale factor
            if not words:
                return 0.0
            
            raw_value = words[0]
            
            # Handle signed 16-bit integer
            if raw_value > 32767:
                raw_value = raw_value - 65536
            
            scale = scale if scale else 1.0
            return float(raw_value) / scale
        
        elif data_type == "ASCII":
            # ASCII -> bytes, 2 bytes per word (big-endian)
            chars = []
            for word in words:
                # Extract 2 characters from each word (big-endian)
                char1 = (word >> 8) & 0xFF
                char2 = word & 0xFF
                
                if char1 != 0:
                    chars.append(chr(char1))
                if char2 != 0:
                    chars.append(chr(char2))
            
            # Join and strip null characters
            result = "".join(chars).rstrip("\x00")
            return result
        
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
    
    def read_field(self, field_name: str) -> Any:
        """
        Read single field dari PLC memory.
        
        Args:
            field_name: Informasi field (e.g., "NO-MO", "SILO ID 101 (SILO BESAR)")
        
        Returns:
            Value from PLC
        """
        # Find field definition
        field_def = None
        for item in self.mapping:
            if item.get("Informasi") == field_name:
                field_def = item
                break
        
        if not field_def:
            raise ValueError(f"Field {field_name} not found in mapping")
        
        # Parse address
        dm_str = field_def["DM - Memory"]
        address, word_count = self._parse_dm_address(dm_str)
        
        # Read from PLC
        words = self._read_from_plc(address, word_count)
        
        # Convert to Python value
        data_type = field_def["Data Type"]
        scale = field_def.get("scale")
        
        value = self._convert_from_words(words, data_type, scale)
        
        logger.info(f"Read {field_name} from DM {address}: {words} -> {value}")
        
        return value
    
    def read_all_fields(self) -> Dict[str, Any]:
        """
        Read semua fields dari PLC memory.
        
        Returns:
            Dictionary dengan key=field_name, value=data dari PLC
        """
        result = {}
        
        for field_def in self.mapping:
            field_name = field_def.get("Informasi")
            if not field_name:
                continue
            
            try:
                value = self.read_field(field_name)
                result[field_name] = value
            except Exception as exc:
                logger.error(f"Error reading {field_name}: {exc}")
                result[field_name] = None
        
        return result
    
    def _read_from_plc(self, address: int, count: int) -> List[int]:
        """
        Low-level read dari PLC menggunakan FINS protocol.
        
        Args:
            address: DM address (e.g., 6001)
            count: Number of words to read
        
        Returns:
            List of 16-bit integer values
        """
        with FinsUdpClient(
            ip=self.settings.plc_ip,
            port=self.settings.plc_port,
            timeout_sec=self.settings.plc_timeout_sec,
        ) as client:
            # Build FINS read frame
            req = MemoryReadRequest(
                area="DM",
                address=address,
                count=count,
            )
            
            frame = build_memory_read_frame(
                req=req,
                client_node=self.settings.client_node,
                plc_node=self.settings.plc_node,
                sid=0x00,
            )
            
            # Send frame
            client.send_raw_hex(frame.hex())
            
            # Receive response
            response = client.recv()
            
            # Parse response
            words = parse_memory_read_response(response.raw, expected_count=count)
            
            return words
    
    def read_batch_data(self) -> Dict[str, Any]:
        """
        Read semua data batch dari PLC dan format sebagai dictionary.
        
        Returns:
            Dictionary dengan struktur batch data
        """
        all_fields = self.read_all_fields()
        
        # Format data
        batch_data = {
            "mo_id": all_fields.get("NO-MO", ""),
            "product_name": all_fields.get("finished_goods", ""),
            "bom_name": all_fields.get("NO-BoM", ""),
            "quantity": all_fields.get("Quantity Goods_id", 0),
            "silos": {},
            "status": {
                "manufacturing": all_fields.get("status manufaturing", False),
                "operation": all_fields.get("Status Operation", False),
            },
            "weight_finished_good": all_fields.get("weight_finished_good", 0),
        }
        
        # Map silos
        silo_mapping = {
            101: "a", 102: "b", 103: "c", 104: "d", 105: "e", 106: "f",
            107: "g", 108: "h", 109: "i", 110: "j", 111: "k", 112: "l", 113: "m",
        }
        
        for silo_num, letter in silo_mapping.items():
            # Find silo ID field
            silo_id_key = None
            for key in all_fields.keys():
                if f"SILO ID {silo_num}" in key or f"SILO {silo_num}" in key:
                    if "Consumption" not in key:
                        silo_id_key = key
                        break
            
            # Fine silo consumption field
            consumption_key = None
            for key in all_fields.keys():
                if f"SILO ID {silo_num}" in key or f"SILO {silo_num}" in key:
                    if "Consumption" in key:
                        consumption_key = key
                        break
            
            if silo_id_key or consumption_key:
                batch_data["silos"][letter] = {
                    "id": all_fields.get(silo_id_key, silo_num) if silo_id_key else silo_num,
                    "consumption": all_fields.get(consumption_key, 0) if consumption_key else 0,
                }
        
        return batch_data


# Singleton instance
_plc_read_service: Optional[PLCReadService] = None


def get_plc_read_service() -> PLCReadService:
    """Get singleton instance of PLCReadService."""
    global _plc_read_service
    if _plc_read_service is None:
        _plc_read_service = PLCReadService()
    return _plc_read_service
