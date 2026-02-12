"""
Background scheduler untuk auto-sync MO dari Odoo ke mo_batch table.
Hanya sync jika table kosong (PLC sudah selesai proses semua batch).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.mo_batch_service import sync_mo_list_to_db
from app.services.odoo_auth_service import fetch_mo_list_detailed

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def auto_sync_mo_task():
    """
    Task untuk sync MO dari Odoo.
    Logic:
    1. Cek apakah table mo_batch kosong
    2. Jika kosong: fetch 10 batch terbaru dari Odoo
    3. Jika ada data: skip (tunggu PLC selesai proses)
    """
    settings = get_settings()
    
    try:
        logger.info("Auto-sync task running...")
        
        # 1. Cek apakah table mo_batch kosong
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM mo_batch"))
            count = result.scalar() or 0
        
        if count > 0:
            logger.info(
                f"Table mo_batch has {count} records. "
                "Skipping sync - waiting for PLC to complete all batches."
            )
            return
        
        logger.info("Table mo_batch is empty. Fetching new batches from Odoo...")
        
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
            logger.info(f"✓ Auto-sync completed: {len(mo_list)} MO batches synced")
        finally:
            db.close()
            
    except Exception as exc:
        logger.exception("Error in auto-sync task: %s", str(exc))


def start_scheduler():
    """Start background scheduler untuk auto-sync."""
    global scheduler
    
    settings = get_settings()
    
    if not settings.enable_auto_sync:
        logger.info("Auto-sync is DISABLED in .env (ENABLE_AUTO_SYNC=false)")
        return
    
    scheduler = AsyncIOScheduler()
    
    # Add job dengan interval dari config
    scheduler.add_job(
        auto_sync_mo_task,
        trigger="interval",
        minutes=settings.sync_interval_minutes,
        id="auto_sync_mo",
        replace_existing=True,
        max_instances=1,  # Prevent concurrent runs
    )
    
    scheduler.start()
    logger.info(
        f"✓ Auto-sync scheduler STARTED: "
        f"interval={settings.sync_interval_minutes} minutes, "
        f"batch_limit={settings.sync_batch_limit}"
    )


def stop_scheduler():
    """Stop background scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Auto-sync scheduler stopped")


@asynccontextmanager
async def scheduler_lifespan() -> AsyncGenerator[None, None]:
    """
    Context manager untuk FastAPI lifespan.
    Digunakan untuk start/stop scheduler saat app startup/shutdown.
    """
    start_scheduler()
    yield
    stop_scheduler()
