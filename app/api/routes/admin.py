"""
Admin routes untuk manage scheduler, mo_batch table, dan monitoring
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, text, select
from sqlalchemy.orm import Session

from app.core.scheduler import (
    auto_sync_mo_task,
    get_scheduler_status,
    plc_read_sync_task,
    process_completed_batches_task,
    set_scheduler_enabled,
)
from app.db.session import get_db
from app.models.system_log import SystemLog
from app.models.tablesmo_batch import TableSmoBatch
from app.services.mo_history_service import get_mo_history_service
from app.services.odoo_consumption_service import get_consumption_service
from app.services.plc_handshake_service import get_handshake_service
from app.services.plc_write_service import get_plc_write_service
from app.services.table_view_service import get_table_view_service
from app.services.task1_reset_service import get_task1_reset_service

logger = logging.getLogger(__name__)
router = APIRouter()


class SchedulerToggleRequest(BaseModel):
    enabled: bool

TASK_MONITOR_CONFIG: dict[str, dict[str, str]] = {
    "task1": {
        "label": "TASK 1",
        "prefix": "[TASK 1]",
        "description": "Auto-sync MO dari Odoo ke mo_batch dan PLC WRITE area",
    },
    "task2": {
        "label": "TASK 2",
        "prefix": "[TASK 2]",
        "description": "PLC read sync ke mo_batch",
    },
    "task3": {
        "label": "TASK 3",
        "prefix": "[TASK 3]",
        "description": "Process completed batches ke Odoo dan history",
    },
    "task4": {
        "label": "TASK 4",
        "prefix": "[TASK 4]",
        "description": "Health monitoring scheduler",
    },
}


def _resolve_task_monitor(task_name: str) -> dict[str, str]:
    task_config = TASK_MONITOR_CONFIG.get(task_name.lower())
    if task_config is None:
        allowed_tasks = ", ".join(TASK_MONITOR_CONFIG.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown task monitor '{task_name}'. Use one of: {allowed_tasks}",
        )
    return task_config


def _build_task_log_query(
    db: Session,
    task_prefix: str,
    since_minutes: Optional[int],
    level: Optional[str] = None,
):
    query = db.query(SystemLog).filter(SystemLog.message.ilike(f"%{task_prefix}%"))

    if since_minutes is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        query = query.filter(SystemLog.timestamp >= cutoff)

    if level:
        query = query.filter(SystemLog.level == level.upper())

    return query


def _derive_task_health(latest_log: Optional[SystemLog]) -> str:
    if latest_log is None:
        return "no-data"

    level = (latest_log.level or "").upper()
    message = (latest_log.message or "").lower()

    if level in {"ERROR", "CRITICAL"}:
        return "error"
    if level == "WARNING":
        return "warning"
    if "skip" in message or "wait" in message:
        return "waiting"
    if "start" in message or "run" in message or "trigger" in message:
        return "running"
    if any(keyword in message for keyword in ["complete", "success", "done", "finish"]):
        return "success"
    return "healthy"


def _serialize_system_log(log: SystemLog) -> dict[str, Any]:
    return {
        "id": str(log.id),
        "timestamp": log.timestamp.isoformat() if log.timestamp is not None else None,
        "level": log.level,
        "module": log.module,
        "message": log.message,
        "batch_no": log.batch_no,
        "mo_id": log.mo_id,
    }


def _build_task_monitor_summary(
    db: Session,
    task_name: str,
    since_minutes: Optional[int],
) -> dict[str, Any]:
    task_config = _resolve_task_monitor(task_name)
    base_query = _build_task_log_query(db, task_config["prefix"], since_minutes)

    total_logs = base_query.count()
    latest_log = base_query.order_by(desc(SystemLog.timestamp)).first()
    error_count = base_query.filter(SystemLog.level.in_(["ERROR", "CRITICAL"])).count()
    warning_count = base_query.filter(SystemLog.level == "WARNING").count()
    info_count = base_query.filter(SystemLog.level == "INFO").count()

    return {
        "task": task_name,
        "label": task_config["label"],
        "description": task_config["description"],
        "status": _derive_task_health(latest_log),
        "latest_level": latest_log.level if latest_log is not None else None,
        "last_run_at": latest_log.timestamp.isoformat() if latest_log is not None else None,
        "latest_message": latest_log.message if latest_log is not None else None,
        "log_counts": {
            "total": total_logs,
            "info": info_count,
            "warning": warning_count,
            "error": error_count,
        },
    }


@router.post("/admin/reset-task1-start")
async def reset_task1_start(db: Session = Depends(get_db)) -> Any:
    """
    Prepare TASK 1 to run from the beginning.

    Actions:
    1. Set all WRITE-area status_read_data flags to 1
    2. Clear all records from mo_batch
    """
    try:
        service = get_task1_reset_service(db)
        result = service.reset_for_fresh_start()

        logger.info(
            "TASK 1 reset start completed: ready=%s deleted=%s",
            result["write_ready_count"],
            result["deleted_mo_batch_count"],
        )

        return {
            "status": "success",
            "message": "TASK 1 initial state prepared successfully",
            "data": result,
        }
    except Exception as exc:
        logger.exception("Error preparing TASK 1 initial state: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to prepare TASK 1 initial state: {str(exc)}",
        ) from exc


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


@router.get("/admin/scheduler/status")
async def get_scheduler_runtime_status() -> Any:
    """
    Status runtime scheduler untuk frontend switch/indicator.
    """
    try:
        return {
            "status": "success",
            "data": get_scheduler_status(),
        }
    except Exception as exc:
        logger.exception("Error getting scheduler runtime status: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduler status: {str(exc)}",
        ) from exc


@router.post("/admin/scheduler/toggle")
async def toggle_scheduler_runtime(payload: SchedulerToggleRequest) -> Any:
    """
    Start/stop scheduler secara runtime agar bisa dikontrol dari frontend.
    """
    try:
        result = set_scheduler_enabled(payload.enabled)
        logger.info(
            "Scheduler runtime toggle requested: enabled=%s action=%s",
            payload.enabled,
            result.get("action"),
        )

        return {
            "status": "success",
            "message": (
                "Scheduler started successfully"
                if payload.enabled
                else "Scheduler stopped successfully"
            ),
            "data": result,
        }
    except Exception as exc:
        logger.exception("Error toggling scheduler runtime: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to toggle scheduler: {str(exc)}",
        ) from exc


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


@router.get("/admin/table/mo-batch")
async def get_mo_batch_table(db: Session = Depends(get_db)) -> Any:
    """
    Get data tabel mo_batch (queue aktif) untuk frontend table view.
    """
    try:
        table_service = get_table_view_service(db)
        data = table_service.get_mo_batch_table()

        return {
            "status": "success",
            "data": data,
        }
    except Exception as exc:
        logger.exception("Error getting mo_batch table: %s", str(exc))
        raise


@router.get("/admin/table/mo-histories")
async def get_mo_histories_table(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    mo_id: Optional[str] = Query(default=None),
) -> Any:
    """
    Get data tabel mo_histories dengan pagination.
    """
    try:
        table_service = get_table_view_service(db)
        data = table_service.get_mo_histories_table(
            limit=limit,
            offset=offset,
            status=status,
            mo_id=mo_id,
        )

        return {
            "status": "success",
            "data": data,
        }
    except Exception as exc:
        logger.exception("Error getting mo_histories table: %s", str(exc))
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


@router.get("/admin/task-monitor/summary")
async def get_task_monitor_summary(
    db: Session = Depends(get_db),
    since_minutes: Optional[int] = Query(default=180, ge=1, le=10080),
) -> Any:
    """
    Ringkasan status monitoring per TASK berdasarkan system_log.
    Cocok untuk kartu monitoring frontend.
    """
    try:
        tasks = [
            _build_task_monitor_summary(db, task_name, since_minutes)
            for task_name in TASK_MONITOR_CONFIG
        ]

        return {
            "status": "success",
            "data": {
                "since_minutes": since_minutes,
                "tasks": tasks,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error getting task monitor summary: %s", str(exc))
        raise


@router.get("/admin/task-monitor/errors")
async def get_task_monitor_errors(
    db: Session = Depends(get_db),
    since_minutes: Optional[int] = Query(default=180, ge=1, le=10080),
    limit_per_task: int = Query(default=5, ge=1, le=50),
    include_warning: bool = Query(default=True),
) -> Any:
    """
    Agregasi alert TASK scheduler (ERROR/CRITICAL dan optional WARNING).
    Cocok untuk panel alert frontend.
    """
    try:
        levels = ["ERROR", "CRITICAL"]
        if include_warning:
            levels.append("WARNING")

        alerts_by_task: dict[str, list[dict[str, Any]]] = {}
        total_alerts = 0

        for task_name, task_config in TASK_MONITOR_CONFIG.items():
            alert_query = _build_task_log_query(
                db=db,
                task_prefix=task_config["prefix"],
                since_minutes=since_minutes,
            ).filter(SystemLog.level.in_(levels))

            task_alerts = (
                alert_query.order_by(desc(SystemLog.timestamp))
                .limit(limit_per_task)
                .all()
            )

            serialized = [_serialize_system_log(item) for item in task_alerts]
            alerts_by_task[task_name] = serialized
            total_alerts += len(serialized)

        return {
            "status": "success",
            "data": {
                "since_minutes": since_minutes,
                "levels": levels,
                "limit_per_task": limit_per_task,
                "total_alerts": total_alerts,
                "tasks": alerts_by_task,
            },
        }
    except Exception as exc:
        logger.exception("Error getting task monitor alerts: %s", str(exc))
        raise


@router.get("/admin/task-monitor/errors/flat")
async def get_task_monitor_errors_flat(
    db: Session = Depends(get_db),
    since_minutes: Optional[int] = Query(default=180, ge=1, le=10080),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    include_warning: bool = Query(default=True),
) -> Any:
    """
    Alert TASK scheduler dalam satu list gabungan terurut waktu terbaru.
    Cocok untuk global feed/notification panel frontend.
    """
    try:
        levels = ["ERROR", "CRITICAL"]
        if include_warning:
            levels.append("WARNING")

        all_alerts: list[dict[str, Any]] = []

        for task_name, task_config in TASK_MONITOR_CONFIG.items():
            alert_query = _build_task_log_query(
                db=db,
                task_prefix=task_config["prefix"],
                since_minutes=since_minutes,
            ).filter(SystemLog.level.in_(levels))

            for item in alert_query.all():
                serialized = _serialize_system_log(item)
                serialized["task"] = task_name
                serialized["task_label"] = task_config["label"]
                serialized["task_prefix"] = task_config["prefix"]
                all_alerts.append(serialized)

        all_alerts.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        paged_alerts = all_alerts[skip : skip + limit]

        return {
            "status": "success",
            "data": {
                "since_minutes": since_minutes,
                "levels": levels,
                "total_alerts": len(all_alerts),
                "skip": skip,
                "limit": limit,
                "items": paged_alerts,
                "has_next": (skip + len(paged_alerts)) < len(all_alerts),
            },
        }
    except Exception as exc:
        logger.exception("Error getting flat task monitor alerts: %s", str(exc))
        raise


@router.get("/admin/task-monitor/{task_name}")
async def get_task_monitor_detail(
    task_name: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    since_minutes: Optional[int] = Query(default=180, ge=1, le=10080),
    level: Optional[str] = Query(default=None),
) -> Any:
    """
    Detail monitoring untuk satu TASK scheduler, termasuk recent log lines.
    """
    try:
        task_config = _resolve_task_monitor(task_name)
        log_query = _build_task_log_query(db, task_config["prefix"], since_minutes, level)
        total = log_query.count()
        items = (
            log_query.order_by(desc(SystemLog.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {
            "status": "success",
            "data": {
                "summary": _build_task_monitor_summary(db, task_name, since_minutes),
                "filters": {
                    "task": task_name.lower(),
                    "label": task_config["label"],
                    "prefix": task_config["prefix"],
                    "since_minutes": since_minutes,
                    "level": level.upper() if level else None,
                    "skip": skip,
                    "limit": limit,
                },
                "logs": [_serialize_system_log(item) for item in items],
                "meta": {
                    "total": total,
                    "has_next": (skip + len(items)) < total,
                },
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error getting task monitor detail for %s: %s", task_name, str(exc))
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
            # Archive + delete atomically in one transaction
            history_service = get_mo_history_service(db)
            archived = history_service.archive_batch(
                batch,
                status="completed",
                mark_synced=True,
            )
            if archived:
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
    push_to_plc: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Any:
    """
    Manual reset batch status manufacturing ke 0.
    Berguna jika batch perlu diproses ulang di PLC.
    Set push_to_plc=true untuk paksa tulis ulang status reset ke PLC WRITE area.
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

        plc_sync_status = "skipped"
        plc_sync_error: Optional[str] = None
        if push_to_plc:
            try:
                plc_service = get_plc_write_service()
                handshake = get_handshake_service()

                batch_data: dict[str, Any] = {
                    "mo_id": batch.mo_id,
                    "consumption": float(batch.consumption) if batch.consumption is not None else 0.0,
                    "equipment_id_batch": batch.equipment_id_batch,
                    "finished_goods": batch.finished_goods,
                    "status_manufacturing": False,
                    "status_operation": False,
                    "actual_weight_quantity_finished_goods": (
                        float(batch.actual_weight_quantity_finished_goods)
                        if batch.actual_weight_quantity_finished_goods is not None
                        else 0.0
                    ),
                }

                for letter in "abcdefghijklm":
                    batch_data[f"silo_{letter}"] = getattr(batch, f"silo_{letter}", None)
                    batch_data[f"consumption_silo_{letter}"] = getattr(
                        batch, f"consumption_silo_{letter}", None
                    )

                plc_service.write_mo_batch_to_plc(
                    batch_data,
                    batch_number=batch.batch_no,
                    skip_handshake_check=True,
                )
                # Manual push should still mark WRITE area unread for PLC to consume.
                handshake.reset_write_area_status()
                plc_sync_status = "success"
            except Exception as plc_exc:
                plc_sync_status = "failed"
                plc_sync_error = str(plc_exc)
                logger.error(
                    "Manual reset DB success but PLC sync failed for MO %s: %s",
                    mo_id,
                    plc_exc,
                    exc_info=True,
                )

        return {
            "status": "success",
            "message": f"Successfully reset status for MO {mo_id}",
            "data": {
                "mo_id": mo_id,
                "status_manufacturing": False,
                "status_operation": False,
                "plc_sync": plc_sync_status,
                "plc_sync_error": plc_sync_error,
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
    Batch-batch ini masih ada di mo_batch table dengan:
    - status_manufacturing = 1
    - update_odoo = 0/false
    """
    try:
        # Get completed batches yang masih di mo_batch table
        stmt = (
            select(TableSmoBatch)
            .where(
                TableSmoBatch.status_manufacturing.is_(True),
                TableSmoBatch.update_odoo.is_(False),
            )
            .order_by(TableSmoBatch.batch_no)
        )
        
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
                "message": "These batches are completed and pending Odoo sync (update_odoo=false)",
                "batches": batch_list,
            },
        }
    except Exception as exc:
        logger.exception("Error getting failed to push batches: %s", str(exc))
        raise
