from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SystemLogResponse(BaseModel):
    id: UUID
    timestamp: datetime
    level: str
    module: str
    message: str
    batch_no: Optional[str] = None
    mo_id: Optional[str] = None

    class Config:
        from_attributes = True


class SystemLogListMeta(BaseModel):
    total: int
    skip: int
    limit: int
    has_next: bool


class SystemLogListResponse(BaseModel):
    items: list[SystemLogResponse]
    meta: SystemLogListMeta
