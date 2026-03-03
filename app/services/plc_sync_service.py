"""
PLC Sync Service - Periodic read and update of mo_batch from PLC data
Reads data from PLC and updates mo_batch records based on MO_ID.
Only updates if values have changed to avoid unnecessary database operations.
Includes handshake logic to mark data as read after successful sync.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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

    MAX_REASONABLE_ACTUAL_CONSUMPTION = 5000.0
    MAX_REASONABLE_WEIGHT = 10000000.0

    def __init__(self):
        self.plc_read_service = get_plc_read_service()
        self.consumption_service = get_consumption_service()

    def _sanitize_numeric_for_update(
        self,
        raw_value: Any,
        field_name: str,
        *,
        minimum: float = 0.0,
        maximum: float,
    ) -> Optional[float]:
        """Return float if value is within plausible range, else None (skip update)."""
        if raw_value is None:
            return None

        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            logger.warning(
                "Skip %s update: non-numeric PLC value=%r",
                field_name,
                raw_value,
            )
            return None

        if numeric < minimum or numeric > maximum:
            logger.warning(
                "Skip %s update: out-of-range PLC value=%s (expected %.3f..%.3f)",
                field_name,
                numeric,
                minimum,
                maximum,
            )
            return None

        return numeric

    def _normalize_binary_status(
        self,
        raw_value: Any,
        field_name: str,
    ) -> Optional[bool]:
        """Normalize PLC status into strict binary value (0/1 only)."""
        if isinstance(raw_value, bool):
            return raw_value

        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            numeric = int(raw_value)
            if numeric in (0, 1):
                return bool(numeric)
            logger.warning(
                "Invalid %s from PLC (must be 0/1): %s. Skip status update.",
                field_name,
                raw_value,
            )
            return None

        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in ("0", "false"):
                return False
            if normalized in ("1", "true"):
                return True
            logger.warning(
                "Invalid %s from PLC string (must be 0/1 or true/false): %s. Skip status update.",
                field_name,
                raw_value,
            )
            return None

        logger.warning(
            "Invalid %s type from PLC: %s (%s). Skip status update.",
            field_name,
            raw_value,
            type(raw_value).__name__,
        )
        return None

    def _normalize_mo_id(self, raw_value: Any) -> Optional[str]:
        """Normalize MO ID from PLC and keep only valid identifier format."""
        if not isinstance(raw_value, str):
            return None

        normalized = raw_value.strip().upper()
        if not normalized:
            return None

        if not re.match(r"^[A-Z0-9]+/[A-Z0-9]+/[A-Z0-9-]+$", normalized):
            logger.warning("Ignoring invalid MO_ID format from PLC: %r", raw_value)
            return None

        return normalized

    async def sync_from_plc(self) -> Dict[str, Any]:
        """
        Read data from all PLC READ batches (01..10) and update mo_batch if values changed.

        Returns:
            Dict with sync summary.
        """
        try:
            processed_batches = 0
            updated_batches = 0
            guard_skipped_values = 0
            failed_batches: List[Dict[str, Any]] = []
            mo_ids: List[str] = []
            first_mo_id: Optional[str] = None

            with SessionLocal() as session:
                for plc_batch_no in range(1, 11):
                    try:
                        plc_data = self.plc_read_service.read_batch_data(batch_no=plc_batch_no)
                    except Exception as exc:
                        failed_batches.append(
                            {
                                "batch_no": plc_batch_no,
                                "error": f"Read error: {exc}",
                            }
                        )
                        continue

                    mo_id_raw = plc_data.get("mo_id") or None
                    mo_id = self._normalize_mo_id(mo_id_raw)
                    if not mo_id:
                        get_handshake_service().mark_read_area_as_read(batch_no=plc_batch_no)
                        continue

                    processed_batches += 1
                    mo_ids.append(mo_id)
                    if first_mo_id is None:
                        first_mo_id = mo_id

                    # Prefer exact match by (batch_no, mo_id), fallback to mo_id only.
                    result = session.execute(
                        select(TableSmoBatch).where(
                            TableSmoBatch.batch_no == plc_batch_no,  # type: ignore[arg-type]
                            TableSmoBatch.mo_id == mo_id,
                        )
                    )
                    batch = result.scalar_one_or_none()

                    if not batch:
                        result = session.execute(
                            select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
                        )
                        batch = result.scalar_one_or_none()

                    if not batch:
                        # Fallback terakhir: gunakan slot/batch_no PLC.
                        # Berguna saat MO_ID terbaca noisy tapi slot mapping masih valid.
                        result = session.execute(
                            select(TableSmoBatch).where(
                                TableSmoBatch.batch_no == plc_batch_no  # type: ignore[arg-type]
                            )
                        )
                        batch = result.scalar_one_or_none()

                    if not batch:
                        failed_batches.append(
                            {
                                "batch_no": plc_batch_no,
                                "mo_id": mo_id,
                                "error": "MO batch not found in DB",
                            }
                        )
                        # Data was still read from PLC. Mark this slot as read to avoid reprocessing loop.
                        get_handshake_service().mark_read_area_as_read(batch_no=plc_batch_no)
                        continue

                    updated, skipped_values = await self._update_batch_if_changed(session, batch, plc_data)
                    guard_skipped_values += skipped_values
                    if updated:
                        session.commit()
                        updated_batches += 1
                        logger.info(
                            "Updated mo_batch for MO_ID=%s (batch_no=%s)",
                            mo_id,
                            plc_batch_no,
                        )

                    # Even if unchanged, slot has been processed.
                    get_handshake_service().mark_read_area_as_read(batch_no=plc_batch_no)

            if processed_batches == 0:
                return {
                    "success": False,
                    "error": "No MO_ID found in PLC data across all batches",
                    "mo_id": None,
                    "updated": False,
                    "processed_batches": 0,
                    "updated_batches": 0,
                    "guard_skipped_values": guard_skipped_values,
                    "failed_batches": failed_batches,
                    "mo_ids": [],
                }

            return {
                "success": True,
                "updated": updated_batches > 0,
                "mo_id": first_mo_id,
                "message": (
                    f"Processed {processed_batches} batch(es), "
                    f"updated {updated_batches} batch(es)"
                ),
                "processed_batches": processed_batches,
                "updated_batches": updated_batches,
                "guard_skipped_values": guard_skipped_values,
                "failed_batches": failed_batches,
                "mo_ids": mo_ids,
            }

        except Exception as e:
            logger.error(f"Error syncing from PLC: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "mo_id": None,
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
        Read from all PLC READ batches, update DB, and sync consumption to Odoo.

        Combined workflow:
        1. Read data from PLC batches 01..10
        2. Update mo_batch table per batch
        3. Sync consumption to Odoo per valid MO
        4. Mark READ handshake per batch slot

        Returns:
            Dict with combined summary
        """
        try:
            processed_batches = 0
            updated_batches = 0
            synced_batches = 0
            guard_skipped_values = 0
            failed_batches: List[Dict[str, Any]] = []
            first_mo_id: Optional[str] = None

            with SessionLocal() as session:
                for plc_batch_no in range(1, 11):
                    try:
                        plc_data = self.plc_read_service.read_batch_data(batch_no=plc_batch_no)
                    except Exception as exc:
                        failed_batches.append(
                            {
                                "batch_no": plc_batch_no,
                                "error": f"Read error: {exc}",
                            }
                        )
                        continue

                    mo_id_raw = plc_data.get("mo_id")
                    mo_id = self._normalize_mo_id(mo_id_raw) or ""
                    if not mo_id:
                        get_handshake_service().mark_read_area_as_read(batch_no=plc_batch_no)
                        continue

                    processed_batches += 1
                    if first_mo_id is None:
                        first_mo_id = mo_id

                    result = session.execute(
                        select(TableSmoBatch).where(
                            TableSmoBatch.batch_no == plc_batch_no,  # type: ignore[arg-type]
                            TableSmoBatch.mo_id == mo_id,
                        )
                    )
                    batch = result.scalar_one_or_none()
                    if not batch:
                        result = session.execute(
                            select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
                        )
                        batch = result.scalar_one_or_none()

                    if not batch:
                        # Fallback terakhir: gunakan slot/batch_no PLC.
                        result = session.execute(
                            select(TableSmoBatch).where(
                                TableSmoBatch.batch_no == plc_batch_no  # type: ignore[arg-type]
                            )
                        )
                        batch = result.scalar_one_or_none()

                    if not batch:
                        failed_batches.append(
                            {
                                "batch_no": plc_batch_no,
                                "mo_id": mo_id,
                                "error": "MO batch not found in DB",
                            }
                        )
                        get_handshake_service().mark_read_area_as_read(batch_no=plc_batch_no)
                        continue

                    updated, skipped_values = await self._update_batch_if_changed(session, batch, plc_data)
                    guard_skipped_values += skipped_values
                    if updated:
                        session.commit()
                        updated_batches += 1

                    consumption_result = await self.sync_consumption_to_odoo(batch)
                    if consumption_result.get("success"):
                        synced_batches += 1
                    else:
                        failed_batches.append(
                            {
                                "batch_no": plc_batch_no,
                                "mo_id": mo_id,
                                "error": consumption_result.get("error", "Consumption sync failed"),
                            }
                        )

                    get_handshake_service().mark_read_area_as_read(batch_no=plc_batch_no)

            if processed_batches == 0:
                return {
                    "success": False,
                    "error": "No MO_ID found in PLC data across all batches",
                    "mo_id": None,
                    "processed_batches": 0,
                    "updated_batches": 0,
                    "synced_batches": 0,
                    "guard_skipped_values": guard_skipped_values,
                    "failed_batches": failed_batches,
                }

            return {
                "success": True,
                "mo_id": first_mo_id,
                "processed_batches": processed_batches,
                "updated_batches": updated_batches,
                "synced_batches": synced_batches,
                "guard_skipped_values": guard_skipped_values,
                "failed_batches": failed_batches,
            }

        except Exception as e:
            logger.error(
                f"Error in sync_from_plc_with_consumption: {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
                "mo_id": None,
            }

    async def _update_batch_if_changed(
        self, session: Session, batch: TableSmoBatch, plc_data: Dict[str, Any]
    ) -> tuple[bool, int]:
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
            return (False, 0)

        changed = False
        guard_skipped_values = 0

        # Expected payload shape from PLCReadService.read_batch_data(batch_no):
        # - batch_no
        # - mo_id
        # - quantity
        # - silos: {a..m: {id, consumption}}
        # - liquids: {lq114, lq115}
        # - status: {manufacturing, operation, read}
        # - weight_finished_good
        status_payload = plc_data.get("status")
        status_obj = status_payload if isinstance(status_payload, dict) else {}

        # Update actual consumption for each silo dynamically from payload
        silos = plc_data.get("silos", {})
        if isinstance(silos, dict):
            for letter, silo_data in silos.items():
                if not isinstance(letter, str) or not isinstance(silo_data, dict):
                    continue

                normalized_letter = letter.strip().lower()
                if len(normalized_letter) != 1 or not normalized_letter.isalpha():
                    continue

                attr_name = f"actual_consumption_silo_{normalized_letter}"
                if not hasattr(batch, attr_name):
                    continue

                new_consumption = silo_data.get("consumption")
                if new_consumption is None:
                    continue

                sanitized = self._sanitize_numeric_for_update(
                    new_consumption,
                    attr_name,
                    maximum=self.MAX_REASONABLE_ACTUAL_CONSUMPTION,
                )
                if sanitized is None:
                    guard_skipped_values += 1
                    continue

                current_value = getattr(batch, attr_name)
                if current_value != sanitized:
                    setattr(batch, attr_name, sanitized)
                    changed = True
                    logger.debug(
                        f"Updated {attr_name}: {current_value} → {sanitized}"
                    )

        # Update liquid actual consumption (LQ114/LQ115)
        liquids = plc_data.get("liquids", {})
        liquid_field_map = {
            "lq114": "actual_consumption_lq_tetes",
            "lq115": "actual_consumption_lq_fml",
        }
        for liquid_key, attr_name in liquid_field_map.items():
            liquid_data = liquids.get(liquid_key, {})
            new_consumption = liquid_data.get("consumption")
            if new_consumption is None:
                continue

            sanitized = self._sanitize_numeric_for_update(
                new_consumption,
                attr_name,
                maximum=self.MAX_REASONABLE_ACTUAL_CONSUMPTION,
            )
            if sanitized is None:
                guard_skipped_values += 1
                continue

            current_value = getattr(batch, attr_name)
            if current_value != sanitized:
                setattr(batch, attr_name, sanitized)
                changed = True
                logger.debug(
                    f"Updated {attr_name}: {current_value} → {sanitized}"
                )

        # Update actual weight quantity finished goods
        new_quantity = plc_data.get("weight_finished_good")
        if new_quantity is None:
            # Backward compatibility with previous key naming
            new_quantity = plc_data.get("quantity_goods")
        if new_quantity is not None:
            sanitized_quantity = self._sanitize_numeric_for_update(
                new_quantity,
                "actual_weight_quantity_finished_goods",
                maximum=self.MAX_REASONABLE_WEIGHT,
            )
            if sanitized_quantity is None:
                guard_skipped_values += 1
            elif batch.actual_weight_quantity_finished_goods != sanitized_quantity:
                batch.actual_weight_quantity_finished_goods = sanitized_quantity
                changed = True
                logger.debug(
                    f"Updated actual_weight_quantity_finished_goods: "
                    f"{batch.actual_weight_quantity_finished_goods} → {sanitized_quantity}"
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
            status_bool = self._normalize_binary_status(
                new_status_mfg,
                "status_manufacturing",
            )
            if status_bool is not None:
                current_status: bool = batch.status_manufacturing  # type: ignore
                if current_status != status_bool:
                    batch.status_manufacturing = status_bool  # type: ignore
                    changed = True
                    logger.debug(
                        f"Updated status_manufacturing: "
                        f"{current_status} -> {status_bool}"
                    )

        new_status_op = status_obj.get("operation")
        if new_status_op is None:
            # Backward compatibility with previous key naming
            new_status_op = plc_data.get("status_operation")
        if new_status_op is not None:
            status_bool = self._normalize_binary_status(
                new_status_op,
                "status_operation",
            )
            if status_bool is None:
                return (changed, guard_skipped_values)
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
                            return (changed, guard_skipped_values)
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
                        return (False, guard_skipped_values)  # No changes to mo_batch (already deleted)
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

        return (changed, guard_skipped_values)


# Singleton instance
_plc_sync_service: Optional[PLCSyncService] = None


def get_plc_sync_service() -> PLCSyncService:
    """Get or create PLCSyncService singleton instance"""
    global _plc_sync_service
    if _plc_sync_service is None:
        _plc_sync_service = PLCSyncService()
    return _plc_sync_service


