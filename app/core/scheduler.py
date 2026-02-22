"""
Enhanced Background Scheduler for Multiple Tasks:
1. Auto-sync MO dari Odoo ke mo_batch table
2. Read PLC memory dan update mo_batch (periodic)
3. Process completed/failed batches untuk update ke Odoo dan move ke history
4. Monitor dan notification untuk batch failures
5. Read equipment failure data dari PLC (periodic)
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, cast

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine, desc, text, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.mo_batch_service import sync_mo_list_to_db
from app.services.odoo_auth_service import fetch_mo_list_detailed
from app.services.plc_sync_service import get_plc_sync_service
from app.services.mo_history_service import get_mo_history_service
from app.services.odoo_consumption_service import get_consumption_service
from app.services.plc_equipment_failure_service import get_equipment_failure_service
from app.services.equipment_failure_db_service import EquipmentFailureDbService
from app.services.equipment_failure_service import EquipmentFailureService
from app.models.system_log import SystemLog
from app.models.tablesmo_batch import TableSmoBatch

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def get_equipment_failure_api_service(db: "Session") -> EquipmentFailureService:
    """Get equipment failure service instance dengan database session."""
    return EquipmentFailureService(db=db)


async def auto_sync_mo_task():
    """
    Task 1: Sync MO dari Odoo ke PLC dan mo_batch.
    Logic:
    1. Cek apakah table mo_batch kosong
    2. Jika kosong: fetch batches from Odoo, sync ke database
    3. WRITE batch data ke PLC memory (PLC akan execute batch ini)
    4. Jika ada data: skip (tunggu PLC selesai proses batch saat ini)
    
    Note: Cancelled batches already removed from mo_batch (moved to mo_histories),
    so they won't be counted in the empty check.
    """
    settings = get_settings()
    
    try:
        logger.info("\n" + "="*80)
        logger.info("[TASK 1] Auto-sync MO task running at: %s", datetime.now())
        logger.info("="*80)
        
        # 1. Cek apakah table mo_batch kosong
        logger.debug("[TASK 1-DEBUG-1] Checking mo_batch table count...")
        engine = create_engine(settings.database_url)
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
                count = result.scalar() or 0
        finally:
            engine.dispose()  # Important: cleanup connection pool
        
        logger.debug(f"[TASK 1-DEBUG-2] mo_batch record count: {count}")
        
        if count > 0:
            logger.info(
                f"[TASK 1] ? Table mo_batch has {count} records. "
                "Skipping sync - waiting for PLC to complete all batches."
            )
            return
        
        logger.info("[TASK 1] ? Table mo_batch is empty. Fetching new batches from Odoo...")
        odoo_fetch_limit = settings.sync_batch_limit
        logger.debug(f"[TASK 1-DEBUG-3] Odoo fetch params: limit={odoo_fetch_limit}, offset=0")
        
        # 2. Fetch dari Odoo
        payload = await fetch_mo_list_detailed(
            limit=odoo_fetch_limit,
            offset=0
        )
        
        logger.debug(f"[TASK 1-DEBUG-4] Odoo response: {payload}")
        
        result = payload.get("result", {})
        mo_list = result.get("data", [])
        
        logger.debug(f"[TASK 1-DEBUG-5] Extracted mo_list count: {len(mo_list)}")
        
        if not mo_list:
            logger.info("[TASK 1] No batches found in Odoo")
            return
        
        logger.info(f"[TASK 1] Found {len(mo_list)} MO(s) from Odoo")
        for idx, mo in enumerate(mo_list, 1):
            logger.debug(f"[TASK 1-DEBUG-6.{idx}] MO data: mo_id={mo.get('id')}, name={mo.get('name')}")
        
        max_plc_slots = 30
        if len(mo_list) > max_plc_slots:
            logger.warning(
                "[TASK 1] Odoo returned %s MO(s), but PLC supports max %s slots. "
                "Only first %s MO(s) will be processed this cycle.",
                len(mo_list),
                max_plc_slots,
                max_plc_slots,
            )
            mo_list = mo_list[:max_plc_slots]

        # 3. Sync ke database (deferred commit)
        logger.debug("[TASK 1-DEBUG-7] Syncing to mo_batch database...")
        db = SessionLocal()
        try:
            synced = sync_mo_list_to_db(db, mo_list, commit=False)
            logger.info(
                f"[TASK 1] ? Database stage completed (not committed yet): {synced} MO batches"
            )
            logger.debug("[TASK 1-DEBUG-8] Database stage successful")
            
            # 4. WRITE batch data ke PLC memory
            logger.debug("[TASK 1-DEBUG-9] Starting PLC write operation...")
            from app.services.mo_batch_service import write_mo_batch_queue_to_plc
            
            written = write_mo_batch_queue_to_plc(db, start_slot=1, limit=synced)
            logger.info(f"[TASK 1] ? PLC write completed: {written} batches written to PLC")
            logger.debug(f"[TASK 1-DEBUG-10] Batches written count: {written}")
            if written != synced:
                raise RuntimeError(
                    f"Partial PLC write detected (staged={synced}, written={written}). "
                    "Rolling back DB stage to avoid queue inconsistency."
                )

            db.commit()
            logger.info(
                f"[TASK 1] ? Auto-sync committed successfully: staged={synced}, written={written}"
            )
            
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
            
    except Exception as exc:
        logger.exception("[TASK 1] ? ERROR in auto-sync task: %s", str(exc))
        logger.error(f"[TASK 1-ERROR] Exception type: {type(exc).__name__}")


async def plc_read_sync_task():
    """
    Task 2: Read PLC memory and update mo_batch database.
    
    Logic:
    1. Read PLC memory once per cycle
    2. Update mo_batch dengan actual consumption dan status dari PLC
    3. NO Odoo sync in this task (Task 3 will handle Odoo sync)
    
    Note: Only update database, consumption data will be synced to Odoo by Task 3
    when status_manufacturing = 1 (completed).
    """
    try:
        logger.info("\n" + "="*80)
        logger.info("[TASK 2] PLC read sync task running at: %s", datetime.now())
        logger.info("="*80)
        
        # Check: apakah ada active batches
        logger.debug("[TASK 2-DEBUG-1] Querying active batches from mo_batch...")
        db = SessionLocal()
        try:
            stmt = select(TableSmoBatch).where(
                TableSmoBatch.status_manufacturing.is_(False)
            )
            result = db.execute(stmt)
            active_batches = result.scalars().all()
            active_batches_count = len(active_batches)
            
            logger.debug(f"[TASK 2-DEBUG-2] Active batches count: {active_batches_count}")
            
            if active_batches_count == 0:
                logger.info("[TASK 2] No active batches to read from PLC")
                return
            
            logger.info(f"[TASK 2] Found {active_batches_count} active batch(es) in queue")
            for idx, batch in enumerate(active_batches, 1):
                logger.debug(f"[TASK 2-DEBUG-3.{idx}] Active batch: mo_id={batch.mo_id}, batch_no={batch.batch_no}, status={batch.status_manufacturing}")
            
        finally:
            db.close()
        
        # Read PLC once per cycle
        logger.debug("[TASK 2-DEBUG-4] Initializing PLC sync service...")
        plc_service = get_plc_sync_service()
        
        try:
            logger.debug("[TASK 2-DEBUG-5] Calling sync_from_plc()...")
            result = await plc_service.sync_from_plc()
            
            logger.debug(f"[TASK 2-DEBUG-6] PLC sync result: {result}")
            
            if result.get("success"):
                mo_id = result.get("mo_id")
                logger.debug(f"[TASK 2-DEBUG-7] PLC sync successful for MO: {mo_id}")
                
                if result.get("updated"):
                    logger.info(
                        f"[TASK 2] ? Updated mo_batch for MO: {mo_id} from PLC data"
                    )
                    logger.debug(f"[TASK 2-DEBUG-8] Update details: {result}")
                else:
                    logger.debug(
                        f"[TASK 2-DEBUG] No changes for MO: {mo_id} (data unchanged)"
                    )
            else:
                error = result.get("error", "Unknown error")
                logger.warning(f"[TASK 2] ? PLC sync failed: {error}")
                logger.debug(f"[TASK 2-DEBUG-9] Error details: {result}")
                
        except Exception as e:
            logger.error(f"[TASK 2] ? Error reading from PLC: {e}", exc_info=True)
            logger.error(f"[TASK 2-ERROR] Exception type: {type(e).__name__}")
            
    except Exception as exc:
        logger.exception("[TASK 2] ? ERROR in PLC read sync task: %s", str(exc))
        logger.error(f"[TASK 2-ERROR] Exception type: {type(exc).__name__}")


async def process_completed_batches_task():
    """
    Task 3: Process completed batches for Odoo sync and archival.
    
    FILTER CONDITION: status_manufacturing=1 AND update_odoo=False
    (Only processes batches completed by PLC and not yet synced to Odoo)
    
    Flow per batch:
    1. Sync consumption data to Odoo via process_batch_consumption()
    2. If Odoo sync succeeds:
       - Set update_odoo=True (mark as synced)
       - Move to mo_histories (archive)
       - Delete from mo_batch (remove from queue)
    3. If Odoo sync fails:
       - Log error and keep batch in queue
       - update_odoo remains False
       - Will retry in next Task 3 cycle
    
    Safety: Batch only deleted from mo_batch if Odoo sync succeeds (prevents duplicate syncs)
    """
    try:
        logger.info("\n" + "="*80)
        logger.info("[TASK 3] Process completed batches task running at: %s", datetime.now())
        logger.info("="*80)
        
        db = SessionLocal()
        try:
            # Pre-flight visibility: summarize mo_batch state
            logger.debug("[TASK 3-DEBUG-0] Snapshot mo_batch status counts...")
            try:
                total_count = db.execute(text("SELECT COUNT(*) FROM mo_batch")).scalar() or 0
                active_count = db.execute(
                    text("SELECT COUNT(*) FROM mo_batch WHERE status_manufacturing = false")
                ).scalar() or 0
                completed_count = db.execute(
                    text("SELECT COUNT(*) FROM mo_batch WHERE status_manufacturing = true")
                ).scalar() or 0
                pending_sync_count = db.execute(
                    text(
                        "SELECT COUNT(*) FROM mo_batch "
                        "WHERE status_manufacturing = true AND update_odoo = false"
                    )
                ).scalar() or 0
                synced_count = db.execute(
                    text("SELECT COUNT(*) FROM mo_batch WHERE update_odoo = true")
                ).scalar() or 0

                logger.info(
                    "[TASK 3] mo_batch snapshot: total=%s active=%s completed=%s "
                    "pending_sync=%s update_odoo_true=%s",
                    total_count,
                    active_count,
                    completed_count,
                    pending_sync_count,
                    synced_count,
                )

                sample_rows = db.execute(
                    text(
                        "SELECT mo_id, batch_no, status_manufacturing, update_odoo, last_read_from_plc "
                        "FROM mo_batch ORDER BY last_read_from_plc DESC NULLS LAST LIMIT 5"
                    )
                ).fetchall()
                if sample_rows:
                    logger.debug("[TASK 3-DEBUG-0b] Sample latest batches (mo_id, batch_no, status_mfg, update_odoo, last_read): %s", sample_rows)

                # Per-batch skip reasons (sampled)
                not_completed = db.execute(
                    text(
                        "SELECT mo_id, batch_no, status_manufacturing, update_odoo, last_read_from_plc "
                        "FROM mo_batch WHERE status_manufacturing = false "
                        "ORDER BY last_read_from_plc DESC NULLS LAST LIMIT 5"
                    )
                ).fetchall()
                for row in not_completed or []:
                    logger.info(
                        "[TASK 3] Skip (not completed): mo_id=%s batch_no=%s status_mfg=%s update_odoo=%s last_read=%s",
                        row[0], row[1], row[2], row[3], row[4]
                    )

                already_synced = db.execute(
                    text(
                        "SELECT mo_id, batch_no, status_manufacturing, update_odoo, last_read_from_plc "
                        "FROM mo_batch WHERE status_manufacturing = true AND update_odoo = true "
                        "ORDER BY last_read_from_plc DESC NULLS LAST LIMIT 5"
                    )
                ).fetchall()
                for row in already_synced or []:
                    logger.info(
                        "[TASK 3] Skip (already synced): mo_id=%s batch_no=%s status_mfg=%s update_odoo=%s last_read=%s",
                        row[0], row[1], row[2], row[3], row[4]
                    )
            except Exception as snap_err:
                logger.warning("[TASK 3] Failed to capture mo_batch snapshot: %s", snap_err)

            # Get ONLY completed batches that haven't been synced to Odoo yet
            # Condition: status_manufacturing = 1 AND update_odoo = False
            logger.debug("[TASK 3-DEBUG-1] Querying completed batches pending Odoo sync...")
            logger.debug("[TASK 3-DEBUG-2] Filter: status_manufacturing=1 AND update_odoo=False")
            
            from sqlalchemy import and_
            stmt = select(TableSmoBatch).where(
                and_(
                    TableSmoBatch.status_manufacturing.is_(True),
                    TableSmoBatch.update_odoo.is_(False)
                )
            )
            completed_batches = db.execute(stmt).scalars().all()
            
            logger.debug(f"[TASK 3-DEBUG-3] Query result count: {len(completed_batches)}")
            
            if not completed_batches:
                logger.info("[TASK 3] No completed batches pending Odoo sync")
                return
            
            logger.info(f"[TASK 3] Found {len(completed_batches)} completed batch(es) waiting for Odoo sync")
            for idx, batch in enumerate(completed_batches, 1):
                logger.debug(f"[TASK 3-DEBUG-4.{idx}] Batch: mo_id={batch.mo_id}, batch_no={batch.batch_no}, status={batch.status_manufacturing}, update_odoo={batch.update_odoo}")
            
            consumption_service = get_consumption_service(db)
            history_service = get_mo_history_service(db)
            processed_count = 0
            failed_count = 0
            
            for batch in completed_batches:
                try:
                    mo_id = str(batch.mo_id)
                    batch_no = batch.batch_no
                    
                    logger.info(f"[TASK 3] Processing batch #{batch_no} (MO: {mo_id})...")
                    logger.debug(f"[TASK 3-DEBUG-5] Batch details: batch_no={batch_no}, mo_id={mo_id}, status={batch.status_manufacturing}, update_odoo={batch.update_odoo}")
                    
                    # Prepare batch data untuk Odoo
                    logger.debug(f"[TASK 3-DEBUG-6] Preparing batch payload for Odoo...")
                    
                    batch_data = {
                        "status_manufacturing": 1,
                        "actual_weight_quantity_finished_goods": (
                            float(batch.actual_weight_quantity_finished_goods)  # type: ignore
                            if batch.actual_weight_quantity_finished_goods is not None  # type: ignore
                            else 0.0
                        ),
                    }
                    
                    logger.debug(f"[TASK 3-DEBUG-7] Weight: {batch_data['actual_weight_quantity_finished_goods']}")
                    
                    # Map actual consumption (DB field -> Odoo payload field)
                    silo_consumption_count = 0
                    for letter in "abcdefghijklm":
                        actual_field = f"actual_consumption_silo_{letter}"
                        consumption_field = f"consumption_silo_{letter}"
                        
                        if hasattr(batch, actual_field):
                            value = getattr(batch, actual_field)
                            if value is not None and value > 0:
                                batch_data[consumption_field] = float(value)
                                silo_consumption_count += 1
                                logger.debug(f"[TASK 3-DEBUG-8] Silo {letter.upper()}: {value}")
                    
                    logger.debug(f"[TASK 3-DEBUG-9] Total silos with consumption: {silo_consumption_count}")
                    logger.debug(f"[TASK 3-DEBUG-10] Complete batch payload: {batch_data}")
                    
                    # Send to Odoo
                    equipment_id = str(batch.equipment_id_batch or "PLC01")
                    logger.info(f"[TASK 3] ? Sending Odoo sync request for batch #{batch_no} (MO: {mo_id}, Equipment: {equipment_id})...")
                    logger.debug(f"[TASK 3-DEBUG-11] Calling consumption_service.process_batch_consumption()")
                    logger.debug(f"[TASK 3-DEBUG-12] Parameters: mo_id={mo_id}, equipment_id={equipment_id}")
                    logger.debug(
                        f"[TASK 3-DEBUG-12b] status_mfg={batch.status_manufacturing}, "
                        f"actual_weight={batch.actual_weight_quantity_finished_goods}"
                    )
                    logger.debug(
                        f"[TASK 3-DEBUG-12c] actual_consumption nonzero count="
                        f"{sum(1 for k in batch_data if k.startswith('consumption_silo_'))}"
                    )
                    
                    result = await consumption_service.process_batch_consumption(
                        mo_id=mo_id,
                        equipment_id=equipment_id,
                        batch_data=batch_data
                    )
                    
                    logger.debug(f"[TASK 3-DEBUG-13] Odoo response: {result}")
                    
                    # Treat partial success as failure to avoid false archive
                    consumption_details = (
                        result.get("consumption", {}) or {}
                    ).get("consumption_details", {}) or {}
                    partial_success = consumption_details.get("partial_success", False)
                    errors = consumption_details.get("errors") or []
                    if partial_success or errors:
                        logger.error(
                            f"[TASK 3] ? Odoo sync PARTIAL/ERROR for batch #{batch_no} "
                            f"(MO: {mo_id}). errors={errors}"
                        )
                        logger.debug(
                            f"[TASK 3-DEBUG-13b] Odoo partial response: {consumption_details}"
                        )
                        failed_count += 1
                        continue

                    if result.get("success"):
                        logger.info(f"[TASK 3] ? Odoo sync SUCCESS for batch #{batch_no} (MO: {mo_id})")
                        logger.debug(f"[TASK 3-DEBUG-14] Odoo response message: {result.get('message', 'N/A')}")
                        
                        # Archive + delete in one transaction, and mark update_odoo=True atomically
                        logger.debug(f"[TASK 3-DEBUG-15] Archiving batch #{batch_no} to mo_histories...")
                        if history_service.archive_batch(batch, status="completed", mark_synced=True):
                            processed_count += 1
                            logger.info(
                                f"[TASK 3] ??? COMPLETE: Batch #{batch_no} "
                                f"(MO: {mo_id}) synced & archived"
                            )
                            logger.debug(f"[TASK 3-DEBUG-16] Batch archived and removed from mo_batch")
                        else:
                            logger.error(f"[TASK 3] ? Failed to archive batch #{batch_no}")
                            logger.debug(f"[TASK 3-DEBUG-ERROR-1] archive_batch() returned False")
                            failed_count += 1
                    
                    else:
                        # Odoo sync failed - keep batch in queue, will retry next cycle
                        error_msg = result.get("error", "Unknown error")
                        logger.warning(
                            f"[TASK 3] ? Odoo sync FAILED for batch #{batch_no} (MO: {mo_id}): {error_msg}"
                        )
                        logger.debug(f"[TASK 3-DEBUG-ERROR-3] Odoo sync failure details: {result}")
                        logger.debug(
                            f"[TASK 3-DEBUG-ERROR-4] Batch will remain in queue with update_odoo=False for retry"
                        )
                        failed_count += 1
                
                except Exception as e:
                    logger.error(
                        f"[TASK 3] ? Exception processing batch #{batch.batch_no}: {str(e)}",
                        exc_info=True
                    )
                    logger.error(f"[TASK 3-ERROR] Exception type: {type(e).__name__}")
                    logger.debug(f"[TASK 3-DEBUG-ERROR-5] Full traceback above")
                    failed_count += 1
                    continue
            
            # Summary log
            total = len(completed_batches)
            logger.info(
                f"[TASK 3] Cycle complete: ? {processed_count} archived, ? {failed_count} failed, "
                f"total {total} batches"
            )
            
        finally:
            db.close()
            
    except Exception as exc:
        logger.exception("[TASK 3] Error in process completed batches task: %s", str(exc))


async def monitor_batch_health_task():
    """
    Task 4: Monitor batch health dan detect anomalies.
    Logic:
    1. Check for batches stuck in processing (long time without updates)
    2. Check for batches with unusual consumption patterns
    3. Log warnings for attention
    """
    try:
        logger.info("[TASK 4] Batch health monitoring task running...")
        settings = get_settings()
        now_utc = datetime.now(timezone.utc)
        stuck_threshold = timedelta(minutes=settings.batch_stuck_threshold_minutes)

        db = SessionLocal()
        try:
            # Get all active batches
            stmt = select(TableSmoBatch).where(
                TableSmoBatch.status_manufacturing.is_(False)
            )
            result = db.execute(stmt)
            active_batches = result.scalars().all()
            
            if not active_batches:
                logger.info("[TASK 4] No active batches to monitor")
                return

            stuck_batches = 0
            warning_batches = 0
            healthy_batches = 0

            for batch in active_batches:
                batch_no = batch.batch_no
                mo_id = batch.mo_id
                status_operation_raw = batch.status_operation
                status_operation = status_operation_raw is True

                if status_operation:
                    warning_batches += 1
                    logger.warning(
                        "[TASK 4] Batch warning: status_operation=1 while still active "
                        "(batch_no=%s, mo_id=%s)",
                        batch_no,
                        mo_id,
                    )

                last_read_raw = batch.last_read_from_plc
                if not isinstance(last_read_raw, datetime):
                    warning_batches += 1
                    logger.warning(
                        "[TASK 4] Batch has no PLC read timestamp yet "
                        "(batch_no=%s, mo_id=%s)",
                        batch_no,
                        mo_id,
                    )
                    continue

                last_read = cast(datetime, last_read_raw)

                if getattr(last_read, "tzinfo", None) is None:
                    last_read = last_read.replace(tzinfo=timezone.utc)

                age = now_utc - last_read
                if age > stuck_threshold:
                    stuck_batches += 1
                    logger.warning(
                        "[TASK 4] Batch appears stuck (age=%s > threshold=%s) "
                        "(batch_no=%s, mo_id=%s, last_read=%s)",
                        age,
                        stuck_threshold,
                        batch_no,
                        mo_id,
                        last_read.isoformat(),
                    )
                else:
                    healthy_batches += 1

            logger.info(
                "[TASK 4] Health summary: total=%s healthy=%s stuck=%s warnings=%s threshold=%s",
                len(active_batches),
                healthy_batches,
                stuck_batches,
                warning_batches,
                stuck_threshold,
            )
            
        finally:
            db.close()
            
    except Exception as exc:
        logger.exception("[TASK 4] Error in batch health monitoring task: %s", str(exc))


async def equipment_failure_monitoring_task():
    """
    Task 5: Monitor dan read equipment failure data dari PLC secara periodik.
    Logic:
    1. Read equipment failure reference data dari PLC menggunakan EQUIPMENT_FAILURE_REFERENCE.json
    2. Simpan ke local database dengan change detection (save_if_changed)
    3. Sync data ke Odoo API via equipment_failure_service.create_failure_report()
    4. Log semua tahap pipeline untuk debugging
    
    Debug Flow:
    [TASK 5] START
    [TASK 5] Step 1: Read from PLC
      - Equipment: {equipment_code}
      - Failure: {failure_info}
      - Timestamp: {failure_timestamp}
    [TASK 5] Step 2: Local DB Save
      - Status: {"saved": true/false}
      - Record ID: {id}
    [TASK 5] Step 3: Odoo API Sync
      - Auth: Authenticating...
      - Request: POST /api/scada/failure-report
      - Response: {status}
    [TASK 5] END
    """
    try:
        logger.info("[TASK 5] ========== START Equipment Failure Monitoring Task ==========")
        
        try:
            # STEP 1: READ FROM PLC
            logger.info("[TASK 5] Step 1: Reading equipment failure from PLC...")
            failure_service = get_equipment_failure_service()
            failure_data = await failure_service.read_equipment_failure_data()
            
            if failure_data:
                equipment_code = failure_data.get("equipment_code")
                failure_info = failure_data.get("failure_info")
                failure_timestamp = failure_data.get("failure_timestamp")
                
                logger.warning(
                    f"[TASK 5] ? Equipment Failure Detected from PLC:\n"
                    f"  Equipment Code: {equipment_code} (type: {type(equipment_code).__name__})\n"
                    f"  Failure Type: {failure_info} (type: {type(failure_info).__name__})\n"
                    f"  Timestamp: {failure_timestamp} (type: {type(failure_timestamp).__name__})"
                )

                failure_date = None
                if isinstance(failure_timestamp, str) and failure_timestamp.strip():
                    try:
                        failure_date = datetime.strptime(
                            failure_timestamp,
                            "%Y-%m-%d %H:%M:%S",
                        )
                        logger.info(f"[TASK 5] ? Parsed failure_date: {failure_date}")
                    except ValueError as e:
                        logger.warning(
                            f"[TASK 5] ? Invalid timestamp format: {failure_timestamp} - {e}"
                        )

                if equipment_code and failure_info and failure_date:
                    db = SessionLocal()
                    try:
                        # STEP 2: SAVE TO LOCAL DATABASE
                        logger.info("[TASK 5] Step 2: Saving to local database with change detection...")
                        db_service = EquipmentFailureDbService(db)
                        save_result = db_service.save_if_changed(
                            equipment_code=str(equipment_code),
                            description=str(failure_info),
                            failure_date=failure_date,
                            source="plc",
                        )
                        
                        if save_result.get("saved"):
                            logger.info(
                                f"[TASK 5] ? Equipment failure saved to DB\n"
                                f"  Record ID: {save_result.get('record_id')}\n"
                                f"  Equipment: {equipment_code}\n"
                                f"  Description: {failure_info}"
                            )
                            
                            # STEP 3: SYNC TO ODOO API
                            logger.info("[TASK 5] Step 3: Syncing to Odoo via API...")
                            try:
                                failure_api_service = await get_equipment_failure_api_service(db)
                                
                                # Format datetime untuk Odoo
                                failure_date_str = failure_date.strftime("%Y-%m-%d %H:%M:%S")
                                
                                logger.info(
                                    f"[TASK 5] Calling Odoo API create_failure_report:\n"
                                    f"  URL: {get_settings().odoo_base_url}/api/scada/equipment-failure\n"
                                    f"  Equipment: {equipment_code}\n"
                                    f"  Description: {failure_info}\n"
                                    f"  Date: {failure_date_str}"
                                )
                                
                                odoo_result = await failure_api_service.create_failure_report(
                                    equipment_code=equipment_code,
                                    description=failure_info,
                                    date=failure_date_str,
                                )
                                
                                if odoo_result.get("success"):
                                    logger.info(
                                        f"[TASK 5] ? Odoo sync successful\n"
                                        f"  Status: {odoo_result.get('status')}\n"
                                        f"  Message: {odoo_result.get('message')}\n"
                                        f"  Data: {odoo_result.get('data')}"
                                    )
                                else:
                                    logger.error(
                                        f"[TASK 5] ? Odoo sync failed\n"
                                        f"  Status: {odoo_result.get('status')}\n"
                                        f"  Message: {odoo_result.get('message')}"
                                    )
                            except Exception as odoo_error:
                                logger.error(
                                    f"[TASK 5] ? Exception during Odoo sync: {odoo_error}",
                                    exc_info=True
                                )
                        else:
                            logger.debug(
                                f"[TASK 5] ? Skipped DB save (duplicate detection)\n"
                                f"  Reason: {save_result.get('reason')}\n"
                                f"  Equipment: {equipment_code}"
                            )
                    finally:
                        db.close()
                else:
                    logger.debug(
                        f"[TASK 5] ? Missing data for DB save:\n"
                        f"  equipment_code={equipment_code}\n"
                        f"  failure_info={failure_info}\n"
                        f"  failure_date={failure_date}"
                    )
                
            else:
                logger.debug("[TASK 5] No equipment failure detected or read failed")
                
        except Exception as e:
            logger.error(f"[TASK 5] Error reading equipment failure from PLC: {e}", exc_info=True)
        
        logger.info("[TASK 5] ========== END Equipment Failure Monitoring Task ==========\n")
            
    except Exception as exc:
        logger.exception("[TASK 5] Error in equipment failure monitoring task: %s", str(exc))


async def system_log_cleanup_task():
    """
    Task 6: Cleanup old logs from system_log table.

    Rules:
    - Delete logs older than LOG_RETENTION_DAYS
    - Keep latest LOG_CLEANUP_KEEP_LAST rows as safety
    """
    settings = get_settings()
    retention_days = settings.log_retention_days
    keep_last = settings.log_cleanup_keep_last

    if retention_days < 1:
        logger.warning(
            "[TASK 6] Skip cleanup: LOG_RETENTION_DAYS must be >= 1, got %s",
            retention_days,
        )
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    db = SessionLocal()
    try:
        query = db.query(SystemLog).filter(SystemLog.timestamp < cutoff)
        if keep_last > 0:
            keep_subquery = (
                select(SystemLog.id)
                .order_by(desc(SystemLog.timestamp))
                .limit(keep_last)
            )
            query = query.filter(~SystemLog.id.in_(keep_subquery))

        deleted = query.delete(synchronize_session=False)
        db.commit()
        logger.info(
            "[TASK 6] Log cleanup completed. deleted=%s cutoff=%s keep_last=%s",
            deleted,
            cutoff.isoformat(),
            keep_last,
        )
    except Exception as exc:
        db.rollback()
        logger.exception("[TASK 6] Error in log cleanup task: %s", str(exc))
    finally:
        db.close()


def start_scheduler():
    """Start enhanced background scheduler dengan multiple tasks."""
    global scheduler
    
    settings = get_settings()
    
    if not settings.enable_auto_sync:
        logger.info("Scheduler is DISABLED in .env (ENABLE_AUTO_SYNC=false)")
        return
    
    # Configure AsyncIOScheduler dengan optimized options
    scheduler = AsyncIOScheduler(
        job_defaults={
            'coalesce': True,           # Merge multiple missed trigger runs into one execution
            'max_instances': 1,         # Prevent concurrent execution of same job
            'misfire_grace_time': 30    # Grace period 30s sebelum log warning
        }
    )
    
    # Task 1: Auto-sync MO dari Odoo (every 60 minutes by default)
    if settings.enable_task_1_auto_sync:
        scheduler.add_job(
            auto_sync_mo_task,
            trigger="interval",
            minutes=settings.sync_interval_minutes,
            id="auto_sync_mo",
            replace_existing=True,
        )
        logger.info(
            f"? Task 1: Auto-sync MO scheduler added "
            f"(interval: {settings.sync_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"? Task 1: Auto-sync MO scheduler DISABLED (ENABLE_TASK_1_AUTO_SYNC=false)")
    
    # Task 2: PLC read sync (every 5 minutes for near real-time updates)
    if settings.enable_task_2_plc_read:
        scheduler.add_job(
            plc_read_sync_task,
            trigger="interval",
            minutes=settings.plc_read_interval_minutes,
            id="plc_read_sync",
            replace_existing=True,
        )
        logger.info(
            f"? Task 2: PLC read sync scheduler added "
            f"(interval: {settings.plc_read_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"? Task 2: PLC read sync scheduler DISABLED (ENABLE_TASK_2_PLC_READ=false)")
    
    # Task 3: Process completed batches (every 3 minutes)
    if settings.enable_task_3_process_completed:
        scheduler.add_job(
            process_completed_batches_task,
            trigger="interval",
            minutes=settings.process_completed_interval_minutes,
            id="process_completed_batches",
            replace_existing=True,
        )
        logger.info(
            f"? Task 3: Process completed batches scheduler added "
            f"(interval: {settings.process_completed_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"? Task 3: Process completed batches scheduler DISABLED (ENABLE_TASK_3_PROCESS_COMPLETED=false)")
    
    # Task 4: Monitor batch health (every 10 minutes)
    if settings.enable_task_4_health_monitor:
        scheduler.add_job(
            monitor_batch_health_task,
            trigger="interval",
            minutes=settings.health_monitor_interval_minutes,
            id="monitor_batch_health",
            replace_existing=True,
        )
        logger.info(
            f"? Task 4: Batch health monitoring scheduler added "
            f"(interval: {settings.health_monitor_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"? Task 4: Batch health monitoring scheduler DISABLED (ENABLE_TASK_4_HEALTH_MONITOR=false)")
    
    # Task 5: Equipment failure monitoring (every 5 minutes by default)
    if settings.enable_task_5_equipment_failure:
        scheduler.add_job(
            equipment_failure_monitoring_task,
            trigger="interval",
            minutes=settings.equipment_failure_interval_minutes,
            id="equipment_failure_monitor",
            replace_existing=True,
        )
        logger.info(
            f"? Task 5: Equipment failure monitoring scheduler added "
            f"(interval: {settings.equipment_failure_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"? Task 5: Equipment failure monitoring scheduler DISABLED (ENABLE_TASK_5_EQUIPMENT_FAILURE=false)")

    # Task 6: System log cleanup (daily by default)
    if settings.enable_task_6_log_cleanup:
        scheduler.add_job(
            system_log_cleanup_task,
            trigger="interval",
            minutes=settings.log_cleanup_interval_minutes,
            id="system_log_cleanup",
            replace_existing=True,
        )
        logger.info(
            f"? Task 6: System log cleanup scheduler added "
            f"(interval: {settings.log_cleanup_interval_minutes} minutes, "
            f"retention: {settings.log_retention_days} days, "
            f"keep_last: {settings.log_cleanup_keep_last})"
        )
    else:
        logger.warning("? Task 6: System log cleanup scheduler DISABLED (ENABLE_TASK_6_LOG_CLEANUP=false)")
    
    scheduler.start()
    
    # Count enabled tasks
    enabled_tasks = [
        settings.enable_task_1_auto_sync,
        settings.enable_task_2_plc_read,
        settings.enable_task_3_process_completed,
        settings.enable_task_4_health_monitor,
        settings.enable_task_5_equipment_failure,
        settings.enable_task_6_log_cleanup,
    ]
    task_count = sum(enabled_tasks)
    
    logger.info(
        f"??? Enhanced Scheduler STARTED with {task_count}/6 tasks enabled ???\n"
        f"  - Task 1: Auto-sync MO ({settings.sync_interval_minutes} min) - {'?' if settings.enable_task_1_auto_sync else '?'}\n"
        f"  - Task 2: PLC read sync ({settings.plc_read_interval_minutes} min) - {'?' if settings.enable_task_2_plc_read else '?'}\n"
        f"  - Task 3: Process completed ({settings.process_completed_interval_minutes} min) - {'?' if settings.enable_task_3_process_completed else '?'}\n"
        f"  - Task 4: Health monitoring ({settings.health_monitor_interval_minutes} min) - {'?' if settings.enable_task_4_health_monitor else '?'}\n"
        f"  - Task 5: Equipment failure ({settings.equipment_failure_interval_minutes} min) - {'?' if settings.enable_task_5_equipment_failure else '?'}\n"
        f"  - Task 6: Log cleanup ({settings.log_cleanup_interval_minutes} min) - {'?' if settings.enable_task_6_log_cleanup else '?'}"
    )


def stop_scheduler():
    """Stop enhanced background scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("? Enhanced scheduler stopped (all tasks terminated)")


@asynccontextmanager
async def scheduler_lifespan() -> AsyncGenerator[None, None]:
    """
    Context manager untuk FastAPI lifespan.
    Digunakan untuk start/stop scheduler saat app startup/shutdown.
    """
    start_scheduler()
    yield
    stop_scheduler()
