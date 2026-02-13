"""
PLC Sync Service - Periodic read and update of mo_batch from PLC data
Reads data from PLC and updates mo_batch records based on MO_ID.
Only updates if values have changed to avoid unnecessary database operations.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_read_service import get_plc_read_service

logger = logging.getLogger(__name__)


class PLCSyncService:
    """Service to sync PLC data to mo_batch table"""

    def __init__(self):
        self.plc_read_service = get_plc_read_service()

    def sync_from_plc(self) -> Dict[str, Any]:
        """
        Read data from PLC and update mo_batch if values changed.

        Returns:
            Dict with sync results (updated count, errors, etc.)
        """
        mo_id = None
        try:
            # Read all data from PLC
            plc_data = self.plc_read_service.read_batch_data()

            # Extract MO_ID from PLC
            mo_id = plc_data.get("mo_id", "").strip()
            if not mo_id:
                return {
                    "success": False,
                    "error": "No MO_ID found in PLC data",
                    "mo_id": None,
                }

            # Find mo_batch record by mo_id
            with SessionLocal() as session:
                result = session.execute(
                    select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
                )
                batch = result.scalar_one_or_none()

                if not batch:
                    return {
                        "success": False,
                        "error": f"MO batch not found for MO_ID: {mo_id}",
                        "mo_id": mo_id,
                    }

                # Check if data has changed and update
                updated = self._update_batch_if_changed(
                    session, batch, plc_data
                )

                if updated:
                    session.commit()
                    logger.info(f"Updated mo_batch for MO_ID: {mo_id}")
                    return {
                        "success": True,
                        "updated": True,
                        "mo_id": mo_id,
                        "message": "Batch data updated successfully",
                    }
                else:
                    return {
                        "success": True,
                        "updated": False,
                        "mo_id": mo_id,
                        "message": "No changes detected, skip update",
                    }

        except Exception as e:
            logger.error(f"Error syncing from PLC: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "mo_id": mo_id,
            }

    def _update_batch_if_changed(
        self, session: Session, batch: TableSmoBatch, plc_data: Dict[str, Any]
    ) -> bool:
        """
        Update batch fields if values have changed.

        Args:
            session: Database session
            batch: mo_batch record to update
            plc_data: Data read from PLC

        Returns:
            True if any field was updated, False otherwise
        """
        changed = False

        # Support both old and new payload shapes from PLCReadService.
        # Current read_batch_data() returns:
        # - quantity
        # - status: {manufacturing, operation}
        # - weight_finished_good
        status_payload = plc_data.get("status")
        status_obj = status_payload if isinstance(status_payload, dict) else {}

        # Map silo letters to consumption values from PLC
        silo_map = {
            "a": "SILO 1 Consumption",
            "b": "SILO 2 Consumption",
            "c": "SILO ID 103 Consumption",
            "d": "SILO ID 104 Consumption",
            "e": "SILO ID 105 Consumption",
            "f": "SILO ID 106  Consumption",
            "g": "SILO ID 107 Consumption",
            "h": "SILO 108 Consumption",
            "i": "SILO ID 109 Consumption",
            "j": "SILO ID 110 Consumption",
            "k": "SILO ID 111 Consumption",
            "l": "SILO ID 112 Consumption",
            "m": "SILO ID 113 Consumption",
        }

        # Update actual consumption for each silo
        silos = plc_data.get("silos", {})
        for letter, field_name in silo_map.items():
            silo_data = silos.get(letter, {})
            new_consumption = silo_data.get("consumption")

            if new_consumption is not None:
                attr_name = f"actual_consumption_silo_{letter}"
                current_value = getattr(batch, attr_name)

                # Update if value changed
                if current_value != new_consumption:
                    setattr(batch, attr_name, new_consumption)
                    changed = True
                    logger.debug(
                        f"Updated {attr_name}: {current_value} → {new_consumption}"
                    )

        # Update actual weight quantity finished goods
        new_quantity = plc_data.get("weight_finished_good")
        if new_quantity is None:
            # Backward compatibility with previous key naming
            new_quantity = plc_data.get("quantity_goods")
        if new_quantity is not None:
            if batch.actual_weight_quantity_finished_goods != new_quantity:
                batch.actual_weight_quantity_finished_goods = new_quantity
                changed = True
                logger.debug(
                    f"Updated actual_weight_quantity_finished_goods: "
                    f"{batch.actual_weight_quantity_finished_goods} → {new_quantity}"
                )

        # Update status fields
        new_status_mfg = status_obj.get("manufacturing")
        if new_status_mfg is None:
            # Backward compatibility with previous key naming
            new_status_mfg = plc_data.get("status_manufacturing")
        if new_status_mfg is not None:
            # Convert to boolean
            status_bool = bool(new_status_mfg)
            current_status: bool = batch.status_manufacturing  # type: ignore
            if current_status != status_bool:
                batch.status_manufacturing = status_bool  # type: ignore
                changed = True
                logger.debug(
                    f"Updated status_manufacturing: "
                    f"{current_status} → {status_bool}"
                )

        new_status_op = status_obj.get("operation")
        if new_status_op is None:
            # Backward compatibility with previous key naming
            new_status_op = plc_data.get("status_operation")
        if new_status_op is not None:
            status_bool = bool(new_status_op)
            current_status_op: bool = batch.status_operation  # type: ignore
            if current_status_op != status_bool:
                batch.status_operation = status_bool  # type: ignore
                changed = True
                logger.debug(
                    f"Updated status_operation: " f"{current_status_op} → {status_bool}"
                )

        # Always update timestamp if any field changed
        if changed:
            batch.last_read_from_plc = datetime.now(timezone.utc)  # type: ignore

        return changed


# Singleton instance
_plc_sync_service: Optional[PLCSyncService] = None


def get_plc_sync_service() -> PLCSyncService:
    """Get or create PLCSyncService singleton instance"""
    global _plc_sync_service
    if _plc_sync_service is None:
        _plc_sync_service = PLCSyncService()
    return _plc_sync_service
