"""
PLC Sync Service - Periodic read and update of mo_batch from PLC data
Reads data from PLC and updates mo_batch records based on MO_ID.
Only updates if values have changed to avoid unnecessary database operations.
Includes handshake logic to mark data as read after successful sync.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_read_service import get_plc_read_service
from app.services.plc_handshake_service import get_handshake_service
from app.services.odoo_consumption_service import (
    get_consumption_service,
)
from app.services.mo_history_service import get_mo_history_service

logger = logging.getLogger(__name__)


class PLCSyncService:
    """Service to sync PLC data to mo_batch table"""

    def __init__(self):
        self.plc_read_service = get_plc_read_service()
        self.consumption_service = get_consumption_service()

    async def sync_from_plc(self) -> Dict[str, Any]:
        """
        Read data from PLC and update mo_batch if values changed.

        Returns:
            Dict with sync results (updated count, errors, etc.)
        """
        mo_id = None
        try:
            # Read all data from PLC
            plc_data = self.plc_read_service.read_batch_data()

            # Extract MO_ID from PLC (handle None values from failed reads)
            mo_id = plc_data.get("mo_id") or None
            if mo_id:
                mo_id = mo_id.strip() if isinstance(mo_id, str) else None
            
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
                updated = await self._update_batch_if_changed(
                    session, batch, plc_data
                )

                if updated:
                    session.commit()
                    logger.info(f"Updated mo_batch for MO_ID: {mo_id}")
                    
                    # Mark READ area as read after successful sync
                    handshake = get_handshake_service()
                    handshake.mark_read_area_as_read()  # Set D6075 = 1
                    
                    return {
                        "success": True,
                        "updated": True,
                        "mo_id": mo_id,
                        "message": "Batch data updated successfully",
                    }
                else:
                    # Even if no changes, still mark as read (we processed it)
                    handshake = get_handshake_service()
                    handshake.mark_read_area_as_read()  # Set D6075 = 1
                    
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

    async def sync_consumption_to_odoo(
        self, batch: TableSmoBatch
    ) -> Dict[str, Any]:
        """
        Sync consumption data from batch to Odoo.

        Setelah reading PLC, function ini:
        1. Update consumption untuk semua silo yang punya data
        2. Mark MO sebagai done jika status_manufacturing = 1

        Args:
            batch: TableSmoBatch record dengan data terbaru dari PLC

        Returns:
            Dict dengan hasil sync ke Odoo
        """
        mo_id_val = str(batch.mo_id) if batch.mo_id is not None else ""
        if not mo_id_val or mo_id_val.strip() == "":
            return {
                "success": False,
                "error": "No MO ID in batch",
            }

        try:
            # Prepare batch data untuk consumption service
            batch_data = {
                "status_manufacturing": batch.status_manufacturing,
                "actual_weight_quantity_finished_goods": (
                    batch.actual_weight_quantity_finished_goods
                ),
            }

            # Add consumption untuk setiap silo
            for letter in "abcdefghijklm":
                consumption_attr = f"consumption_silo_{letter}"
                if hasattr(batch, consumption_attr):
                    batch_data[consumption_attr] = getattr(
                        batch, consumption_attr
                    )

            # Get equipment ID dari batch jika ada
            equipment_id_val = (
                batch.equipment_id_batch
                if batch.equipment_id_batch is not None
                else "PLC01"
            )
            equipment_id = str(equipment_id_val)

            # Process batch consumption dengan consumption service
            result = await self.consumption_service.process_batch_consumption(
                mo_id=mo_id_val,
                equipment_id=equipment_id,
                batch_data=batch_data,
            )

            logger.info(
                f"Consumption sync result for {mo_id_val}: "
                f"{result}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Error syncing consumption for {mo_id_val}: {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    async def sync_from_plc_with_consumption(self) -> Dict[str, Any]:
        """
        Read from PLC, update batch, dan sync consumption ke Odoo.

        Combined workflow yang:
        1. Read data dari PLC
        2. Update mo_batch table
        3. Sync consumption ke Odoo
        4. Mark done di Odoo jika manufacturing selesai

        Returns:
            Dict dengan combined results
        """
        mo_id = None
        try:
            # Step 1: Read from PLC
            plc_data = self.plc_read_service.read_batch_data()

            mo_id = plc_data.get("mo_id", "").strip()
            if not mo_id:
                return {
                    "success": False,
                    "error": "No MO_ID found in PLC data",
                    "mo_id": None,
                }

            # Step 2: Update mo_batch
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

                # Update batch dari PLC data
                updated = await self._update_batch_if_changed(
                    session, batch, plc_data
                )

                if updated:
                    session.commit()
                    logger.info(f"Updated mo_batch for MO_ID: {mo_id}")

                # Step 3: Sync consumption ke Odoo
                # Menggunakan asyncio.run karena function ini sync tapi
                # consumption service adalah async
                consumption_result = await self.sync_consumption_to_odoo(batch)

                return {
                    "success": True,
                    "mo_id": mo_id,
                    "batch_updated": updated,
                    "consumption_sync": consumption_result,
                }

        except Exception as e:
            logger.error(
                f"Error in sync_from_plc_with_consumption: {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
                "mo_id": mo_id,
            }

    async def _update_batch_if_changed(
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
        # Check if status_manufacturing is already 1 (True)
        # If manufacturing is COMPLETED, skip ALL updates
        # This prevents interfering with the completion workflow
        current_status_mfg: bool = batch.status_manufacturing  # type: ignore
        if current_status_mfg:
            logger.info(
                f"Skip update for MO {batch.mo_id}: "
                f"status_manufacturing already completed (1). "
                f"Batch is being/been processed for Odoo completion."
            )
            return False

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
            "a": "SILO ID 101 Consumption",
            "b": "SILO ID 102 Consumption",
            "c": "SILO ID 103 Consumption",
            "d": "SILO ID 104 Consumption",
            "e": "SILO ID 105 Consumption",
            "f": "SILO ID 106 Consumption",
            "g": "SILO ID 107 Consumption",
            "h": "SILO ID 108 Consumption",
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

        # Update status fields (but only if DB is not yet marked complete)
        # LOGIC:
        # 1. Check current DB status BEFORE any update
        # 2. If DB status_manufacturing = true → SKIP ALL updates
        # 3. If DB status_manufacturing = false → ALLOW updates including status itself
        # 4. Next cycle: DB is true → blocks automatically
        
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
            logger.debug(
                "Status operation check: plc=%s db=%s mo_id=%s batch_no=%s",
                status_bool,
                current_status_op,
                batch.mo_id,
                batch.batch_no,
            )
            
            # AUTO-CANCEL LOGIC: Detect status_operation=1 (failed state)
            # Support idempotent retry with odoo_cancelled flag
            # Triggers when:
            # 1. status_operation=True (failed) AND status_manufacturing=False (not completed)
            # This covers both: new failures and retry scenarios for archive
            odoo_cancelled_flag: bool = getattr(batch, 'odoo_cancelled', False)  # type: ignore
            status_manufacturing: bool = getattr(batch, 'status_manufacturing', False)  # type: ignore
            
            if status_bool and not status_manufacturing:
                # Failed batch detected (not completed normally)
                mo_id_val = batch.mo_id
                mo_id = str(mo_id_val) if mo_id_val is not None else "Unknown"
                batch_no: int = batch.batch_no  # type: ignore
                
                logger.warning(
                    f"⚠️ BATCH FAILURE DETECTED: status_operation=1 for "
                    f"batch #{batch_no} (MO: {mo_id}). Initiating auto-cancel "
                    f"(odoo_cancelled={odoo_cancelled_flag})..."
                )
                
                try:
                    # Step 1: Cancel MO in Odoo (skip if already cancelled)
                    if not odoo_cancelled_flag:
                        logger.debug(
                            f"🔍 DEBUG: About to call cancel_mo for mo_id={mo_id}, batch_no={batch_no}"
                        )
                        cancel_result = await self.consumption_service.cancel_mo(mo_id)
                        logger.debug(
                            f"🔍 DEBUG: Raw cancel_result type={type(cancel_result)}, value={cancel_result}"
                        )
                        logger.debug(
                            "Auto-cancel Odoo result: %s for mo_id=%s batch_no=%s",
                            cancel_result,
                            mo_id,
                            batch_no,
                        )
                        
                        # Debug: Check what keys are in cancel_result
                        if isinstance(cancel_result, dict):
                            logger.debug(
                                f"🔍 DEBUG: cancel_result.keys() = {cancel_result.keys()}"
                            )
                            logger.debug(
                                f"🔍 DEBUG: cancel_result.get('success') = {cancel_result.get('success')}"
                            )
                        
                        if cancel_result.get("success"):
                            logger.info(
                                f"✓ Odoo cancellation successful for batch #{batch_no} (MO: {mo_id})"
                            )
                            # Set odoo_cancelled flag to prevent re-cancel on retry
                            batch.odoo_cancelled = True  # type: ignore
                            session.commit()
                            logger.debug(
                                f"🔍 DEBUG: Set odoo_cancelled=True for batch_no={batch_no}"
                            )
                        else:
                            logger.warning(
                                f"🔍 DEBUG: cancel_result.get('success') returned False/None, "
                                f"skipping archive step for batch_no={batch_no}"
                            )
                            logger.error(
                                f"✗ Failed to cancel MO {mo_id} in Odoo: "
                                f"{cancel_result.get('error')}"
                            )
                            # Don't continue to archive if Odoo cancel failed
                            # Continue to update status_operation to mark the failure
                            batch.status_operation = status_bool  # type: ignore
                            changed = True
                            return changed
                    else:
                        logger.info(
                            f"⏩ Odoo cancel already completed for batch #{batch_no} (MO: {mo_id}), "
                            f"proceeding directly to archive retry..."
                        )
                    
                    # Step 2: Archive to history with status='cancelled'
                    # This step executes if:
                    # - Odoo cancel just succeeded above, OR
                    # - odoo_cancelled flag was already True (retry scenario)
                    logger.debug(
                        f"🔍 DEBUG: About to call cancel_batch on history_service for batch_no={batch_no}"
                    )
                    history_service = get_mo_history_service(session)
                    logger.debug(
                        f"🔍 DEBUG: history_service instance = {history_service}"
                    )
                    archive_result = history_service.cancel_batch(
                        batch_no=batch_no,
                        notes=f"Auto-cancelled: status_operation=1 (failed) detected from PLC"
                    )
                    logger.debug(
                        f"🔍 DEBUG: Raw archive_result type={type(archive_result)}, value={archive_result}"
                    )
                    logger.debug(
                        "Auto-cancel archive result: %s for mo_id=%s batch_no=%s",
                        archive_result,
                        mo_id,
                        batch_no,
                    )
                    
                    # Debug: Check what keys are in archive_result
                    if isinstance(archive_result, dict):
                        logger.debug(
                            f"🔍 DEBUG: archive_result.keys() = {archive_result.keys()}"
                        )
                        logger.debug(
                            f"🔍 DEBUG: archive_result.get('success') = {archive_result.get('success')}"
                        )
                    
                    if archive_result.get("success"):
                        logger.info(
                            f"✓✓ Batch #{batch_no} (MO: {mo_id}) cancelled and archived to history"
                        )
                        # Return immediately - batch is now archived and deleted
                        # No need to update status_operation field
                        return False  # No changes to mo_batch (already deleted)
                    else:
                        logger.error(
                            f"✗ Failed to archive cancelled batch #{batch_no}: "
                            f"{archive_result.get('message')}. Will retry on next PLC read."
                        )
                        # Keep odoo_cancelled=True, will retry archive next iteration
                
                except Exception as cancel_error:
                    logger.error(
                        f"✗ Exception during auto-cancel for batch #{batch_no}: {cancel_error}",
                        exc_info=True
                    )
                    # Continue to update status_operation to mark the failure
            
            # Update status_operation field (if batch still exists)
            if current_status_op != status_bool:
                batch.status_operation = status_bool  # type: ignore
                changed = True
                logger.debug(
                    f"Updated status_operation: {current_status_op} → {status_bool}"
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
