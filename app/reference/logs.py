from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.system_log import SystemLog
from app.schemas.system_log import SystemLogResponse
from sqlalchemy import desc

router = APIRouter()

@router.get("/", response_model=List[SystemLogResponse])
def get_system_logs(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    level: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None
):
    """
    Get system logs for frontend monitoring.
    """
    query = db.query(SystemLog)

    if level:
        query = query.filter(SystemLog.level == level)
    
    if module:
        query = query.filter(SystemLog.module.contains(module))
        
    if search:
        query = query.filter(SystemLog.message.contains(search))

    # Always show newest first
    logs = query.order_by(desc(SystemLog.timestamp)).offset(skip).limit(limit).all()
    return logs

@router.delete("/clear")
def clear_logs(db: Session = Depends(get_db)):
    """
    Clear old logs (Manual cleanup)
    """
    # Keep last 1000 logs, delete rest (example logic)
    # Or just delete all:
    db.query(SystemLog).delete()
    db.commit()
    return {"message": "Logs cleared"}