"""
Admin routes untuk manage scheduler, mo_batch table, dan monitoring
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, select
from sqlalchemy.orm import Session

from app.core.scheduler import auto_sync_mo_task, plc_read_sync_task, process_completed_batches_task
from app.db.session import get_db
from app.services.mo_history_service import get_mo_history_service
from app.models.tablesmo_batch import TableSmoBatch
from app.services.odoo_consumption_service import get_consumption_service

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
    Get current status of mo_batch table dengan detail per batch.
    """
    try:
        result = db.execute(text("SELECT COUNT(*) FROM mo_batch"))
        count = result.scalar() or 0
        
        batches = []
        if count > 0:
            result = db.execute(
                text("""
                SELECT batch_no, mo_id, equipment_id_batch, consumption,
                       status_manufacturing, status_operation,
                       actual_weight_quantity_finished_goods,
                       last_read_from_plc
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
                    "status_manufacturing": bool(row.status_manufacturing),
                    "status_operation": bool(row.status_operation),
                    "actual_finished_goods": (
                        float(row.actual_weight_quantity_finished_goods)  # type: ignore
                        if row.actual_weight_quantity_finished_goods is not None  # type: ignore
                        else 0.0
                    ),
                    "last_read_from_plc": (
                        row.last_read_from_plc.isoformat()  # type: ignore
                        if row.last_read_from_plc is not None  # type: ignore
                        else None
                    ),
                }
                for row in result
            ]
        
        # Count by status
        active_count = len([b for b in batches if not b["status_manufacturing"]])
        completed_count = len([b for b in batches if b["status_manufacturing"]])
        
        return {
            "status": "success",
            "data": {
                "total_batches": count,
                "active_batches": active_count,
                "completed_batches": completed_count,
                "is_empty": count == 0,
                "batches": batches,
            },
        }
    except Exception as exc:
        logger.exception("Error getting batch status: %s", str(exc))
        raise


@router.get("/admin/monitor/real-time")
async def get_realtime_monitoring(db: Session = Depends(get_db)) -> Any:
    """
    Get real-time monitoring dashboard data.
    Menampilkan status semua batch secara real-time.
    """
    try:
        # Get all batches dengan detail
        stmt = select(TableSmoBatch).order_by(TableSmoBatch.batch_no)
        result = db.execute(stmt)
        batches = result.scalars().all()
        
        # Categorize batches
        in_progress = []
        completed = []
        
        for batch in batches:
            batch_info = {
                "batch_no": batch.batch_no,
                "mo_id": batch.mo_id,
                "equipment_id": batch.equipment_id_batch,
                "finished_goods": batch.finished_goods,
                "status_manufacturing": bool(batch.status_manufacturing),
                "status_operation": bool(batch.status_operation),
                "actual_weight": (
                    float(batch.actual_weight_quantity_finished_goods)  # type: ignore
                    if batch.actual_weight_quantity_finished_goods is not None  # type: ignore
                    else 0.0
                ),
                "last_read": (
                    batch.last_read_from_plc.isoformat()  # type: ignore
                    if batch.last_read_from_plc is not None  # type: ignore
                    else None
                ),
                "actual_consumptions": {
                    f"silo_{letter}": (
                        float(getattr(batch, f"actual_consumption_silo_{letter}"))
                        if getattr(batch, f"actual_consumption_silo_{letter}")
                        else 0.0
                    )
                    for letter in "abcdefghijklm"
                    if getattr(batch, f"actual_consumption_silo_{letter}", 0) > 0
                },
            }
            
            if batch.status_manufacturing:  # type: ignore
                completed.append(batch_info)
            else:
                in_progress.append(batch_info)
        
        return {
            "status": "success",
            "data": {
                "summary": {
                    "total": len(batches),
                    "in_progress": len(in_progress),
                    "completed": len(completed),
                },
                "in_progress": in_progress,
                "completed": completed,
            },
        }
    except Exception as exc:
        logger.exception("Error getting realtime monitoring: %s", str(exc))
        raise


@router.get("/admin/history")
async def get_batch_history(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """
    Get history of processed batches (completed and failed).
    Support pagination.
    """
    try:
        history_service = get_mo_history_service(db)
        histories = history_service.get_history(limit=limit, offset=offset)
        
        history_list = [
            {
                "id": str(history.id),
                "batch_no": history.batch_no,
                "mo_id": history.mo_id,
                "finished_goods": history.finished_goods,
                "equipment_id": history.equipment_id_batch,
                "status_manufacturing": bool(history.status_manufacturing),
                "actual_weight": (
                    float(history.actual_weight_quantity_finished_goods)  # type: ignore
                    if history.actual_weight_quantity_finished_goods is not None  # type: ignore
                    else 0.0
                ),
                "last_read": (
                    history.last_read_from_plc.isoformat()  # type: ignore
                    if history.last_read_from_plc is not None  # type: ignore
                    else None
                ),
                "actual_consumptions": {
                    f"silo_{letter}": (
                        float(getattr(history, f"actual_consumption_silo_{letter}"))
                        if getattr(history, f"actual_consumption_silo_{letter}")
                        else 0.0
                    )
                    for letter in "abcdefghijklm"
                    if getattr(history, f"actual_consumption_silo_{letter}", 0) > 0
                },
            }
            for history in histories
        ]
        
        return {
            "status": "success",
            "data": {
                "total": len(history_list),
                "limit": limit,
                "offset": offset,
                "histories": history_list,
            },
        }
    except Exception as exc:
        logger.exception("Error getting batch history: %s", str(exc))
        raise


@router.get("/admin/history/{mo_id}")
async def get_batch_history_by_mo(
    mo_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """
    Get history for specific MO ID.
    """
    try:
        history_service = get_mo_history_service(db)
        history = history_service.get_history_by_mo_id(mo_id)
        
        if not history:
            return {
                "status": "error",
                "message": f"History not found for MO ID: {mo_id}",
            }
        
        return {
            "status": "success",
            "data": {
                "id": str(history.id),
                "batch_no": history.batch_no,
                "mo_id": history.mo_id,
                "finished_goods": history.finished_goods,
                "equipment_id": history.equipment_id_batch,
                "status_manufacturing": bool(history.status_manufacturing),
                "actual_weight": (
                    float(history.actual_weight_quantity_finished_goods)  # type: ignore
                    if history.actual_weight_quantity_finished_goods is not None  # type: ignore
                    else 0.0
                ),
                "last_read": (
                    history.last_read_from_plc.isoformat()  # type: ignore
                    if history.last_read_from_plc is not None  # type: ignore
                    else None
                ),
                "actual_consumptions": {
                    f"silo_{letter}": (
                        float(getattr(history, f"actual_consumption_silo_{letter}"))
                        if getattr(history, f"actual_consumption_silo_{letter}")
                        else 0.0
                    )
                    for letter in "abcdefghijklm"
                    if getattr(history, f"actual_consumption_silo_{letter}", 0) > 0
                },
            },
        }
    except Exception as exc:
        logger.exception(f"Error getting history for MO {mo_id}: %s", str(exc))
        raise


@router.post("/admin/manual/retry-push-odoo/{mo_id}")
async def retry_push_to_odoo(
    mo_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """
    Manual retry untuk push completed batch ke Odoo.
    Berguna jika sebelumnya gagal update ke Odoo.
    """
    try:
        # Find batch by mo_id
        stmt = select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
        result = db.execute(stmt)
        batch = result.scalar_one_or_none()
        
        if not batch:
            return {
                "status": "error",
                "message": f"Batch not found for MO ID: {mo_id}",
            }
        
        if not batch.status_manufacturing:  # type: ignore
            return {
                "status": "error",
                "message": f"Batch {mo_id} is not yet completed (status_manufacturing = 0)",
            }
        
        logger.info(f"Manual retry push to Odoo for MO {mo_id}")
        
        # Prepare batch data dengan naming konsisten
        # Field di DB: actual_consumption_silo_{letter}
        # Field di payload: consumption_silo_{letter} (contract process_batch_consumption)
        batch_data = {
            "status_manufacturing": 1,
            "actual_weight_quantity_finished_goods": (
                float(batch.actual_weight_quantity_finished_goods)  # type: ignore
                if batch.actual_weight_quantity_finished_goods is not None  # type: ignore
                else 0.0
            ),
        }
        
        # Map actual consumption -> consumption untuk Odoo API
        for letter in "abcdefghijklm":
            actual_field = f"actual_consumption_silo_{letter}"
            consumption_field = f"consumption_silo_{letter}"
            
            if hasattr(batch, actual_field):
                value = getattr(batch, actual_field)
                if value is not None and value > 0:
                    batch_data[consumption_field] = float(value)
        
        # Push to Odoo
        consumption_service = get_consumption_service(db)
        equipment_id = str(batch.equipment_id_batch or "PLC01")
        result = await consumption_service.process_batch_consumption(
            mo_id=mo_id,
            equipment_id=equipment_id,
            batch_data=batch_data
        )
        
        if result.get("success"):
            # Move to history and delete from batch
            history_service = get_mo_history_service(db)
            history = history_service.move_to_history(batch, status="completed")
            
            if history:
                if history_service.delete_from_batch(batch):
                    return {
                        "status": "success",
                        "message": f"Successfully pushed MO {mo_id} to Odoo and archived",
                        "data": result,
                    }
            
            return {
                "status": "partial_success",
                "message": f"Pushed to Odoo but failed to archive MO {mo_id}",
                "data": result,
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to push MO {mo_id} to Odoo",
                "error": result.get("error"),
            }
    
    except Exception as exc:
        logger.exception(f"Error retrying push for MO {mo_id}: %s", str(exc))
        raise


@router.post("/admin/manual/reset-batch/{mo_id}")
async def reset_batch_status(
    mo_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """
    Manual reset batch status manufacturing ke 0.
    Berguna jika batch perlu diproses ulang di PLC.
    """
    try:
        # Find batch by mo_id
        stmt = select(TableSmoBatch).where(TableSmoBatch.mo_id == mo_id)
        result = db.execute(stmt)
        batch = result.scalar_one_or_none()
        
        if not batch:
            return {
                "status": "error",
                "message": f"Batch not found for MO ID: {mo_id}",
            }
        
        logger.info(f"Manual reset status for MO {mo_id}")
        
        # Reset status
        batch.status_manufacturing = False  # type: ignore
        batch.status_operation = False  # type: ignore
        
        # Optionally reset actual values
        # batch.actual_weight_quantity_finished_goods = None
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Successfully reset status for MO {mo_id}",
            "data": {
                "mo_id": mo_id,
                "status_manufacturing": False,
                "status_operation": False,
            },
        }
    
    except Exception as exc:
        logger.exception(f"Error resetting batch {mo_id}: %s", str(exc))
        db.rollback()
        raise


@router.post("/admin/manual/cancel-batch/{batch_no}")
async def cancel_batch_manually(
    batch_no: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Any:
    """
    Cancel a batch dan pindahkan ke history dengan status 'cancelled'.
    
    Digunakan untuk batch yang gagal atau tidak jadi diproses dan tidak perlu diulang.
    Batch akan dihapus dari mo_batch dan disimpan ke mo_histories dengan status cancelled.
    
    Args:
        batch_no: Nomor batch yang akan di-cancel
        notes: Alasan cancellation (optional)
    
    Returns:
        Status dan info batch yang di-cancel
    """
    try:
        history_service = get_mo_history_service(db)
        result = history_service.cancel_batch(batch_no, notes)
        
        if result["success"]:
            logger.info(f"Batch {batch_no} cancelled successfully via API")
            return result
        else:
            logger.warning(f"Failed to cancel batch {batch_no}: {result['message']}")
            raise HTTPException(status_code=404, detail=result["message"])
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error cancelling batch {batch_no}: %s", str(exc))
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error cancelling batch: {str(exc)}"
        )


@router.post("/admin/manual/trigger-plc-sync")
async def trigger_plc_sync_manually() -> Any:
    """
    Manually trigger PLC read sync task.
    Berguna untuk testing atau force sync.
    """
    try:
        logger.info("Manual PLC sync triggered via API")
        await plc_read_sync_task()
        
        return {
            "status": "success",
            "message": "Manual PLC sync completed successfully",
        }
    except Exception as exc:
        logger.exception("Error in manual PLC sync: %s", str(exc))
        return {
            "status": "error",
            "message": f"Manual PLC sync failed: {str(exc)}",
        }


@router.post("/admin/manual/trigger-process-completed")
async def trigger_process_completed_manually() -> Any:
    """
    Manually trigger process completed batches task.
    Berguna untuk force processing completed batches.
    """
    try:
        logger.info("Manual process completed triggered via API")
        await process_completed_batches_task()
        
        return {
            "status": "success",
            "message": "Manual process completed task finished",
        }
    except Exception as exc:
        logger.exception("Error in manual process completed: %s", str(exc))
        return {
            "status": "error",
            "message": f"Manual process completed failed: {str(exc)}",
        }


@router.get("/admin/failed-to-push")
async def get_failed_to_push_batches(db: Session = Depends(get_db)) -> Any:
    """
    Get list batch yang sudah completed tapi belum berhasil push ke Odoo.
    Batch-batch ini masih ada di mo_batch table dengan status_manufacturing = 1.
    """
    try:
        # Get completed batches yang masih di mo_batch table
        stmt = select(TableSmoBatch).where(
            TableSmoBatch.status_manufacturing.is_(True)
        ).order_by(TableSmoBatch.batch_no)
        
        result = db.execute(stmt)
        batches = result.scalars().all()
        
        batch_list = [
            {
                "batch_no": batch.batch_no,
                "mo_id": batch.mo_id,
                "equipment_id": batch.equipment_id_batch,
                "finished_goods": batch.finished_goods,
                "actual_weight": (
                    float(batch.actual_weight_quantity_finished_goods)  # type: ignore
                    if batch.actual_weight_quantity_finished_goods is not None  # type: ignore
                    else 0.0
                ),
                "last_read": (
                    batch.last_read_from_plc.isoformat()  # type: ignore
                    if batch.last_read_from_plc is not None  # type: ignore
                    else None
                ),
            }
            for batch in batches
        ]
        
        return {
            "status": "success",
            "data": {
                "total": len(batch_list),
                "message": "These batches are completed but not yet pushed to Odoo",
                "batches": batch_list,
            },
        }
    except Exception as exc:
        logger.exception("Error getting failed to push batches: %s", str(exc))
        raise