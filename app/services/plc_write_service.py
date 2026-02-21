"""
PLC Write Service
Menggunakan MASTER_BATCH_REFERENCE.json sebagai mapping memory PLC.
Includes handshake logic to prevent overwriting unread data.
"""
import json
import logging
import math
import os
import re
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import build_memory_write_frame, parse_memory_write_response
from app.services.plc_handshake_service import get_handshake_service

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

    def _normalize_silo_number(self, raw_number: int) -> int:
        if raw_number < 100:
            return 100 + raw_number
        return raw_number

    def _build_silo_field_maps(self, batch_name: str) -> tuple[Dict[int, str], Dict[int, str]]:
        id_fields: Dict[int, str] = {}
        consumption_fields: Dict[int, str] = {}

        for item in self.mapping.get(batch_name, []):
            info = str(item.get("Informasi") or "")
            info_upper = info.upper()
            if "SILO" not in info_upper:
                continue

            match = re.search(r"SILO(?:\s+ID)?\s+(\d+)", info_upper)
            if not match:
                continue

            raw_number = int(match.group(1))
            silo_number = self._normalize_silo_number(raw_number)

            if "CONSUMPTION" in info_upper:
                consumption_fields[silo_number] = info
            else:
                id_fields[silo_number] = info

        return id_fields, consumption_fields
    
    def _convert_to_words(self, value: Any, data_type: str, length: Optional[float] = None, scale: Optional[float] = None, word_count: Optional[int] = None) -> List[int]:
        """
        Convert Python value ke list of 16-bit words untuk PLC.
        
        Args:
            value: Data yang akan di-convert
            data_type: "REAL", "ASCII", atau "boolean"
            length: Length dari data (untuk ASCII)
            scale: Scale factor (untuk REAL)
            word_count: Expected number of words (for multi-word values)
        
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
            
            # Determine if multi-word is needed
            # If word_count expected is 2+, use 32-bit signed integer (2 words)
            if word_count and word_count >= 2:
                # 32-bit signed range: -2147483648 to 2147483647
                if int_value < -2147483648 or int_value > 2147483647:
                    raise ValueError(f"Value {int_value} out of 32-bit range")
                
                # Split into 2 words (big-endian): high word, low word
                # For positive: high = value >> 16, low = value & 0xFFFF
                high_word = (int_value >> 16) & 0xFFFF
                low_word = int_value & 0xFFFF
                
                return [high_word, low_word]
            else:
                # Single word (16-bit) - use signed range
                if int_value < -32768 or int_value > 32767:
                    raise ValueError(f"Value {int_value} out of 16-bit signed range [-32768, 32767]")
                
                return [int_value & 0xFFFF]
        
        elif data_type == "ASCII":
            # ASCII -> bytes, 2 bytes per word (big-endian)
            if not isinstance(value, str):
                value = str(value)
            
            # Calculate required words
            # Each word = 2 ASCII characters
            if length:
                expected_words = int(math.ceil(float(length) / 2.0))
            else:
                expected_words = (len(value) + 1) // 2
            
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
        
        # Pass expected word count for proper multi-word handling
        words = self._convert_to_words(value, data_type, length, scale, word_count=expected_count)
        
        # Validate word count
        if len(words) != expected_count:
            # Use debug level for known cases where padding is expected
            log_level = logging.DEBUG if len(words) < expected_count else logging.WARNING
            logger.log(
                log_level,
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
    
    def write_batch(self, batch_name: str, data: Dict[str, Any], skip_handshake_check: bool = False) -> None:
        """
        Write multiple fields ke PLC untuk satu batch mengikuti MASTER_BATCH_REFERENCE.json.
        
        Args:
            batch_name: Nama batch (e.g., "BATCH01")
            data: Dictionary dengan key=field_name, value=data
            skip_handshake_check: If True, skip checking status_read_data (for testing only)
        
        Field names HARUS match dengan "Informasi" field di MASTER_BATCH_REFERENCE.json
        
        Handshake Logic:
            - Before writing, checks D7076 (status_read_data for WRITE area)
            - If D7076 = 0: PLC hasn't read previous batch yet, SKIP write to prevent overwrite
            - If D7076 = 1: PLC has read, safe to write new batch
            - After writing, D7076 is automatically set to 0 by Middleware
        
        Example:
            write_batch("BATCH01", {
                "BATCH": 1,
                "NO-MO": "WH/MO/00002",
                "NO-BoM": "JF SUPER 2A 25",
                "finished_goods": "JF SUPER 2A 25",
                "Quantity Goods_id": 2000000,
                "SILO ID 101 (SILO BESAR)": 101,
                "SILO ID 101 Consumption": 14415,
                ...
            })
        """
        if batch_name not in self.mapping:
            raise ValueError(f"Batch {batch_name} not found in MASTER_BATCH_REFERENCE mapping")
        
        # Handshake check: Verify PLC has read previous batch
        if not skip_handshake_check:
            handshake = get_handshake_service()
            plc_has_read = handshake.check_write_area_status()
            
            if not plc_has_read:
                logger.warning(
                    f"[{batch_name}] Handshake check failed: PLC hasn't read previous batch yet (D7076=0). "
                    f"Skipping write to prevent data overwrite. PLC will set D7076=1 when ready."
                )
                raise RuntimeError(
                    f"Cannot write {batch_name}: PLC handshake not ready (D7076=0). "
                    f"Wait for PLC to read current batch first."
                )
            
            logger.info(f"[{batch_name}] Handshake check passed: PLC ready for new batch (D7076=1)")
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        logger.info(f"[{batch_name}] Writing {len(data)} fields to PLC...")
        
        for field_name, value in data.items():
            try:
                # Find field in mapping
                field_def = None
                for item in self.mapping[batch_name]:
                    if item["Informasi"] == field_name:
                        field_def = item
                        break
                
                if not field_def:
                    logger.warning(
                        f"[{batch_name}] Field '{field_name}' not found in MASTER_BATCH_REFERENCE mapping. "
                        f"Available fields: {[item['Informasi'] for item in self.mapping[batch_name]]}"
                    )
                    skipped_count += 1
                    continue
                
                # Write field
                self.write_field(batch_name, field_name, value)
                success_count += 1
                
            except Exception as exc:
                logger.error(
                    f"[{batch_name}] Error writing field '{field_name}' with value {value}: {exc}",
                    exc_info=True
                )
                error_count += 1
        
        # After successful write, reset handshake flag to 0
        # (indicating Middleware has written new data, PLC should read it)
        if not skip_handshake_check and error_count == 0:
            handshake = get_handshake_service()
            handshake.reset_write_area_status()  # Set D7076 = 0
            logger.info(f"[{batch_name}] Reset handshake flag (D7076=0) - waiting for PLC to read")
        
        logger.info(
            f"[{batch_name}] Write completed: "
            f"✓ {success_count} success, "
            f"⚠ {skipped_count} skipped, "
            f"✗ {error_count} errors"
        )
        
        if error_count > 0:
            raise RuntimeError(
                f"Failed to write {batch_name}: {error_count} field(s) failed. "
                f"Check logs for details."
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
        Write data dari mo_batch table ke PLC mengikuti MASTER_BATCH_REFERENCE.json mapping.
        
        Args:
            mo_batch_data: Dictionary dengan data dari mo_batch table
            batch_number: Nomor batch (1-30) yang menentukan BATCH01-BATCH30
        
        Field mapping:
            - BATCH: Nomor slot batch (1-30)
            - NO-MO: Manufacturing Order ID (ASCII 16 chars)
            - NO-BoM: Bill of Materials / Finished Goods (ASCII 16 chars)
            - finished_goods: Nama finished goods (ASCII 16 chars)
            - Quantity Goods_id: Target quantity (REAL)
            - SILO ID 101-113: Silo IDs per silo (REAL)
            - SILO ID XX Consumption: Target consumption per silo (REAL)
            - status_manufacturing: Status selesai (0/1)
            - Status Operation: Status operasi (0/1)
            - weight_finished_good: Actual weight hasil (REAL)
        """
        if batch_number < 1 or batch_number > 30:
            raise ValueError(f"Batch number must be 1-30, got {batch_number}")
        
        batch_name = f"BATCH{batch_number:02d}"
        
        # Build PLC write data following MASTER_BATCH_REFERENCE.json mapping
        # Truncate strings to 16 chars for ASCII fields (8 words max)
        mo_id = str(mo_batch_data.get("mo_id", ""))[:16]
        finished_goods = str(mo_batch_data.get("finished_goods") or mo_batch_data.get("mo_id", ""))[:16]
        
        plc_data = {
            "BATCH": batch_number,
            "NO-MO": mo_id,
            "NO-BoM": finished_goods,
            "finished_goods": finished_goods,
            "Quantity Goods_id": mo_batch_data.get("consumption", 0),
        }
        
        # Map silos (A-M -> 101-113)
        silo_id_fields, consumption_fields = self._build_silo_field_maps(batch_name)
        silo_letters = "abcdefghijklm"
        for idx, letter in enumerate(silo_letters):
            silo_number = 101 + idx

            # Silo ID field name from reference (e.g., "SILO ID 101 (SILO BESAR)")
            silo_id_field = silo_id_fields.get(silo_number)
            if silo_id_field:
                silo_value = mo_batch_data.get(f"silo_{letter}", silo_number)
                plc_data[silo_id_field] = silo_value
                logger.debug(f"Set {silo_id_field} = {silo_value}")
            else:
                logger.debug(f"Silo ID field not found for {silo_number} in {batch_name}")

            # Silo Consumption field name from reference (e.g., "SILO ID 101 Consumption")
            consumption_field = consumption_fields.get(silo_number)
            if consumption_field:
                consumption_value = mo_batch_data.get(f"consumption_silo_{letter}", 0)
                plc_data[consumption_field] = float(consumption_value) if consumption_value else 0
                logger.debug(f"Set {consumption_field} = {plc_data[consumption_field]}")
            else:
                logger.debug(f"Silo consumption field not found for {silo_number} in {batch_name}")
        
        # Write status fields (Note: field names must match MASTER_BATCH_REFERENCE exactly)
        # Check mapping for actual field names
        for item in self.mapping.get(batch_name, []):
            info = item.get("Informasi", "").lower()
            
            if "status" in info and "manufacturing" in info:
                plc_data[item["Informasi"]] = mo_batch_data.get("status_manufacturing", False)
                logger.debug(f"Set status field: {item['Informasi']} = {plc_data[item['Informasi']]}")
            
            if "status" in info and "operation" in info:
                plc_data[item["Informasi"]] = mo_batch_data.get("status_operation", False)
                logger.debug(f"Set operation field: {item['Informasi']} = {plc_data[item['Informasi']]}")
            
            if "weight" in info and "finished" in info:
                plc_data[item["Informasi"]] = mo_batch_data.get("actual_weight_quantity_finished_goods", 0)
                logger.debug(f"Set weight field: {item['Informasi']} = {plc_data[item['Informasi']]}")
        
        # Write to PLC
        self.write_batch(batch_name, plc_data)
        
        logger.info(
            f"✓ MO batch data written to PLC {batch_name}: "
            f"mo_id={mo_batch_data.get('mo_id')}, "
            f"batch={batch_number}/30, "
            f"fields={len(plc_data)}"
        )


# Singleton instance
_plc_write_service: Optional[PLCWriteService] = None


def get_plc_write_service() -> PLCWriteService:
    """Get singleton instance of PLCWriteService."""
    global _plc_write_service
    if _plc_write_service is None:
        _plc_write_service = PLCWriteService()
    return _plc_write_service
