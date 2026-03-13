"""
PLC Handshake Service

Manages handshaking between Middleware and PLC through status_read_data flags.

READ Area Handshaking (per-batch status_read_data):
- Middleware reads data from PLC per batch READ area
- After successful read, Middleware sets status_read_data for that batch:
  BATCH 01..10 -> D6076, D6176, ..., D6976
- PLC sees status_read_data=1 and prepares next data cycle
- PLC resets status_read_data back to 0 when ready for next read

WRITE Area Handshaking (D7076):
- Middleware writes batch data to PLC (D7000-D7075)
- After successful write, Middleware checks D7076
- If D7076 = 1: PLC already read the data, safe to write new batch
- If D7076 = 0: PLC hasn't read yet, skip writing to avoid overwrite
- PLC sets D7076 = 1 after reading batch data

Equipment Failure Handshaking (D8022):
- Similar to READ area handshaking
- Middleware reads failure data, then sets D8022 = 1
- PLC resets D8022 = 0 when ready for next failure report
"""
import json
import logging
from pathlib import Path
import re
import socket
import time
from typing import Dict, Literal, Optional

from app.core.config import get_settings
from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    build_memory_read_frame,
    build_memory_write_frame,
    parse_memory_read_response,
    parse_memory_write_response,
    MemoryReadRequest,
)

logger = logging.getLogger(__name__)


