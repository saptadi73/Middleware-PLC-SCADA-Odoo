from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SystemLogBase(BaseModel):
    level: str
    module: str
    message: str
    batch_no: Optional[str] = None
    mo_id: Optional[str] = None

class SystemLogResponse(SystemLogBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True