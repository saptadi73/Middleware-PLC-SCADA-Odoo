"""
PLC Handshake Service

Manages handshaking between Middleware and PLC through status_read_data flags.

READ Area Handshaking (D6075):
- Middleware reads data from PLC (D6001-D6074)
- After successful read, Middleware sets D6075 = 1 (mark as read)
- PLC sees D6075=1 and prepares next data cycle
- PLC resets D6075 back to 0 when ready for next read

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
import socket
import time
from typing import Literal, Optional

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
    READ_AREA_STATUS_ADDRESS = 6075  # D6075 for READ area handshake
    WRITE_AREA_STATUS_ADDRESS = 7076  # D7076 for WRITE/BATCH area handshake  
    EQUIPMENT_FAILURE_STATUS_ADDRESS = 8022  # D8022 for equipment failure handshake
    
    def __init__(self):
        self.settings = get_settings()
    
    def check_write_area_status(self) -> bool:
        """
        Check if PLC has read the batch data (WRITE area).
        
        Returns:
            True: PLC has read (D7076 = 1), safe to write new batch
            False: PLC hasn't read yet (D7076 = 0), should NOT write
        """
        try:
            status = self._read_status_flag(self.WRITE_AREA_STATUS_ADDRESS)
            
            if status == 1:
                logger.info("✓ WRITE area handshake: PLC has read batch data (D7076=1). Safe to write.")
                return True
            else:
                logger.warning("⚠ WRITE area handshake: PLC hasn't read yet (D7076=0). Skip write to avoid overwrite.")
                return False
                
        except Exception as exc:
            logger.error(f"Error checking WRITE area status: {exc}", exc_info=True)
            # Default to False (safer - don't write if status unknown)
            return False
    
    def mark_read_area_as_read(self) -> bool:
        """
        Mark READ area as read by Middleware (set D6075 = 1).
        
        Called after successfully reading data from PLC READ area (D6001-D6074).
        This tells PLC that Middleware has processed the data.
        
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            self._write_status_flag(self.READ_AREA_STATUS_ADDRESS, 1)
            logger.info("✓ Marked READ area as read (D6075=1)")
            return True
        except Exception as exc:
            logger.error(f"Error marking READ area as read: {exc}", exc_info=True)
            return False
    
    def check_read_area_status(self) -> bool:
        """
        Check READ area status flag.
        
        Returns:
            True: Middleware has already read (D6075=1)
            False: Not yet read (D6075=0)
        """
        try:
            status = self._read_status_flag(self.READ_AREA_STATUS_ADDRESS)
            return status == 1
        except Exception as exc:
            logger.error(f"Error checking READ area status: {exc}", exc_info=True)
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
            logger.info("✓ Marked equipment failure as read (D8022=1)")
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
    
    def reset_write_area_status(self) -> bool:
        """
        Reset WRITE area status to 0 (for testing purposes).
        
        Normally this is done by PLC after it finishes reading.
        
        Returns:
            True if successfully reset, False otherwise
        """
        try:
            self._write_status_flag(self.WRITE_AREA_STATUS_ADDRESS, 0)
            logger.info("✓ Reset WRITE area status (D7076=0)")
            return True
        except Exception as exc:
            logger.error(f"Error resetting WRITE area status: {exc}", exc_info=True)
            return False
    
    def reset_read_area_status(self) -> bool:
        """
        Reset READ area status to 0 (for testing purposes).
        
        Normally this is done by PLC after preparing next data.
        
        Returns:
            True if successfully reset, False otherwise
        """
        try:
            self._write_status_flag(self.READ_AREA_STATUS_ADDRESS, 0)
            logger.info("✓ Reset READ area status (D6075=0)")
            return True
        except Exception as exc:
            logger.error(f"Error resetting READ area status: {exc}", exc_info=True)
            return False
    
    def reset_equipment_failure_status(self) -> bool:
        """
        Reset equipment failure status to 0 (for testing purposes).
        
        Returns:
            True if successfully reset, False otherwise
        """
        try:
            self._write_status_flag(self.EQUIPMENT_FAILURE_STATUS_ADDRESS, 0)
            logger.info("✓ Reset equipment failure status (D8022=0)")
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
        max_attempts = 3
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                with FinsUdpClient(
                    ip=self.settings.plc_ip,
                    port=self.settings.plc_port,
                    timeout_sec=self.settings.plc_timeout_sec,
                ) as client:
                    request = MemoryReadRequest(area="DM", address=address, count=1)
                    frame = build_memory_read_frame(
                        request,
                        self.settings.client_node,
                        self.settings.plc_node,
                        sid=0x00,
                    )

                    client.send_raw_hex(frame.hex())
                    response = client.recv()
                    words = parse_memory_read_response(response.raw, expected_count=1)

                    if not words:
                        raise ValueError(f"No data returned from address D{address}")

                    return 1 if words[0] != 0 else 0
            except (TimeoutError, socket.timeout) as exc:
                last_error = exc
                if attempt < max_attempts:
                    logger.warning(
                        "Handshake read timeout at D%s (attempt %s/%s). Retrying...",
                        address,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(0.1)
                    continue
                break

        raise RuntimeError(
            f"Handshake read timeout at D{address} after {max_attempts} attempts"
        ) from last_error
    
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
