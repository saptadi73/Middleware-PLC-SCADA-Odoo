from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.system_log import SystemLog
from app.schemas.system_log import (
    SystemLogListMeta,
    SystemLogListResponse,
    SystemLogResponse,
)

router = APIRouter()


@router.get("/", response_model=SystemLogListResponse)
def get_system_logs(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    level: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
):
    query = db.query(SystemLog)

    if level:
        query = query.filter(SystemLog.level == level.upper())
    if module:
        query = query.filter(SystemLog.module.ilike(f"%{module}%"))
    if search:
        query = query.filter(SystemLog.message.ilike(f"%{search}%"))
    if start_time:
        query = query.filter(SystemLog.timestamp >= start_time)
    if end_time:
        query = query.filter(SystemLog.timestamp <= end_time)

    total = query.count()
    items = query.order_by(desc(SystemLog.timestamp)).offset(skip).limit(limit).all()

    return SystemLogListResponse(
        items=[SystemLogResponse.model_validate(item) for item in items],
        meta=SystemLogListMeta(
            total=total,
            skip=skip,
            limit=limit,
            has_next=(skip + len(items)) < total,
        ),
    )


@router.delete("/clear")
def clear_logs(
    db: Session = Depends(get_db),
    keep_last: int = Query(default=1000, ge=0),
    older_than_days: Optional[int] = Query(default=None, ge=1),
):
    if older_than_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
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
        return {
            "message": (
                f"Logs older than {older_than_days} day(s) cleaned "
                f"(cutoff={cutoff.isoformat()})."
            ),
            "deleted_count": deleted,
            "kept_count": keep_last if keep_last > 0 else 0,
            "older_than_days": older_than_days,
        }

    if keep_last <= 0:
        deleted = db.query(SystemLog).delete(synchronize_session=False)
        db.commit()
        return {
            "message": "All logs cleared",
            "deleted_count": deleted,
            "kept_count": 0,
        }

    keep_subquery = (
        select(SystemLog.id)
        .order_by(desc(SystemLog.timestamp))
        .limit(keep_last)
    )
    deleted = (
        db.query(SystemLog)
        .filter(~SystemLog.id.in_(keep_subquery))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {
        "message": f"Logs cleaned. Kept latest {keep_last} rows.",
        "deleted_count": deleted,
        "kept_count": keep_last,
    }
