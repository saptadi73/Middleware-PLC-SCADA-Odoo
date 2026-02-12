"""
PLC Write Service
Menggunakan MASTER_BATCH_REFERENCE.json sebagai mapping memory PLC.
"""
import json
import logging
import os
import re
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import build_memory_write_frame, parse_memory_write_response

logger = logging.getLogger(__name__)


class PLCWriteService:
    """Service untuk write data ke PLC menggunakan FINS protocol."""
    
    def __init__(self):
        self.settings = get_settings()
        self.mapping: Dict[str, List[Dict[str, Any]]] = {}
        self._load_reference()
    
    def _load_reference(self):
        """Load MASTER_BATCH_REFERENCE.json sebagai mapping reference."""
        reference_path = Path(__file__).parent.parent / "reference" / "MASTER_BATCH_REFERENCE.json"
        
        if not reference_path.exists():
            logger.warning(f"MASTER_BATCH_REFERENCE.json not found at {reference_path}")
            return
        
        with open(reference_path, "r", encoding="utf-8") as f:
            self.mapping = json.load(f)
        
        logger.info(f"Loaded PLC memory mapping: {len(self.mapping)} batches")
    
    def _parse_dm_address(self, dm_str: str) -> tuple[int, int]:
        """
        Parse DM address string menjadi (start_address, word_count).
        
        Examples:
            "D7000" -> (7000, 1)
            "D7001-7008" -> (7001, 8)
        """
        dm_str = dm_str.strip().upper()
        
        # Single address: D7000
        if "-" not in dm_str:
            match = re.match(r"D(\d+)", dm_str)
            if not match:
                raise ValueError(f"Invalid DM address format: {dm_str}")
            address = int(match.group(1))
            return (address, 1)
        
        # Range address: D7001-7008
        match = re.match(r"D(\d+)-(\d+)", dm_str)
        if not match:
            raise ValueError(f"Invalid DM range format: {dm_str}")
        
        start = int(match.group(1))
        end = int(match.group(2))
        count = end - start + 1
        
        if count <= 0:
            raise ValueError(f"Invalid DM range: {dm_str} (count={count})")
        
        return (start, count)
    
    def _convert_to_words(self, value: Any, data_type: str, length: Optional[float] = None, scale: Optional[float] = None) -> List[int]:
        """
        Convert Python value ke list of 16-bit words untuk PLC.
        
        Args:
            value: Data yang akan di-convert
            data_type: "REAL", "ASCII", atau "boolean"
            length: Length dari data (untuk ASCII)
            scale: Scale factor (untuk REAL)
        
        Returns:
            List of 16-bit integer values
        """
        data_type = data_type.upper()
        
        if data_type == "BOOLEAN":
            # Boolean -> 0 atau 1 dalam 1 word
            return [1 if value else 0]
        
        elif data_type == "REAL":
            # REAL -> integer dengan scale factor
            scale = scale if scale else 1.0
            
            # Convert to integer
            if isinstance(value, (int, float)):
                int_value = int(value * scale)
            else:
                try:
                    int_value = int(float(value) * scale)
                except (ValueError, TypeError):
                    raise ValueError(f"Cannot convert {value} to REAL")
            
            # Ensure 16-bit signed integer range
            if int_value < -32768 or int_value > 32767:
                # If out of signed range, check unsigned range
                if int_value < 0 or int_value > 65535:
                    raise ValueError(f"Value {int_value} out of 16-bit range")
            
            return [int_value]
        
        elif data_type == "ASCII":
            # ASCII -> bytes, 2 bytes per word (big-endian)
            if not isinstance(value, str):
                value = str(value)
            
            # Calculate required words
            # Each word = 2 ASCII characters
            expected_words = int(length) if length else (len(value) + 1) // 2
            
            # Pad string to even length
            padded = value.ljust(expected_words * 2, "\x00")
            
            # Convert to words (2 chars = 1 word, big-endian)
            words = []
            for i in range(0, len(padded), 2):
                char1 = ord(padded[i]) if i < len(padded) else 0
                char2 = ord(padded[i + 1]) if i + 1 < len(padded) else 0
                word = (char1 << 8) | char2
                words.append(word)
            
            return words[:expected_words]
        
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
    
    def write_field(self, batch_name: str, field_name: str, value: Any) -> None:
        """
        Write single field ke PLC memory.
        
        Args:
            batch_name: Nama batch (e.g., "BATCH01")
            field_name: Informasi field (e.g., "NO-MO", "SILO ID 101")
            value: Nilai yang akan ditulis
        """
        if batch_name not in self.mapping:
            raise ValueError(f"Batch {batch_name} not found in mapping")
        
        # Find field definition
        field_def = None
        for item in self.mapping[batch_name]:
            if item["Informasi"] == field_name:
                field_def = item
                break
        
        if not field_def:
            raise ValueError(f"Field {field_name} not found in {batch_name}")
        
        # Parse address
        dm_str = field_def["DM"]
        address, expected_count = self._parse_dm_address(dm_str)
        
        # Convert value to words
        data_type = field_def["Data Type"]
        length = field_def.get("length")
        scale = field_def.get("scale")
        
        words = self._convert_to_words(value, data_type, length, scale)
        
        # Validate word count
        if len(words) != expected_count:
            logger.warning(
                f"Word count mismatch for {field_name}: expected {expected_count}, got {len(words)}. "
                f"Adjusting to match expected count."
            )
            # Pad or truncate to match expected count
            if len(words) < expected_count:
                words.extend([0] * (expected_count - len(words)))
            else:
                words = words[:expected_count]
        
        # Write to PLC
        self._write_to_plc(address, words)
        
        logger.info(f"Written {field_name} to DM {address}: {words} (value={value})")
    
    def write_batch(self, batch_name: str, data: Dict[str, Any]) -> None:
        """
        Write multiple fields ke PLC untuk satu batch.
        
        Args:
            batch_name: Nama batch (e.g., "BATCH01")
            data: Dictionary dengan key=field_name, value=data
        
        Example:
            write_batch("BATCH01", {
                "BATCH": 1,
                "NO-MO": "WH/MO/00002",
                "NO-BoM": "JF PLUS 25",
                "SILO ID 101 (SILO BESAR)": 101,
                "SILO 1 Consumption": 825.0,
            })
        """
        if batch_name not in self.mapping:
            raise ValueError(f"Batch {batch_name} not found in mapping")
        
        success_count = 0
        error_count = 0
        
        for field_name, value in data.items():
            try:
                self.write_field(batch_name, field_name, value)
                success_count += 1
            except Exception as exc:
                logger.error(f"Error writing {field_name}: {exc}")
                error_count += 1
        
        logger.info(
            f"Batch {batch_name} write completed: "
            f"{success_count} success, {error_count} errors"
        )
    
    def _write_to_plc(self, address: int, values: List[int]) -> None:
        """
        Low-level write ke PLC menggunakan FINS protocol.
        
        Args:
            address: DM address (e.g., 7000)
            values: List of 16-bit integer values
        """
        with FinsUdpClient(
            ip=self.settings.plc_ip,
            port=self.settings.plc_port,
            timeout_sec=self.settings.plc_timeout_sec,
        ) as client:
            # Build FINS write frame
            frame = build_memory_write_frame(
                area="DM",
                address=address,
                values=values,
                client_node=self.settings.client_node,
                plc_node=self.settings.plc_node,
                sid=0x00,
            )
            
            # Send frame
            client.send_raw_hex(frame.hex())
            
            # Receive response
            response = client.recv()
            
            # Parse response (raises exception on error)
            parse_memory_write_response(response.raw)
    
    def write_mo_batch_to_plc(self, mo_batch_data: Dict[str, Any], batch_number: int = 1) -> None:
        """
        Write data dari mo_batch table ke PLC.
        
        Args:
            mo_batch_data: Dictionary dengan data dari mo_batch table
            batch_number: Nomor batch (1-30) untuk menentukan BATCH01-BATCH30
        """
        if batch_number < 1 or batch_number > 30:
            raise ValueError(f"Batch number must be 1-30, got {batch_number}")
        
        batch_name = f"BATCH{batch_number:02d}"
        
        # Build PLC write data
        plc_data = {
            "BATCH": batch_number,
            "NO-MO": mo_batch_data.get("mo_id", ""),
            "NO-BoM": mo_batch_data.get("mo_id", ""),  # Could be different field
            "finished_goods": mo_batch_data.get("mo_id", ""),  # Product name if available
            "Quantity Goods_id": mo_batch_data.get("consumption", 0),
        }
        
        # Map silos (A-M -> 101-113)
        silo_letters = "abcdefghijklm"
        for idx, letter in enumerate(silo_letters):
            silo_number = 101 + idx
            
            # Silo ID
            silo_id_field = f"SILO ID {silo_number} (SILO BESAR)" if silo_number <= 103 else f"SILO ID {silo_number}"
            silo_value = mo_batch_data.get(f"silo_{letter}", silo_number)
            plc_data[silo_id_field] = silo_value
            
            # Silo Consumption
            consumption_field = f"SILO {idx + 1} Consumption" if silo_number <= 101 else f"SILO ID {silo_number} Consumption"
            consumption_value = mo_batch_data.get(f"consumption_silo_{letter}", 0)
            
            # Apply scale if consumption value exists
            if consumption_value:
                # Scale by 10 according to reference (scale: 10.0)
                plc_data[consumption_field] = float(consumption_value)
            else:
                plc_data[consumption_field] = 0
        
        # Status fields
        plc_data["status manufaturing"] = mo_batch_data.get("status_manufacturing", False)
        plc_data["Status Operation"] = mo_batch_data.get("status_operation", False)
        plc_data["weight_finished_good"] = mo_batch_data.get("actual_weight_quantity_finished_goods", 0)
        
        # Write to PLC
        self.write_batch(batch_name, plc_data)
        
        logger.info(f"MO batch data written to PLC {batch_name}: mo_id={mo_batch_data.get('mo_id')}")


# Singleton instance
_plc_write_service: Optional[PLCWriteService] = None


def get_plc_write_service() -> PLCWriteService:
    """Get singleton instance of PLCWriteService."""
    global _plc_write_service
    if _plc_write_service is None:
        _plc_write_service = PLCWriteService()
    return _plc_write_service
