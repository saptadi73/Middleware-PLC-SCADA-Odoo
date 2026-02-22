"""
Odoo Consumption and Mark Done Service

Service untuk update material consumption di Odoo dan mark MO sebagai done.
Digunakan setelah membaca data dari PLC untuk:
1. Update consumption untuk setiap silo/component
2. Mark MO sebagai done jika status_manufacturing = 1

Database Persistence:
- Odoo update dilakukan terlebih dahulu
- Hanya jika Odoo respond sukses, data disimpan ke database
- Ini memastikan database selalu sync dengan Odoo
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tablesmo_batch import TableSmoBatch

logger = logging.getLogger(__name__)


class OdooConsumptionService:
    """Service untuk update consumption dan mark done di Odoo
    
    Workflow:
    1. Receive batch data (PLC read)
    2. Send to Odoo API
    3. Wait for success response
    4. Only then → update local database
    5. This ensures DB is always sync with Odoo state
    """

    def __init__(self, db: Optional[Session] = None):
        self.settings = get_settings()
        self.db = db  # Optional database session
        self._silo_mapping: Dict[int, Dict[str, str]] = {}
        self._load_silo_mapping()

    def _load_silo_mapping(self) -> None:
        """Load silo mapping dari silo_data.json"""
        try:
            reference_path = (
                Path(__file__).parent.parent
                / "reference"
                / "silo_data.json"
            )

            if not reference_path.exists():
                logger.warning(
                    f"silo_data.json not found at {reference_path}"
                )
                return

            with open(reference_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Load from current silo_data.json structure.
                mapping_list = data.get("raw_list", [])
                for item in mapping_list:
                    silo_id = item.get("id")
                    if silo_id:
                        self._silo_mapping[silo_id] = {
                            "equipment_code": item.get("equipment_code", ""),
                            "scada_tag": item.get("scada_tag"),
                        }

            logger.info(
                f"Loaded equipment mapping: {len(self._silo_mapping)} items "
                f"(silos + liquid tanks)"
            )
        except Exception as e:
            logger.error(f"Error loading equipment mapping: {e}")

    def _log_odoo_response(
        self, endpoint: str, response: httpx.Response
    ) -> None:
        try:
            payload = response.json()
            logger.info(
                "Odoo response %s status=%s body=%s",
                endpoint,
                response.status_code,
                payload,
            )
        except ValueError:
            logger.info(
                "Odoo response %s status=%s text=%s",
                endpoint,
                response.status_code,
                response.text,
            )

    async def _authenticate(self) -> Optional[httpx.AsyncClient]:
        """
        Authenticate dengan Odoo dan return client dengan session cookie.

        Returns:
            AsyncClient dengan session authenticated, atau None jika gagal
        """
        try:
            base_url = self.settings.odoo_base_url.rstrip("/")
            auth_url = f"{base_url}/api/scada/authenticate"
            logger.info(
                "Odoo auth attempt: url=%s db=%s user=%s",
                auth_url,
                self.settings.odoo_db,
                self.settings.odoo_username,
            )

            auth_payload = {
                "db": self.settings.odoo_db,
                "login": self.settings.odoo_username,
                "password": self.settings.odoo_password,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(auth_url, json=auth_payload)
                response.raise_for_status()

                auth_data = response.json()
                
                # Handle both direct status and nested result.status
                status = auth_data.get("status")
                if not status:
                    # Check if status is nested in result
                    result = auth_data.get("result", {})
                    status = result.get("status")
                
                if status != "success":
                    logger.error(f"Odoo auth failed: {auth_data}")
                    return None

                # Create new client dengan cookies
                cookies = response.cookies
                new_client = httpx.AsyncClient(timeout=30.0)
                new_client.cookies.update(cookies)
                logger.info("✓ Authenticated with Odoo successfully")
                return new_client

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    async def update_consumption_with_equipment_codes(
        self,
        mo_id: str,
        consumption_data: Dict[str, float],
        quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        ✅ RECOMMENDED: Automated batch update using /update-with-consumptions endpoint.

        This is the RECOMMENDED method for automated batch processing.
        Makes a SINGLE efficient API call to Odoo's /api/scada/mo/update-with-consumptions
        endpoint with all consumption data at once.

        Benefits:
        - Single API call for ALL components (vs separate calls in update_consumption)
        - More efficient and faster
        - Better for automated workflows
        - Lower latency

        Args:
            mo_id: Manufacturing Order ID (e.g., "WH/MO/00001")
            consumption_data: Dict dengan format {equipment_code: quantity, ...}
                            Contoh: {"silo101": 825, "silo102": 600}
                            OR {scada_tag: quantity} - auto convert
            quantity: Optional jumlah product quantity untuk update MO

        Returns:
            Dict dengan hasil update dari Odoo (batch update response)
        """
        client = await self._authenticate()
        if not client:
            logger.error(
                "Failed to authenticate to Odoo; cannot call update-with-consumptions"
            )
            return {
                "success": False,
                "error": "Failed to authenticate with Odoo",
            }

        try:
            base_url = self.settings.odoo_base_url.rstrip("/")
            update_endpoint = (
                f"{base_url}/api/scada/mo/update-with-consumptions"
            )

            # Convert consumption data ke Odoo format jika perlu
            # (jika input pakai scada_tag silo_a, convert ke silo101)
            converted_data: Dict[str, float] = {}
            valid_equipment_codes = {
                data.get("equipment_code")
                for data in self._silo_mapping.values()
                if data.get("equipment_code")
            }
            for key, qty in consumption_data.items():
                try:
                    qty_value = float(qty)
                except (TypeError, ValueError):
                    logger.warning(
                        f"Invalid quantity for {key}: {qty}, skipping"
                    )
                    continue

                if qty_value <= 0:
                    logger.debug(f"Skipping {key}: quantity <= 0")
                    continue

                # Check jika key sudah valid equipment_code (silo101..silo115)
                if key in valid_equipment_codes:
                    converted_data[key] = qty_value
                else:
                    # Convert dari scada_tag (silo_a) ke equipment_code (silo101)
                    equipment_code = self._convert_scada_tag_to_equipment_code(key)
                    if equipment_code:
                        converted_data[equipment_code] = qty_value
                    else:
                        logger.warning(
                            f"Cannot convert {key} to equipment_code, skipping"
                        )

            if not converted_data:
                logger.warning(
                    "No valid consumption entries after conversion for MO %s. "
                    "Check silo mapping, consumption values, and scada_tag keys.",
                    mo_id,
                )
                return {
                    "success": False,
                    "error": (
                        "No valid consumption entries after conversion "
                        "(check silo mapping and quantity values)"
                    ),
                }

            # Build payload untuk Odoo endpoint
            payload: Dict[str, Any] = {
                "mo_id": mo_id,
            }

            if quantity and quantity > 0:
                payload["quantity"] = float(quantity)

            # Add all consumption data
            payload.update(converted_data)

            logger.info(
                "Sending to /mo/update-with-consumptions: mo_id=%s keys=%s quantity=%s",
                mo_id,
                list(converted_data.keys()),
                payload.get("quantity"),
            )
            logger.debug(f"Complete payload to /update-with-consumptions: {payload}")

            response = await client.post(update_endpoint, json=payload)
            self._log_odoo_response(update_endpoint, response)
            response.raise_for_status()

            raw_data = response.json()
            result_data = raw_data.get("result", raw_data)
            status = result_data.get("status")
            message = result_data.get("message")
            errors = result_data.get("errors", []) or []

            if status in ["success", "ok"]:
                is_partial_success = len(errors) > 0
                if is_partial_success:
                    logger.warning(
                        "update-with-consumptions completed with errors "
                        f"for {mo_id}: {errors}"
                    )
                logger.info(
                    f"Updated MO {mo_id} with consumptions via "
                    f"update-with-consumptions endpoint"
                )
                
                # ✓ Odoo update successful → Save to database
                db_saved = self._save_consumption_to_db(
                    mo_id=mo_id,
                    consumption_data=converted_data,
                )
                
                return {
                    "success": True,
                    "mo_id": mo_id,
                    "endpoint": "update-with-consumptions",
                    "consumed_items": result_data.get("consumed_items"),
                    "errors": errors,
                    "partial_success": is_partial_success,
                    "message": message,
                    "db_saved": db_saved,  # ← Indicate if DB was updated
                }
            else:
                logger.error(
                    f"Update failed for {mo_id}: "
                    f"{message}"
                )
                return {
                    "success": False,
                    "error": message or str(result_data),
                }

        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 404:
                endpoint_path = "/api/scada/mo/update-with-consumptions"
                logger.error(
                    f"Endpoint {endpoint_path} not found on Odoo server"
                )
                return {
                    "success": False,
                    "error": (
                        f"Odoo endpoint not found (404): {endpoint_path}. "
                        "Deploy or upgrade SCADA Odoo module on target "
                        "server so this endpoint is available."
                    ),
                }
            logger.error(
                f"Error updating consumption with odoo codes for {mo_id}: {e}"
            )
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(
                f"Error updating consumption with odoo codes for {mo_id}: {e}"
            )
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await client.aclose()

    def _convert_scada_tag_to_equipment_code(self, scada_tag: str) -> Optional[str]:
        """
        Convert SCADA tag (silo_a) ke equipment code (silo101).

        Args:
            scada_tag: SCADA tag (e.g., "silo_a")

        Returns:
            Equipment code (e.g., "silo101") atau None jika tidak found
        """
        for silo_data in self._silo_mapping.values():
            if silo_data.get("scada_tag") == scada_tag:
                return silo_data.get("equipment_code")
        return None

    def _convert_equipment_code_to_scada_tag(self, equipment_code: str) -> Optional[str]:
        """
        Convert equipment code (silo101) ke SCADA tag (silo_a).

        Args:
            equipment_code: Equipment code (e.g., "silo101")

        Returns:
            SCADA tag (e.g., "silo_a") atau None jika tidak found atau LQ tank
        """
        for silo_data in self._silo_mapping.values():
            if silo_data.get("equipment_code") == equipment_code:
                return silo_data.get("scada_tag")
        return None

    def _save_consumption_to_db(
        self,
        mo_id: str,
        consumption_data: Dict[str, float],
    ) -> bool:
        """
        Save consumption data ke mo_batch table di database.
        
        IMPORTANT: Hanya dipanggil setelah Odoo update SUKSES.
        Ini memastikan DB selalu sync dengan Odoo state.

        Args:
            mo_id: Manufacturing Order ID
            consumption_data: Dict {equipment_code: quantity, ...}
                            Contoh: {"silo101": 825.5, "silo102": 600.3}

        Returns:
            True jika berhasil, False jika gagal atau tidak ada session
        """
        if not self.db:
            logger.debug(
                "Database session not available, skipping DB save"
            )
            return False

        try:
            # Find mo_batch record berdasarkan mo_id
            stmt = select(TableSmoBatch).where(
                TableSmoBatch.mo_id == mo_id
            )
            mo_batch = self.db.execute(stmt).scalars().first()

            if not mo_batch:
                logger.warning(f"MO batch {mo_id} not found in database")
                return False

            # Check if status_manufacturing is already 1 (True)
            # If manufacturing is done, skip update to prevent overwriting completed data
            current_status_mfg: bool = mo_batch.status_manufacturing  # type: ignore
            if current_status_mfg:
                logger.info(
                    f"Skip consumption update for MO {mo_id}: "
                    f"status_manufacturing already completed (1)"
                )
                return False

            # Convert equipment_code back to SCADA tag dan update fields
            # Silos: silo101 → silo_a → actual_consumption_silo_a
            # Liquid tanks: lq114 → lq_tetes → actual_consumption_lq_tetes
            #              lq115 → lq_fml → actual_consumption_lq_fml
            for equipment_code, quantity in consumption_data.items():
                scada_tag = self._convert_equipment_code_to_scada_tag(equipment_code)
                if scada_tag:
                    # Build field name: silo_a → actual_consumption_silo_a
                    #                   lq_tetes → actual_consumption_lq_tetes
                    field_name = f"actual_consumption_{scada_tag}"
                    if hasattr(mo_batch, field_name):
                        setattr(mo_batch, field_name, float(quantity))
                        logger.debug(
                            f"Set {field_name} = {quantity} for MO {mo_id}"
                        )
                    else:
                        logger.warning(
                            f"Field {field_name} not found in mo_batch"
                        )
                else:
                    logger.debug(
                        f"Equipment {equipment_code} has no SCADA tag, "
                        f"skipping SCADA-based save"
                    )

            # Update last read timestamp
            mo_batch.last_read_from_plc = datetime.now(timezone.utc)  # type: ignore

            # Commit ke database
            self.db.commit()
            logger.info(
                f"✓ Saved {len(consumption_data)} consumption entries to DB "
                f"for MO {mo_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error saving consumption to database for {mo_id}: {e}"
            )
            self.db.rollback()
            return False

    async def update_consumption(
        self,
        mo_id: str,
        equipment_id: str,
        consumption_data: Dict[str, float],
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        MANUAL UPDATE: Material consumption per-component using /material-consumption endpoint.

        ⚠️ IMPORTANT: This method is for MANUAL per-component updates only.
        It makes SEPARATE API calls to Odoo's /api/scada/material-consumption endpoint
        for each material component using product_id parameter.

        For automated batch processing, use update_consumption_with_equipment_codes() instead,
        which is more efficient and uses a single API call.

        Use this method for:
        - Manual correction of specific material consumption
        - Per-component adjustments after verification
        - One-off updates

        Args:
            mo_id: Manufacturing order ID (e.g., "MO/2025/001")
            equipment_id: Equipment code (e.g., "PLC01")
            consumption_data: Dict dengan format {product_id: quantity, ...}
                            Contoh: {"silo_a": 50.5, "silo_b": 25.3}
            timestamp: ISO format timestamp, default = now

        Returns:
            Dict dengan status update consumption dengan detail per component
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        client = await self._authenticate()
        if not client:
            return {
                "success": False,
                "error": "Failed to authenticate with Odoo",
            }

        try:
            base_url = self.settings.odoo_base_url.rstrip("/")
            consumption_url = (
                f"{base_url}/api/scada/material-consumption"
            )

            results = []

            for product_key, quantity in consumption_data.items():
                if quantity <= 0:
                    logger.debug(f"Skipping {product_key}: quantity <= 0")
                    continue

                payload: Dict[str, Any] = {
                    "equipment_id": equipment_id,
                    "product_id": product_key,
                    "quantity": float(quantity),
                    "timestamp": timestamp,
                    "mo_id": mo_id,
                }

                try:
                    response = await client.post(
                        consumption_url, json=payload
                    )
                    self._log_odoo_response(consumption_url, response)
                    response.raise_for_status()

                    result_data = response.json()
                    results.append({
                        "product": product_key,
                        "quantity": quantity,
                        "status": result_data.get("status"),
                        "message": result_data.get("message"),
                    })

                    logger.info(
                        f"Updated consumption for {product_key}: "
                        f"{quantity} on MO {mo_id}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error updating consumption for {product_key}: {e}"
                    )
                    results.append({
                        "product": product_key,
                        "quantity": quantity,
                        "status": "error",
                        "error": str(e),
                    })

            return {
                "success": True,
                "mo_id": mo_id,
                "equipment_id": equipment_id,
                "items_updated": len(results),
                "details": results,
            }

        except Exception as e:
            logger.error(f"Error in update_consumption: {e}")
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await client.aclose()

    def _save_mark_done_to_db(
        self,
        mo_id: str,
        finished_qty: float,
    ) -> bool:
        """
        Save mark-done status ke mo_batch table di database.
        
        IMPORTANT: Hanya dipanggil setelah Odoo mark-done SUKSES.

        Args:
            mo_id: Manufacturing Order ID
            finished_qty: Finished quantity

        Returns:
            True jika berhasil, False jika gagal
        """
        if not self.db:
            logger.debug(
                "Database session not available, skipping DB save"
            )
            return False

        try:
            # Find mo_batch record berdasarkan mo_id
            stmt = select(TableSmoBatch).where(
                TableSmoBatch.mo_id == mo_id
            )
            mo_batch = self.db.execute(stmt).scalars().first()

            if not mo_batch:
                logger.warning(f"MO batch {mo_id} not found in database")
                return False

            # Update status dan finished quantity
            mo_batch.status_manufacturing = True  # type: ignore
            mo_batch.actual_weight_quantity_finished_goods = float(  # type: ignore
                finished_qty
            )
            mo_batch.last_read_from_plc = datetime.now(timezone.utc)  # type: ignore

            # Commit ke database
            self.db.commit()
            logger.info(
                f"✓ Saved mark-done to DB for MO {mo_id} "
                f"(finished_qty={finished_qty})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error saving mark-done to database for {mo_id}: {e}"
            )
            self.db.rollback()
            return False

    async def mark_mo_done(
        self,
        mo_id: str,
        finished_qty: float,
        equipment_id: Optional[str] = None,
        auto_consume: bool = False,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mark Manufacturing Order sebagai done di Odoo.

        Args:
            mo_id: Manufacturing order ID (e.g., "MO/2025/001")
            finished_qty: Quantity yang selesai (harus > 0)
            equipment_id: Equipment code (optional)
            auto_consume: Jika True, auto-apply remaining consumption
            message: Optional message untuk log

        Returns:
            Dict dengan status mark done
        """
        client = await self._authenticate()
        if not client:
            return {
                "success": False,
                "error": "Failed to authenticate with Odoo",
            }

        try:
            base_url = self.settings.odoo_base_url.rstrip("/")
            mark_done_url = f"{base_url}/api/scada/mo/mark-done"

            payload: Dict[str, Any] = {
                "mo_id": mo_id,
                "finished_qty": float(finished_qty),
                "auto_consume": auto_consume,
                # Some Odoo deployments parse this with strict
                # "%Y-%m-%d %H:%M:%S" format.
                "date_end_actual": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }

            if equipment_id:
                payload["equipment_id"] = equipment_id

            if message:
                payload["message"] = message

            response = await client.post(mark_done_url, json=payload)
            self._log_odoo_response(mark_done_url, response)
            response.raise_for_status()

            raw_data = response.json()
            result_data = raw_data.get("result", raw_data)
            status = result_data.get("status")
            message_text = result_data.get("message")

            if status == "success":
                logger.info(
                    f"Marked MO {mo_id} as done with "
                    f"finished_qty={finished_qty}"
                )
                
                # ✓ Odoo mark-done successful → Save to database
                db_saved = self._save_mark_done_to_db(
                    mo_id=mo_id,
                    finished_qty=finished_qty,
                )
                
                return {
                    "success": True,
                    "mo_id": mo_id,
                    "finished_qty": finished_qty,
                    "message": message_text,
                    "db_saved": db_saved,  # ← Indicate if DB was updated
                }
            else:
                logger.error(
                    f"Mark done failed for {mo_id}: "
                    f"{message_text}"
                )
                return {
                    "success": False,
                    "error": message_text or str(result_data),
                }

        except Exception as e:
            logger.error(f"Error marking MO {mo_id} as done: {e}")
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await client.aclose()

    async def process_batch_consumption(
        self,
        mo_id: str,
        equipment_id: str,
        batch_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process consumption untuk semua silo component dalam batch.

        MIGRATED to use efficient /api/scada/mo/update-with-consumptions endpoint.
        
        Args:
            mo_id: Manufacturing order ID
            equipment_id: Equipment code
            batch_data: Dict dengan format:
                      {
                          "consumption_silo_a": 50.5,
                          "consumption_silo_b": 25.3,
                          ...
                          "status_manufacturing": 1,
                          "actual_weight_quantity_finished_goods": 1000
                      }

        Returns:
            Dict dengan hasil proses keseluruhan
        """
        try:
            # Extract consumption data from batch
            # Convert SCADA tags (silo_a, silo_b) → equipment codes (silo101, silo102)
            consumption_entries: Dict[str, float] = {}
            
            for letter in "abcdefghijklm":
                consumption_key = f"consumption_silo_{letter}"
                silo_tag = f"silo_{letter}"

                if consumption_key in batch_data:
                    consumption_value = batch_data[consumption_key]
                    if consumption_value and consumption_value > 0:
                        # Convert silo_a → silo101, etc
                        equipment_code = self._convert_scada_tag_to_equipment_code(silo_tag)
                        if equipment_code:
                            consumption_entries[equipment_code] = float(consumption_value)
                        else:
                            logger.warning(
                                f"Cannot convert {silo_tag} to equipment_code, skipping"
                            )

            logger.info(
                "process_batch_consumption: mo_id=%s equipment_id=%s status_mfg=%s",
                mo_id,
                equipment_id,
                batch_data.get("status_manufacturing"),
            )
            logger.debug("process_batch_consumption payload keys: %s", list(batch_data.keys()))

            # Step 1: Update consumption using efficient endpoint
            # (/api/scada/mo/update-with-consumptions - single call)
            update_result = {
                "consumption_updated": False,
                "consumption_details": None,
            }

            if consumption_entries:
                # Extract quantity (actual_weight_finished_good) untuk update stock.move.line
                quantity = batch_data.get("actual_weight_quantity_finished_goods")
                if quantity is not None:
                    try:
                        quantity = float(quantity)
                    except (TypeError, ValueError):
                        quantity = None
                
                update_result[
                    "consumption_details"
                ] = await self.update_consumption_with_equipment_codes(
                    mo_id=mo_id,
                    consumption_data=consumption_entries,
                    quantity=quantity,
                )
                update_result["consumption_updated"] = update_result[
                    "consumption_details"
                ].get("success", False)
            else:
                logger.warning(
                    "No consumption entries to send for MO %s. "
                    "All values <=0 or missing in batch_data.",
                    mo_id,
                )

            # Step 2: Optional mark done (disabled by default)
            mark_done_result = {
                "mo_marked_done": False,
                "mark_done_details": None,
                "skipped": True,
                "reason": "mark done disabled by default",
            }

            status_manufacturing = batch_data.get("status_manufacturing", 0)
            run_mark_done = bool(batch_data.get("run_mark_done", False))
            if run_mark_done and status_manufacturing == 1:
                finished_qty = batch_data.get(
                    "actual_weight_quantity_finished_goods", 0
                )

                if finished_qty > 0:
                    mark_done_result[
                        "mark_done_details"
                    ] = await self.mark_mo_done(
                        mo_id=mo_id,
                        finished_qty=finished_qty,
                        equipment_id=equipment_id,
                        auto_consume=True,
                    )
                    mark_done_result["mo_marked_done"] = mark_done_result[
                        "mark_done_details"
                    ].get("success", False)
                    mark_done_result["skipped"] = False
                    mark_done_result["reason"] = None
                else:
                    mark_done_result["reason"] = (
                        "run_mark_done=true but finished_qty <= 0"
                    )
            elif run_mark_done and status_manufacturing != 1:
                mark_done_result["reason"] = (
                    "run_mark_done=true but status_manufacturing != 1"
                )
            elif not run_mark_done:
                mark_done_result["reason"] = (
                    "run_mark_done is false; mark done not executed"
                )

            return {
                "success": (
                    update_result["consumption_updated"]
                    or mark_done_result["mo_marked_done"]
                ),
                "mo_id": mo_id,
                "endpoint": "update-with-consumptions",  # ← Indicates efficient endpoint used
                "consumption": update_result,
                "mark_done": mark_done_result,
            }

        except Exception as e:
            logger.error(
                f"Error processing batch consumption for {mo_id}: {e}"
            )
            return {
                "success": False,
                "error": str(e),
            }

    async def cancel_mo(self, mo_id: str) -> Dict[str, Any]:
        """
        Cancel Manufacturing Order di Odoo.
        
        Called when status_operation=1 (failed) detected from PLC.
        
        Args:
            mo_id: Manufacturing order ID (e.g., "WH/MO/00003")
        
        Returns:
            Dict with cancellation result:
            {
                "success": bool,
                "message": str,
                "mo_id": str,
                "mo_state": str ("cancel" if successful)
            }
        """
        client = None
        try:
            logger.info(f"Attempting to cancel MO {mo_id} in Odoo...")
            
            # Authenticate dengan Odoo
            client = await self._authenticate()
            if not client:
                return {
                    "success": False,
                    "error": "Failed to authenticate with Odoo",
                    "mo_id": mo_id,
                }
            
            # Call Odoo cancel endpoint
            cancel_url = f"{self.settings.odoo_url}/api/scada/mo/cancel"
            payload = {"mo_id": mo_id}
            
            logger.debug(f"Sending cancel request to Odoo: {cancel_url}")
            logger.debug(f"Payload: {payload}")
            
            response = await client.post(cancel_url, json=payload, timeout=30.0)
            
            self._log_odoo_response(cancel_url, response)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("status") == "success":
                    logger.info(
                        f"✓ Successfully cancelled MO {mo_id} in Odoo. "
                        f"State: {result.get('mo_state')}"
                    )
                    return {
                        "success": True,
                        "message": result.get("message", "MO cancelled successfully"),
                        "mo_id": mo_id,
                        "mo_state": result.get("mo_state", "cancel"),
                    }
                else:
                    error_msg = result.get("message", "Unknown error from Odoo")
                    logger.error(f"✗ Failed to cancel MO {mo_id}: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "mo_id": mo_id,
                    }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"✗ Odoo cancel request failed for MO {mo_id}: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "mo_id": mo_id,
                }
        
        except Exception as e:
            logger.error(f"Error cancelling MO {mo_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "mo_id": mo_id,
            }
        finally:
            if client:
                await client.aclose()

    def get_silo_mapping(self) -> Dict[int, Dict[str, str]]:
        """Get current silo mapping"""
        return self._silo_mapping

    def get_silo_by_id(self, silo_id: int) -> Optional[Dict[str, str]]:
        """Get silo mapping by ID"""
        return self._silo_mapping.get(silo_id)

    def get_silo_by_scada_tag(
        self, scada_tag: str
    ) -> Optional[Dict[str, str]]:
        """Get silo mapping by SCADA tag"""
        for silo_data in self._silo_mapping.values():
            if silo_data.get("scada_tag") == scada_tag:
                return silo_data
        return None


# Singleton instance (without DB)
_consumption_service: Optional[OdooConsumptionService] = None


def get_consumption_service(
    db: Optional[Session] = None,
) -> OdooConsumptionService:
    """
    Get consumption service instance.
    
    Args:
        db: Optional database session for persistence
        
    Returns:
        OdooConsumptionService instance (singleton if no db provided)
    """
    global _consumption_service
    
    # If db provided, create new instance with DB support
    if db is not None:
        return OdooConsumptionService(db=db)
    
    # Otherwise return singleton without DB
    if _consumption_service is None:
        _consumption_service = OdooConsumptionService()
    return _consumption_service
