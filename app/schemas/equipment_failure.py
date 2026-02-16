"""
Schemas untuk Equipment Failure Report
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class FailureReportRequest(BaseModel):
    """Request model untuk create failure report."""
    
    equipment_code: str = Field(
        ...,
        description="Equipment code (dari scada.equipment)",
        example="PLC01"
    )
    description: str = Field(
        ...,
        description="Deskripsi failure",
        example="Motor overload saat proses mixing"
    )
    date: Optional[str] = Field(
        None,
        description="Timestamp format YYYY-MM-DD HH:MM:SS atau YYYY-MM-DDTHH:MM, default = server time",
        example="2026-02-15 08:30:00"
    )


class FailureReportResponse(BaseModel):
    """Response model untuk failure report."""
    
    id: int = Field(..., description="Failure report ID")
    equipment_id: int = Field(..., description="Equipment ID")
    equipment_code: str = Field(..., description="Equipment code")
    equipment_name: str = Field(..., description="Equipment name")
    description: str = Field(..., description="Failure description")
    date: str = Field(..., description="Failure timestamp dalam format ISO 8601")
    
    class Config:
        from_attributes = True


class FailureReportListResponse(BaseModel):
    """Response model untuk list failure reports."""
    
    id: int
    equipment_code: str
    equipment_name: Optional[str]
    description: str
    date: datetime
    created_at: Optional[datetime]
