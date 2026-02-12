"""
Admin routes untuk manage auto-sync scheduler dan mo_batch table
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text, Result
from sqlalchemy.orm import Session

from app.core.scheduler import auto_sync_mo_task
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/admin/clear-mo-batch")
async def clear_mo_batch(db: Session = Depends(get_db)) -> Any:
    """
    Clear all records from mo_batch table.
    Gunakan endpoint ini setelah PLC selesai proses semua batch.
    """
    try:
        # Get count before deleting
        count_result = db.execute(text("SELECT COUNT(*) FROM mo_batch"))
        deleted_count = count_result.scalar() or 0
        
        # Delete all records
        db.execute(text("DELETE FROM mo_batch"))
        db.commit()
        
        logger.info(f"mo_batch table cleared: {deleted_count} records deleted")
        
        return {
            "status": "success",
            "message": f"mo_batch table cleared successfully",
            "deleted_count": deleted_count,
        }
    except Exception as exc:
        db.rollback()
        logger.exception("Error clearing mo_batch table: %s", str(exc))
        raise


@router.post("/admin/trigger-sync")
async def trigger_sync_manually() -> Any:
    """
    Manually trigger auto-sync task.
    Berguna untuk testing atau force sync tanpa tunggu interval.
    """
    try:
        logger.info("Manual sync triggered via API")
        await auto_sync_mo_task()
        
        return {
            "status": "success",
            "message": "Manual sync completed successfully",
        }
    except Exception as exc:
        logger.exception("Error in manual sync: %s", str(exc))
        return {
            "status": "error",
            "message": f"Manual sync failed: {str(exc)}",
        }


@router.get("/admin/batch-status")
async def get_batch_status(db: Session = Depends(get_db)) -> Any:
    """
    Get current status of mo_batch table.
    """
    try:
        result = db.execute(text("SELECT COUNT(*) FROM mo_batch"))
        count = result.scalar() or 0
        
        batches = []
        if count > 0:
            result = db.execute(
                text("""
                SELECT batch_no, mo_id, equipment_id_batch, consumption
                FROM mo_batch 
                ORDER BY batch_no
                """)
            )
            batches = [
                {
                    "batch_no": row.batch_no,
                    "mo_id": row.mo_id,
                    "equipment": row.equipment_id_batch,
                    "consumption": float(row.consumption) if row.consumption else 0.0,
                }
                for row in result
            ]
        
        return {
            "status": "success",
            "data": {
                "total_batches": count,
                "is_empty": count == 0,
                "batches": batches,
            },
        }
    except Exception as exc:
        logger.exception("Error getting batch status: %s", str(exc))
        raise
