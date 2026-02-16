import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.mo_batch_service import sync_mo_list_to_db
from app.services.odoo_auth_service import fetch_mo_list_detailed
from app.services.odoo_consumption_service import (
    get_consumption_service,
)
from app.services.equipment_failure_service import get_equipment_failure_service
from app.schemas.equipment_failure import (
    FailureReportRequest,
    FailureReportResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ConsumptionUpdateRequest(BaseModel):
    """Request model untuk update consumption ke Odoo."""

    mo_id: str = Field(..., description="Manufacturing Order ID")
    equipment_id: str = Field(..., description="Equipment code")
    consumption_data: Dict[str, float] = Field(
        ...,
        description="Consumption data {silo_tag: quantity}",
    )
    timestamp: Optional[str] = Field(
        None,
        description="ISO format timestamp, default = now",
    )


class MarkMODoneRequest(BaseModel):
    """Request model untuk mark MO sebagai done."""

    mo_id: str = Field(..., description="Manufacturing Order ID")
    finished_qty: float = Field(
        ...,
        gt=0,
        description="Finished quantity (must be > 0)",
    )
    equipment_id: Optional[str] = Field(
        None,
        description="Equipment code",
    )
    auto_consume: bool = Field(
        False,
        description="Auto-apply remaining consumption",
    )
    message: Optional[str] = Field(
        None,
        description="Optional message",
    )


class BatchConsumptionRequest(BaseModel):
    """Request model untuk process batch consumption."""

    mo_id: str = Field(..., description="Manufacturing Order ID")
    equipment_id: str = Field(..., description="Equipment code")
    batch_data: Dict[str, Any] = Field(
        ...,
        description="Batch data dengan consumption dan status",
    )


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/scada/mo-list-detailed")
async def mo_list_detailed(
    limit: int = Query(10, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Any:
    """
    Fetch detailed MO list from Odoo and sync to local database.
    Handles session persistence internally.
    """
    try:
        # Fetch MO list with session persistence
        payload = await fetch_mo_list_detailed(limit=limit, offset=offset)

        # Sync to database
        result = payload.get("result", {})
        mo_list = result.get("data", [])
        count = result.get("count", 0)
        
        sync_mo_list_to_db(db, mo_list)

        return {
            "status": "success",
            "message": "MO list fetched and synced successfully",
            "data": {
                "count": count,
                "total_fetched": len(mo_list),
                "limit": limit,
                "offset": offset,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error fetching MO list from Odoo: %s", str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch MO list: {str(exc)}",
        ) from exc

@router.post("/consumption/update")
async def update_consumption(
    request: ConsumptionUpdateRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    UPDATE MANUAL PER-COMPONENT using /material-consumption endpoint.

    ⚠️ IMPORTANT: This endpoint is for MANUAL updates per material component only.
    It calls Odoo's /api/scada/material-consumption endpoint with product_id parameter
    for each material separately.

    For automated batch processing of all components at once, use /consumption/batch-process
    which uses the more efficient /api/scada/mo/update-with-consumptions endpoint.

    Use this endpoint for:
    - Manual correction of specific material consumption
    - Updating a single component after verification
    - Per-component adjustments

    ✓ Database: Automatically saved after successful Odoo update

    Example request:
    ```json
    {
      "mo_id": "MO/2025/001",
      "equipment_id": "PLC01",
      "consumption_data": {
        "silo_a": 50.5,
        "silo_b": 25.3
      },
      "timestamp": "2025-02-13T10:30:00"
    }
    ```

    Returns:
        Success response dengan details update consumption per component
    """
    try:
        service = get_consumption_service(db=db)
        result = await service.update_consumption(
            mo_id=request.mo_id,
            equipment_id=request.equipment_id,
            consumption_data=request.consumption_data,
            timestamp=request.timestamp,
        )

        if result.get("success"):
            return {
                "status": "success",
                "message": "Consumption updated successfully",
                "data": result,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Unknown error"),
            )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Error updating consumption: %s",
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update consumption: {str(exc)}",
        ) from exc


@router.post("/consumption/mark-done")
async def mark_mo_done(
    request: MarkMODoneRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Mark Manufacturing Order sebagai done di Odoo.

    Endpoint ini digunakan setelah status_manufacturing = 1 (manufacturing selesai)
    untuk mark MO sebagai done dengan finished quantity.

    ✓ Database: Automatically saved after successful Odoo update
    ✓ Fields updated: status_manufacturing, actual_weight_quantity_finished_goods, last_read_from_plc

    Example request:
    ```json
    {
      "mo_id": "MO/2025/001",
      "finished_qty": 1000.0,
      "equipment_id": "PLC01",
      "auto_consume": true
    }
    ```

    Returns:
        Success response dengan confirmation mark done
    """
    try:
        service = get_consumption_service(db=db)
        result = await service.mark_mo_done(
            mo_id=request.mo_id,
            finished_qty=request.finished_qty,
            equipment_id=request.equipment_id,
            auto_consume=request.auto_consume,
            message=request.message,
        )

        if result.get("success"):
            return {
                "status": "success",
                "message": "Manufacturing order marked as done",
                "data": result,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Unknown error"),
            )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Error marking MO as done: %s",
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark MO as done: {str(exc)}",
        ) from exc


@router.post("/consumption/batch-process")
async def process_batch_consumption(
    request: BatchConsumptionRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    AUTOMATED BATCH PROCESSING using /update-with-consumptions endpoint.

    ⚠️ IMPORTANT: This is the RECOMMENDED endpoint for automated batch processing.
    It calls Odoo's /api/scada/mo/update-with-consumptions endpoint in a SINGLE call
    with all consumption data at once.

    This is more efficient than /consumption/update which makes separate calls
    per component via /material-consumption endpoint.

    Use this endpoint for:
    - Automated PLC read workflow (all components at once)
    - Batch processing with auto mark-done
    - Production/manufacturing updates

    ✓ Database: Automatically saved after successful Odoo update
    ✓ Automatic mark-done: If status_manufacturing = 1, MO marked done with finished_qty

    Example request:
    ```json
    {
      "mo_id": "MO/2025/001",
      "equipment_id": "PLC01",
      "batch_data": {
        "consumption_silo_a": 50.5,
        "consumption_silo_b": 25.3,
        "consumption_silo_c": 0,
        "status_manufacturing": 1,
        "actual_weight_quantity_finished_goods": 1000
      }
    }
    ```

    Returns:
        Comprehensive response dengan consumption dan mark-done status
    """
    try:
        service = get_consumption_service(db=db)
        result = await service.process_batch_consumption(
            mo_id=request.mo_id,
            equipment_id=request.equipment_id,
            batch_data=request.batch_data,
        )

        if result.get("success"):
            return {
                "status": "success",
                "message": "Batch consumption processed successfully",
                "data": result,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Unknown error"),
            )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Error processing batch consumption: %s",
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process batch consumption: {str(exc)}",
        ) from exc


@router.post("/api/scada/equipment-failure")
async def create_equipment_failure(
    request: FailureReportRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Create equipment failure report.
    
    Available only when module `grt_scada_failure_report` is installed in Odoo.
    
    Request body:
    ```json
    {
        "equipment_code": "PLC01",
        "description": "Motor overload saat proses mixing",
        "date": "2026-02-15 08:30:00"
    }
    ```
    
    Response (Success):
    ```json
    {
        "status": "success",
        "message": "Equipment failure report created",
        "data": {
            "id": 1,
            "equipment_id": 1,
            "equipment_code": "PLC01",
            "equipment_name": "Main PLC - Injection Machine 01",
            "description": "Motor overload saat proses mixing",
            "date": "2026-02-15T08:30:00"
        }
    }
    ```
    
    Response (Error):
    ```json
    {
        "status": "error",
        "message": "Equipment with code \"PLC01\" not found"
    }
    ```
    """
    try:
        service = get_equipment_failure_service(db=db)
        
        result = await service.create_failure_report(
            equipment_code=request.equipment_code,
            description=request.description,
            date=request.date,
        )
        
        if result.get("success"):
            return {
                "status": "success",
                "message": result.get("message", "Equipment failure report created"),
                "data": result.get("data"),
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Failed to create failure report"),
            )
    
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Error creating failure report: %s",
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create failure report: {str(exc)}",
        ) from exc