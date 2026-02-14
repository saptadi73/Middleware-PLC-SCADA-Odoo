"""
Enhanced Background Scheduler for Multiple Tasks:
1. Auto-sync MO dari Odoo ke mo_batch table
2. Read PLC memory dan update mo_batch (periodic)
3. Process completed/failed batches untuk update ke Odoo dan move ke history
4. Monitor dan notification untuk batch failures
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine, text, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.mo_batch_service import sync_mo_list_to_db
from app.services.odoo_auth_service import fetch_mo_list_detailed
from app.services.plc_sync_service import get_plc_sync_service
from app.services.mo_history_service import get_mo_history_service
from app.services.odoo_consumption_service import get_consumption_service
from app.models.tablesmo_batch import TableSmoBatch

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def auto_sync_mo_task():
    """
    Task 1: Sync MO dari Odoo ke mo_batch.
    Logic:
    1. Cek apakah table mo_batch kosong
    2. Jika kosong: fetch batches from Odoo
    3. Jika ada data: skip (tunggu PLC selesai proses)
    
    Note: Cancelled batches already removed from mo_batch (moved to mo_histories),
    so they won't be counted in the empty check.
    """
    settings = get_settings()
    
    try:
        logger.info("[TASK 1] Auto-sync MO task running...")
        
        # 1. Cek apakah table mo_batch kosong
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
            count = result.scalar() or 0
        
        if count > 0:
            logger.info(
                f"[TASK 1] Table mo_batch has {count} records. "
                "Skipping sync - waiting for PLC to complete all batches."
            )
            return
        
        logger.info("[TASK 1] Table mo_batch is empty. Fetching new batches from Odoo...")
        
        # 2. Fetch dari Odoo
        payload = await fetch_mo_list_detailed(
            limit=settings.sync_batch_limit,
            offset=0
        )
        
        result = payload.get("result", {})
        mo_list = result.get("data", [])
        
        # 3. Sync ke database
        db = SessionLocal()
        try:
            sync_mo_list_to_db(db, mo_list)
            logger.info(f"[TASK 1] ✓ Auto-sync completed: {len(mo_list)} MO batches synced")
        finally:
            db.close()
            
    except Exception as exc:
        logger.exception("[TASK 1] Error in auto-sync task: %s", str(exc))


async def plc_read_sync_task():
    """
    Task 2: Read PLC memory dan update mo_batch secara periodik.
    
    Logic (Optimized):
    1. Read PLC memory once per cycle (PLC memory contains one active MO at a time)
    2. Update corresponding mo_batch record dengan actual consumption dan status
    3. Skip jika status_manufacturing sudah 1 (completed) - handled by sync_from_plc()
    
    Note: No need to loop per batch karena PLC hanya process satu MO pada satu waktu.
    """
    try:
        logger.info("[TASK 2] PLC read sync task running...")
        
        # Cek apakah ada active batches
        db = SessionLocal()
        try:
            stmt = select(TableSmoBatch).where(
                TableSmoBatch.status_manufacturing.is_(False)
            )
            result = db.execute(stmt)
            active_batches_count = len(result.scalars().all())
            
            if active_batches_count == 0:
                logger.info("[TASK 2] No active batches to sync from PLC")
                return
            
            logger.info(f"[TASK 2] Found {active_batches_count} active batch(es) in queue")
            
        finally:
            db.close()
        
        # Read PLC once per cycle (PLC memory only contains one active MO)
        plc_service = get_plc_sync_service()
        
        try:
            result = plc_service.sync_from_plc()
            
            if result.get("success"):
                if result.get("updated"):
                    mo_id = result.get("mo_id")
                    logger.info(
                        f"[TASK 2] ✓ Updated batch for MO: {mo_id} from PLC"
                    )
                else:
                    mo_id = result.get("mo_id")
                    logger.debug(
                        f"[TASK 2] No changes for MO: {mo_id} (data unchanged)"
                    )
            else:
                error = result.get("error", "Unknown error")
                logger.warning(f"[TASK 2] PLC sync failed: {error}")
                
        except Exception as e:
            logger.error(f"[TASK 2] Error reading from PLC: {e}", exc_info=True)
            
    except Exception as exc:
        logger.exception("[TASK 2] Error in PLC read sync task: %s", str(exc))


async def process_completed_batches_task():
    """
    Task 3: Process completed batches (status_manufacturing = 1).
    Logic:
    1. Find all completed batches
    2. Update consumption ke Odoo
    3. Mark MO as done di Odoo
    4. Move to history
    5. Delete from mo_batch
    """
    try:
        logger.info("[TASK 3] Process completed batches task running...")
        
        db = SessionLocal()
        try:
            # Get completed batches
            history_service = get_mo_history_service(db)
            completed_batches = history_service.get_completed_batches()
            
            if not completed_batches:
                logger.info("[TASK 3] No completed batches to process")
                return
            
            logger.info(f"[TASK 3] Found {len(completed_batches)} completed batches")
            
            consumption_service = get_consumption_service(db)
            processed_count = 0
            
            for batch in completed_batches:
                try:
                    mo_id = str(batch.mo_id)
                    logger.info(
                        f"[TASK 3] Processing completed batch {batch.batch_no} "
                        f"(MO: {mo_id})"
                    )
                    
                    # Prepare batch data untuk Odoo
                    # Note: Gunakan naming 'consumption_silo_{letter}' (bukan 'actual_consumption_silo_{letter}')
                    # agar konsisten dengan contract process_batch_consumption()
                    batch_data = {
                        "status_manufacturing": 1,
                        "actual_weight_quantity_finished_goods": (
                            float(batch.actual_weight_quantity_finished_goods)  # type: ignore
                            if batch.actual_weight_quantity_finished_goods is not None  # type: ignore
                            else 0.0
                        ),
                    }
                    
                    # Map actual consumption dari database -> consumption payload untuk Odoo
                    # Field di DB: actual_consumption_silo_{letter}
                    # Field di payload: consumption_silo_{letter} (contract process_batch_consumption)
                    for letter in "abcdefghijklm":
                        actual_field = f"actual_consumption_silo_{letter}"
                        consumption_field = f"consumption_silo_{letter}"
                        
                        if hasattr(batch, actual_field):
                            value = getattr(batch, actual_field)
                            if value is not None and value > 0:
                                batch_data[consumption_field] = float(value)
                    
                    # Update ke Odoo
                    equipment_id = str(batch.equipment_id_batch or "PLC01")
                    result = await consumption_service.process_batch_consumption(
                        mo_id=mo_id,
                        equipment_id=equipment_id,
                        batch_data=batch_data
                    )
                    
                    if result.get("success"):
                        # Move to history
                        history = history_service.move_to_history(
                            batch, status="completed"
                        )
                        
                        if history:
                            # Delete from mo_batch
                            if history_service.delete_from_batch(batch):
                                processed_count += 1
                                logger.info(
                                    f"[TASK 3] ✓ Processed and archived MO {mo_id}"
                                )
                            else:
                                logger.error(
                                    f"[TASK 3] Failed to delete MO {mo_id} from mo_batch"
                                )
                        else:
                            logger.error(
                                f"[TASK 3] Failed to move MO {mo_id} to history"
                            )
                    else:
                        logger.error(
                            f"[TASK 3] Failed to update Odoo for MO {mo_id}: "
                            f"{result.get('error')}"
                        )
                
                except Exception as e:
                    logger.error(
                        f"[TASK 3] Error processing batch {batch.batch_no}: {e}",
                        exc_info=True
                    )
                    continue
            
            logger.info(
                f"[TASK 3] ✓ Completed batches processing finished: "
                f"{processed_count}/{len(completed_batches)} batches processed"
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
            
            # TODO: Add monitoring logic
            # - Check last_read_from_plc timestamp untuk detect stuck batches
            # - Check consumption values untuk detect anomalies
            # - Trigger notifications jika needed
            
            logger.info(f"[TASK 4] Monitored {len(active_batches)} active batches")
            
        finally:
            db.close()
            
    except Exception as exc:
        logger.exception("[TASK 4] Error in batch health monitoring task: %s", str(exc))


def start_scheduler():
    """Start enhanced background scheduler dengan multiple tasks."""
    global scheduler
    
    settings = get_settings()
    
    if not settings.enable_auto_sync:
        logger.info("Scheduler is DISABLED in .env (ENABLE_AUTO_SYNC=false)")
        return
    
    scheduler = AsyncIOScheduler()
    
    # Task 1: Auto-sync MO dari Odoo (every 60 minutes by default)
    if settings.enable_task_1_auto_sync:
        scheduler.add_job(
            auto_sync_mo_task,
            trigger="interval",
            minutes=settings.sync_interval_minutes,
            id="auto_sync_mo",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            f"✓ Task 1: Auto-sync MO scheduler added "
            f"(interval: {settings.sync_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"⊘ Task 1: Auto-sync MO scheduler DISABLED (ENABLE_TASK_1_AUTO_SYNC=false)")
    
    # Task 2: PLC read sync (every 5 minutes for near real-time updates)
    if settings.enable_task_2_plc_read:
        scheduler.add_job(
            plc_read_sync_task,
            trigger="interval",
            minutes=settings.plc_read_interval_minutes,
            id="plc_read_sync",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            f"✓ Task 2: PLC read sync scheduler added "
            f"(interval: {settings.plc_read_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"⊘ Task 2: PLC read sync scheduler DISABLED (ENABLE_TASK_2_PLC_READ=false)")
    
    # Task 3: Process completed batches (every 3 minutes)
    if settings.enable_task_3_process_completed:
        scheduler.add_job(
            process_completed_batches_task,
            trigger="interval",
            minutes=settings.process_completed_interval_minutes,
            id="process_completed_batches",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            f"✓ Task 3: Process completed batches scheduler added "
            f"(interval: {settings.process_completed_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"⊘ Task 3: Process completed batches scheduler DISABLED (ENABLE_TASK_3_PROCESS_COMPLETED=false)")
    
    # Task 4: Monitor batch health (every 10 minutes)
    if settings.enable_task_4_health_monitor:
        scheduler.add_job(
            monitor_batch_health_task,
            trigger="interval",
            minutes=settings.health_monitor_interval_minutes,
            id="monitor_batch_health",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            f"✓ Task 4: Batch health monitoring scheduler added "
            f"(interval: {settings.health_monitor_interval_minutes} minutes)"
        )
    else:
        logger.warning(f"⊘ Task 4: Batch health monitoring scheduler DISABLED (ENABLE_TASK_4_HEALTH_MONITOR=false)")
    
    scheduler.start()
    
    # Count enabled tasks
    enabled_tasks = [
        settings.enable_task_1_auto_sync,
        settings.enable_task_2_plc_read,
        settings.enable_task_3_process_completed,
        settings.enable_task_4_health_monitor,
    ]
    task_count = sum(enabled_tasks)
    
    logger.info(
        f"✓✓✓ Enhanced Scheduler STARTED with {task_count}/4 tasks enabled ✓✓✓\n"
        f"  - Task 1: Auto-sync MO ({settings.sync_interval_minutes} min) - {'✓' if settings.enable_task_1_auto_sync else '⊘'}\n"
        f"  - Task 2: PLC read sync ({settings.plc_read_interval_minutes} min) - {'✓' if settings.enable_task_2_plc_read else '⊘'}\n"
        f"  - Task 3: Process completed ({settings.process_completed_interval_minutes} min) - {'✓' if settings.enable_task_3_process_completed else '⊘'}\n"
        f"  - Task 4: Health monitoring ({settings.health_monitor_interval_minutes} min) - {'✓' if settings.enable_task_4_health_monitor else '⊘'}"
    )


def stop_scheduler():
    """Stop enhanced background scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("✓ Enhanced scheduler stopped (all tasks terminated)")


@asynccontextmanager
async def scheduler_lifespan() -> AsyncGenerator[None, None]:
    """
    Context manager untuk FastAPI lifespan.
    Digunakan untuk start/stop scheduler saat app startup/shutdown.
    """
    start_scheduler()
    yield
    stop_scheduler()