class PLCHandshakeService:
    """Service for managing PLC handshake flags (status_read_data)."""
    
    # Memory addresses for status_read_data flags
    WRITE_AREA_STATUS_ADDRESS = 7076  # D7076 for WRITE/BATCH area handshake  
    EQUIPMENT_FAILURE_STATUS_ADDRESS = 8022  # D8022 for equipment failure handshake
    MANUAL_WEIGHING_STATUS_ADDRESS = 9013  # default fallback; can be overridden by reference
    READ_BATCH_STATUS_START = 6076  # BATCH_READ_01 status_read_data
    READ_BATCH_STATUS_STEP = 100    # Per-batch offset
    READ_BATCH_MIN = 1
    READ_BATCH_MAX = 10
    
    def __init__(self):
        self.settings = get_settings()
        self._read_status_by_batch: Dict[int, int] = {}
        self._write_status_by_batch: Dict[int, int] = {}
        self._write_mo_field_by_batch: Dict[int, tuple[int, int]] = {}
        self._manual_weighing_status_address = self.MANUAL_WEIGHING_STATUS_ADDRESS
        self._load_read_status_addresses_from_mapping()
        self._load_write_addresses_from_mapping()
        self._load_manual_weighing_status_address_from_mapping()

    def _load_read_status_addresses_from_mapping(self) -> None:
        """Load per-batch status_read_data addresses from READ_DATA_PLC_MAPPING.json."""
        reference_path = Path(__file__).parent.parent / "reference" / "READ_DATA_PLC_MAPPING.json"
        if not reference_path.exists():
            logger.warning(
                "READ_DATA_PLC_MAPPING.json not found at %s; using handshake fallback addresses",
                reference_path,
            )
            return

        try:
            data = json.loads(reference_path.read_text(encoding="utf-8"))
            loaded_count = 0
            for batch_no in range(self.READ_BATCH_MIN, self.READ_BATCH_MAX + 1):
                key = f"BATCH_READ_{batch_no:02d}"
                fields = data.get(key, [])
                for field in fields:
                    info = str(field.get("Informasi") or "").strip().lower()
                    if info != "status_read_data":
                        continue

                    dm = str(field.get("DM") or field.get("DM - Memory") or "").strip().upper()
                    match = re.match(r"D(\d+)", dm)
                    if not match:
                        continue

                    self._read_status_by_batch[batch_no] = int(match.group(1))
                    loaded_count += 1
                    break

            if loaded_count:
                logger.info("Loaded READ handshake addresses from mapping: %s batch(es)", loaded_count)
            else:
                logger.warning("No status_read_data addresses found in READ mapping; using fallback addresses")
        except Exception as exc:
            logger.warning(
                "Failed loading READ handshake addresses from mapping: %s. Using fallback addresses.",
                exc,
            )
    
    def check_write_area_status(self) -> bool:
        """
        Check if PLC has read the batch data (WRITE area).
        
        Returns:
            True: PLC has read (D7076 = 1), safe to write new batch
            False: PLC hasn't read yet (D7076 = 0), should NOT write
        """
        try:
            primary_status = self._read_status_flag(self.WRITE_AREA_STATUS_ADDRESS)

            if primary_status == 1:
                logger.info(
                    "WRITE area handshake: PLC has read batch data (D7076=1). Safe to write."
                )
                return True

            status_map = self._read_all_write_status_flags()
            occupied_slots = self._get_non_empty_write_mo_slots()
            has_any_status_read = any(flag == 1 for flag in status_map.values())

            if not occupied_slots and not has_any_status_read:
                logger.warning(
                    "WRITE area handshake: D7076=0 but WRITE queue appears empty/clean "
                    "(all status_read_data=0 and NO-MO empty). Treating as READY for initial write."
                )
                return True

            logger.warning(
                "WRITE area handshake: not ready (D7076=0). occupied_slots=%s, any_status_read=%s",
                occupied_slots,
                has_any_status_read,
            )
            return False

        except Exception as exc:
            logger.error(f"Error checking WRITE area status: {exc}", exc_info=True)
            # Default to False (safer - don't write if status unknown)
            return False

    def _load_write_addresses_from_mapping(self) -> None:
        """Load WRITE status_read_data and NO-MO addresses from MASTER_BATCH_REFERENCE.json."""
        reference_path = Path(__file__).parent.parent / "reference" / "MASTER_BATCH_REFERENCE.json"
        if not reference_path.exists():
            logger.warning(
                "MASTER_BATCH_REFERENCE.json not found at %s; using D7076-only handshake check",
                reference_path,
            )
            return

        try:
            data = json.loads(reference_path.read_text(encoding="utf-8"))
            loaded_status = 0
            loaded_mo = 0
            for key, fields in data.items():
                match_key = re.match(r"(?:WRITE_)?BATCH(\d+)$", str(key).strip().upper())
                if not match_key:
                    continue

                batch_no = int(match_key.group(1))
                for field in fields:
                    info = str(field.get("Informasi") or "").strip().lower()
                    dm = str(field.get("DM") or field.get("DM - Memory") or "").strip().upper()
                    if not dm:
                        continue

                    if info == "status_read_data":
                        status_match = re.match(r"D(\d+)", dm)
                        if status_match:
                            self._write_status_by_batch[batch_no] = int(status_match.group(1))
                            loaded_status += 1
                    elif info == "no-mo":
                        try:
                            self._write_mo_field_by_batch[batch_no] = self._parse_dm_range(dm)
                            loaded_mo += 1
                        except ValueError:
                            continue

            if loaded_status:
                logger.info("Loaded WRITE handshake status addresses from mapping: %s batch(es)", loaded_status)
            else:
                logger.warning(
                    "No WRITE status_read_data addresses found in MASTER mapping; using D7076-only handshake check"
                )

            if loaded_mo:
                logger.info("Loaded WRITE NO-MO addresses from mapping: %s batch(es)", loaded_mo)
            else:
                logger.warning("No WRITE NO-MO addresses found in MASTER mapping")

        except Exception as exc:
            logger.warning(
                "Failed loading WRITE handshake/NO-MO addresses from mapping: %s. "
                "Using D7076-only handshake check.",
                exc,
            )

    def _load_manual_weighing_status_address_from_mapping(self) -> None:
        """Load manual weighing handshake address from ADDITIONAL_EQUIPMENT_REFERENCE.json."""
        reference_path = Path(__file__).parent.parent / "reference" / "ADDITIONAL_EQUIPMENT_REFERENCE.json"
        if not reference_path.exists():
            logger.warning(
                "ADDITIONAL_EQUIPMENT_REFERENCE.json not found at %s; using fallback manual handshake address D%s",
                reference_path,
                self._manual_weighing_status_address,
            )
            return

        try:
            data = json.loads(reference_path.read_text(encoding="utf-8"))
            fields = data.get("ADDITIONAL", [])
            for field in fields:
                info = str(field.get("Informasi") or "").strip().lower()
                if info != "status_manual_weigh_read":
                    continue

                dm = str(field.get("DM") or field.get("DM - Memory") or "").strip().upper()
                match = re.match(r"D(\d+)", dm)
                if not match:
                    continue

                self._manual_weighing_status_address = int(match.group(1))
                logger.info(
                    "Loaded manual weighing handshake address from reference: D%s",
                    self._manual_weighing_status_address,
                )
                return

            logger.warning(
                "status_manual_weigh_read not found in ADDITIONAL reference; using fallback D%s",
                self._manual_weighing_status_address,
            )
        except Exception as exc:
            logger.warning(
                "Failed loading manual weighing handshake address from reference: %s. Using fallback D%s",
                exc,
                self._manual_weighing_status_address,
            )

    def _parse_dm_range(self, dm_str: str) -> tuple[int, int]:
        """Parse DM string to (start_address, word_count)."""
        dm_clean = dm_str.strip().upper()
        if "-" not in dm_clean:
            single_match = re.match(r"D(\d+)", dm_clean)
            if not single_match:
                raise ValueError(f"Invalid DM format: {dm_str}")
            return int(single_match.group(1)), 1

        range_match = re.match(r"D(\d+)-(\d+)", dm_clean)
        if not range_match:
            raise ValueError(f"Invalid DM range format: {dm_str}")

        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if end < start:
            raise ValueError(f"Invalid DM range order: {dm_str}")
        return start, (end - start + 1)

    def _read_words(self, address: int, count: int) -> list[int]:
        """Read multiple words from PLC DM area with retry."""
        max_attempts = 3
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                with FinsUdpClient(
                    ip=self.settings.plc_ip,
                    port=self.settings.plc_port,
                    timeout_sec=self.settings.plc_timeout_sec,
                ) as client:
                    request = MemoryReadRequest(area="DM", address=address, count=count)
                    frame = build_memory_read_frame(
                        request,
                        self.settings.client_node,
                        self.settings.plc_node,
                        sid=0x00,
                    )

                    client.send_raw_hex(frame.hex())
                    response = client.recv()
                    words = parse_memory_read_response(response.raw, expected_count=count)

                    if len(words) != count:
                        raise ValueError(
                            f"Unexpected word count from D{address}: expected={count}, got={len(words)}"
                        )
                    return words
            except (TimeoutError, socket.timeout, ValueError) as exc:
                last_error = exc
                if attempt < max_attempts:
                    logger.warning(
                        "Handshake multi-read timeout/error at D%s count=%s (attempt %s/%s). Retrying...",
                        address,
                        count,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(0.1)
                    continue
                break

        raise RuntimeError(
            f"Handshake multi-read failed at D{address} (count={count}) after {max_attempts} attempts"
        ) from last_error

    def _read_all_write_status_flags(self) -> Dict[int, int]:
        """Read all mapped WRITE status_read_data flags by batch number."""
        statuses: Dict[int, int] = {}
        for batch_no, address in sorted(self._write_status_by_batch.items()):
            try:
                statuses[batch_no] = self._read_status_flag(address)
            except Exception as exc:
                logger.warning(
                    "Failed reading WRITE status_read_data for batch %s at D%s: %s",
                    batch_no,
                    address,
                    exc,
                )
                statuses[batch_no] = 0
        return statuses

    def _decode_ascii_words(self, words: list[int]) -> str:
        """Decode ASCII words (big-endian 2 chars/word) to trimmed text."""
        raw_bytes = bytearray()
        for word in words:
            raw_bytes.append((word >> 8) & 0xFF)
            raw_bytes.append(word & 0xFF)
        return raw_bytes.decode("ascii", errors="ignore").replace("\x00", "").strip()

    def _get_non_empty_write_mo_slots(self) -> list[int]:
        """Return WRITE batch numbers whose NO-MO field is not empty."""
        occupied: list[int] = []
        for batch_no, (address, word_count) in sorted(self._write_mo_field_by_batch.items()):
            try:
                words = self._read_words(address, word_count)
                mo_text = self._decode_ascii_words(words)
                if mo_text:
                    occupied.append(batch_no)
            except Exception as exc:
                logger.warning(
                    "Failed reading WRITE NO-MO for batch %s at D%s: %s",
                    batch_no,
                    address,
                    exc,
                )
        return occupied
    
    def _get_read_status_address(self, batch_no: int) -> int:
        """Resolve READ status_read_data address for batch number (1..10)."""
        if batch_no < self.READ_BATCH_MIN or batch_no > self.READ_BATCH_MAX:
            raise ValueError(
                f"batch_no must be {self.READ_BATCH_MIN}..{self.READ_BATCH_MAX}, got {batch_no}"
            )
        mapped_address = self._read_status_by_batch.get(batch_no)
        if mapped_address is not None:
            return mapped_address
        return self.READ_BATCH_STATUS_START + (
            (batch_no - self.READ_BATCH_MIN) * self.READ_BATCH_STATUS_STEP
        )

    def mark_read_area_as_read(self, batch_no: int = 1) -> bool:
        """
        Mark READ area as read by Middleware (set per-batch status_read_data = 1).
        
        Called after successfully reading data from PLC READ area for a specific batch.
        This tells PLC that Middleware has processed the data.
        
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            address = self._get_read_status_address(batch_no)
            self._write_status_flag(address, 1)
            logger.info("Marked READ area batch %s as read (D%s=1)", batch_no, address)
            return True
        except Exception as exc:
            logger.error(f"Error marking READ area batch as read: {exc}", exc_info=True)
            return False
    
    def check_read_area_status(self, batch_no: int = 1) -> bool:
        """
        Check READ area status flag.
        
        Returns:
            True: Middleware has already read (status_read_data=1)
            False: Not yet read (status_read_data=0)
        """
        try:
            status = self._read_status_flag(self._get_read_status_address(batch_no))
            return status == 1
        except Exception as exc:
            logger.error(f"Error checking READ area batch status: {exc}", exc_info=True)
            return False
    
    def mark_equipment_failure_as_read(self) -> bool:
        """
        Mark equipment failure data as read by Middleware (set D8022 = 1).
        
        Called after successfully reading equipment failure from PLC.
        
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            self._write_status_flag(self.EQUIPMENT_FAILURE_STATUS_ADDRESS, 1)
            logger.info("Marked equipment failure as read (D8022=1)")
            return True
        except Exception as exc:
            logger.error(f"Error marking equipment failure as read: {exc}", exc_info=True)
            return False
    
    def check_equipment_failure_status(self) -> bool:
        """
        Check equipment failure status flag.
        
        Returns:
            True: Middleware has already read (D8022=1)
            False: Not yet read (D8022=0)
        """
        try:
            status = self._read_status_flag(self.EQUIPMENT_FAILURE_STATUS_ADDRESS)
            return status == 1
        except Exception as exc:
            logger.error(f"Error checking equipment failure status: {exc}", exc_info=True)
            return False
    
    def mark_manual_weighing_as_read(self) -> bool:
        """
        Mark manual weighing data as read by Middleware (set configured handshake address = 1).
        
        Called after successfully reading and syncing manual weighing data to Odoo.
        This tells PLC that Middleware has processed the weighing data.
        
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            self._write_status_flag(self._manual_weighing_status_address, 1)
            logger.info("Marked manual weighing as read (D%s=1)", self._manual_weighing_status_address)
            return True
        except Exception as exc:
            logger.error(f"Error marking manual weighing as read: {exc}", exc_info=True)
            return False
    
    def check_manual_weighing_status(self) -> bool:
        """
        Check manual weighing status flag.
        
        Returns:
            True: Middleware has already read (address=1)
            False: Not yet read (address=0)
        """
        try:
            status = self._read_status_flag(self._manual_weighing_status_address)
            return status == 1
        except Exception as exc:
            logger.error(f"Error checking manual weighing status: {exc}", exc_info=True)
            return False
    
    def reset_manual_weighing_status(self) -> bool:
        """
        Reset manual weighing status to 0 (for testing purposes).
        
        Returns:
            True if successfully reset, False otherwise
        """
        try:
            self._write_status_flag(self._manual_weighing_status_address, 0)
            logger.info("Reset manual weighing status (D%s=0)", self._manual_weighing_status_address)
            return True
        except Exception as exc:
            logger.error(f"Error resetting manual weighing status: {exc}", exc_info=True)
            return False

    def mark_all_write_areas_as_ready(self) -> list[int]:
        """
        Mark all mapped WRITE-area status_read_data flags as ready (set to 1).

        This is used when the system must be restarted from a clean state and
        TASK 1 needs the PLC WRITE area handshake to allow a fresh write cycle.

        Returns:
            List of DM addresses that were updated to 1.
        """
        addresses = sorted(
            {self.WRITE_AREA_STATUS_ADDRESS, *self._write_status_by_batch.values()}
        )

        for address in addresses:
            self._write_status_flag(address, 1)

        logger.info(
            "Marked WRITE area handshake as ready on %s address(es): %s",
            len(addresses),
            ", ".join(f"D{address}" for address in addresses),
        )
        return addresses
    
    def reset_write_area_status(self) -> bool:
        """
        Reset WRITE area status to 0 (for testing purposes).
        
        Normally this is done by PLC after it finishes reading.
        
        Returns:
            True if successfully reset, False otherwise
        """
        try:
            self._write_status_flag(self.WRITE_AREA_STATUS_ADDRESS, 0)
            logger.info("Reset WRITE area status (D7076=0)")
            return True
        except Exception as exc:
            logger.error(f"Error resetting WRITE area status: {exc}", exc_info=True)
            return False
    
    def reset_read_area_status(self, batch_no: int = 1) -> bool:
        """
        Reset READ area status to 0 for a specific batch (for testing purposes).
        
        Normally this is done by PLC after preparing next data.
        
        Returns:
            True if successfully reset, False otherwise
        """
        try:
            address = self._get_read_status_address(batch_no)
            self._write_status_flag(address, 0)
            logger.info("Reset READ area status batch %s (D%s=0)", batch_no, address)
            return True
        except Exception as exc:
            logger.error(f"Error resetting READ area batch status: {exc}", exc_info=True)
            return False
    
    def reset_equipment_failure_status(self) -> bool:
        """
        Reset equipment failure status to 0 (for testing purposes).
        
        Returns:
            True if successfully reset, False otherwise
        """
        try:
            self._write_status_flag(self.EQUIPMENT_FAILURE_STATUS_ADDRESS, 0)
            logger.info("Reset equipment failure status (D8022=0)")
            return True
        except Exception as exc:
            logger.error(f"Error resetting equipment failure status: {exc}", exc_info=True)
            return False
    def _read_status_flag(self, address: int) -> int:
        """
        Read a single status flag from PLC.
        
        Args:
            address: DM address (e.g., 6077, 7076, 8022)
        
        Returns:
            0 or 1 (status flag value)
        """
        words = self._read_words(address, 1)
        if not words:
            raise RuntimeError(f"Handshake read failed: empty response at D{address}")
        return 1 if words[0] != 0 else 0
    
    def _write_status_flag(self, address: int, value: int) -> None:
        """
        Write a status flag to PLC.
        
        Args:
            address: DM address (e.g., 6077, 7076, 8022)
            value: 0 or 1
        """
        if value not in (0, 1):
            raise ValueError(f"Status flag must be 0 or 1, got {value}")
        
        max_attempts = 3
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                with FinsUdpClient(
                    ip=self.settings.plc_ip,
                    port=self.settings.plc_port,
                    timeout_sec=self.settings.plc_timeout_sec,
                ) as client:
                    frame = build_memory_write_frame(
                        area="DM",
                        address=address,
                        values=[value],
                        client_node=self.settings.client_node,
                        plc_node=self.settings.plc_node,
                        sid=0x00,
                    )

                    client.send_raw_hex(frame.hex())
                    response = client.recv()
                    parse_memory_write_response(response.raw)
                return
            except (TimeoutError, socket.timeout) as exc:
                last_error = exc
                if attempt < max_attempts:
                    logger.warning(
                        "Handshake write timeout at D%s (attempt %s/%s). Retrying...",
                        address,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(0.1)
                    continue
                break

        raise RuntimeError(
            f"Handshake write timeout at D{address} after {max_attempts} attempts"
        ) from last_error


# Singleton instance
_handshake_service: Optional[PLCHandshakeService] = None


def get_handshake_service() -> PLCHandshakeService:
    """Get singleton instance of PLCHandshakeService."""
    global _handshake_service
    if _handshake_service is None:
        _handshake_service = PLCHandshakeService()
    return _handshake_service
