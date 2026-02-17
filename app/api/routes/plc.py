"""
PLC API routes untuk read/write data ke PLC
"""
import logging
from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_write_service import get_plc_write_service
from app.services.plc_read_service import get_plc_read_service
from app.services.plc_sync_service import get_plc_sync_service

logger = logging.getLogger(__name__)
router = APIRouter()


class PLCWriteFieldRequest(BaseModel):
    """Request model untuk write single field ke PLC."""
    batch_name: str = Field(..., description="Batch name (BATCH01-BATCH30)")
    field_name: str = Field(..., description="Field name dari MASTER_BATCH_REFERENCE.json")
    value: Any = Field(..., description="Value to write")


class PLCWriteBatchRequest(BaseModel):
    """Request model untuk write multiple fields ke PLC."""
    batch_name: str = Field(..., description="Batch name (BATCH01-BATCH30)")
    data: Dict[str, Any] = Field(..., description="Dictionary of field_name: value")


class PLCWriteMORequest(BaseModel):
    """Request model untuk write MO batch dari database ke PLC."""
    batch_no: int = Field(..., ge=1, description="Batch number dari mo_batch table")
    plc_batch_slot: int = Field(default=1, ge=1, le=30, description="PLC batch slot (BATCH01-BATCH30)")


@router.post("/plc/write-field")
async def write_field_to_plc(request: PLCWriteFieldRequest) -> Any:
    """
    Write single field ke PLC memory.
    
    Example:
    ```json
    {
      "batch_name": "BATCH01",
      "field_name": "NO-MO",
      "value": "WH/MO/00002"
    }
    ```
    """
    try:
        service = get_plc_write_service()
        service.write_field(
            batch_name=request.batch_name,
            field_name=request.field_name,
            value=request.value,
        )
        
        return {
            "status": "success",
            "message": f"Written {request.field_name} to {request.batch_name}",
            "data": {
                "batch_name": request.batch_name,
                "field_name": request.field_name,
                "value": request.value,
            },
        }
    except Exception as exc:
        logger.exception("Error writing field to PLC: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write to PLC: {str(exc)}",
        ) from exc


@router.post("/plc/write-batch")
async def write_batch_to_plc(request: PLCWriteBatchRequest) -> Any:
    """
    Write multiple fields ke PLC untuk satu batch.
    
    Example:
    ```json
    {
      "batch_name": "BATCH01",
      "data": {
        "BATCH": 1,
        "NO-MO": "WH/MO/00002",
        "NO-BoM": "JF PLUS 25",
        "SILO ID 101 (SILO BESAR)": 101,
        "SILO 1 Consumption": 825.0
      }
    }
    ```
    """
    try:
        service = get_plc_write_service()
        service.write_batch(
            batch_name=request.batch_name,
            data=request.data,
        )
        
        return {
            "status": "success",
            "message": f"Written batch data to {request.batch_name}",
            "data": {
                "batch_name": request.batch_name,
                "field_count": len(request.data),
            },
        }
    except Exception as exc:
        logger.exception("Error writing batch to PLC: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write to PLC: {str(exc)}",
        ) from exc


@router.post("/plc/write-mo-batch")
async def write_mo_batch_to_plc(
    request: PLCWriteMORequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Write MO batch dari database ke PLC.
    
    Process:
    1. Read batch data dari mo_batch table berdasarkan batch_no
    2. Convert data ke format PLC
    3. Write ke PLC memory slot (BATCH01-BATCH30)
    
    Example:
    ```json
    {
      "batch_no": 1,
      "plc_batch_slot": 1
    }
    ```
    """
    try:
        # Get batch from database
        batch = (
            db.query(TableSmoBatch)
            .filter(TableSmoBatch.batch_no == request.batch_no)
            .first()
        )
        
        if not batch:
            raise HTTPException(
                status_code=404,
                detail=f"Batch {request.batch_no} not found in database",
            )
        
        # Convert to dict
        # Extract values to avoid Column type inference issues
        consumption_val = batch.consumption  # type: ignore
        actual_weight_val = batch.actual_weight_quantity_finished_goods  # type: ignore
        
        batch_data = {
            "mo_id": batch.mo_id,
            "consumption": float(consumption_val) if consumption_val is not None else 0.0,  # type: ignore
            "equipment_id_batch": batch.equipment_id_batch,
            "finished_goods": batch.finished_goods,
            "status_manufacturing": batch.status_manufacturing or False,
            "status_operation": batch.status_operation or False,
            "actual_weight_quantity_finished_goods": (
                float(actual_weight_val)  # type: ignore
                if actual_weight_val is not None
                else 0.0
            ),
        }
        
        # Add silo data
        for letter in "abcdefghijklm":
            batch_data[f"silo_{letter}"] = getattr(batch, f"silo_{letter}", None)
            batch_data[f"component_silo_{letter}_name"] = getattr(
                batch, f"component_silo_{letter}_name", None
            )
            batch_data[f"consumption_silo_{letter}"] = getattr(
                batch, f"consumption_silo_{letter}", None
            )
        
        # Write to PLC
        service = get_plc_write_service()
        service.write_mo_batch_to_plc(batch_data, request.plc_batch_slot)
        
        return {
            "status": "success",
            "message": f"MO batch written to PLC slot BATCH{request.plc_batch_slot:02d}",
            "data": {
                "batch_no": request.batch_no,
                "mo_id": batch.mo_id,
                "plc_batch_slot": request.plc_batch_slot,
                "plc_batch_name": f"BATCH{request.plc_batch_slot:02d}",
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error writing MO batch to PLC: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write MO batch to PLC: {str(exc)}",
        ) from exc


@router.get("/plc/config")
async def get_plc_config() -> Any:
    """Get current PLC configuration."""
    service = get_plc_write_service()
    
    return {
        "status": "success",
        "data": {
            "plc_ip": service.settings.plc_ip,
            "plc_port": service.settings.plc_port,
            "plc_protocol": service.settings.plc_protocol,
            "plc_timeout_sec": service.settings.plc_timeout_sec,
            "client_node": service.settings.client_node,
            "plc_node": service.settings.plc_node,
            "batches_loaded": len(service.mapping),
        },
    }


@router.get("/plc/read-field/{field_name}")
async def read_field_from_plc(field_name: str) -> Any:
    """
    Read single field dari PLC memory.
    
    Example:
    GET /api/plc/read-field/NO-MO
    """
    try:
        service = get_plc_read_service()
        value = service.read_field(field_name)
        
        return {
            "status": "success",
            "message": f"Read {field_name} from PLC",
            "data": {
                "field_name": field_name,
                "value": value,
            },
        }
    except Exception as exc:
        logger.exception("Error reading field from PLC: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read from PLC: {str(exc)}",
        ) from exc


@router.get("/plc/read-all")
async def read_all_fields_from_plc() -> Any:
    """
    Read semua fields dari PLC memory.
    
    Returns all fields dari READ_DATA_PLC_MAPPING.json
    """
    try:
        service = get_plc_read_service()
        data = service.read_all_fields()
        
        return {
            "status": "success",
            "message": f"Read {len(data)} fields from PLC",
            "data": data,
        }
    except Exception as exc:
        logger.exception("Error reading all fields from PLC: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read from PLC: {str(exc)}",
        ) from exc


@router.get("/plc/read-batch")
async def read_batch_from_plc() -> Any:
    """
    Read batch data dari PLC dan format sebagai structured data.
    
    Returns formatted batch data dengan silos, status, etc.
    """
    try:
        service = get_plc_read_service()
        batch_data = service.read_batch_data()
        
        return {
            "status": "success",
            "message": "Read batch data from PLC",
            "data": batch_data,
        }
    except Exception as exc:
        logger.exception("Error reading batch data from PLC: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read batch from PLC: {str(exc)}",
        ) from exc


@router.post("/plc/sync-from-plc")
async def sync_data_from_plc() -> Any:
    """
    Read data dari PLC dan update mo_batch table berdasarkan MO_ID.
    
    Process:
    1. Read all fields dari PLC
    2. Extract MO_ID dari PLC data
    3. Find corresponding mo_batch record
    4. Update actual consumption fields jika ada perubahan
    5. Update status dan weight fields
    6. Update last_read_from_plc timestamp
    
    Returns sync result dengan informasi update status.
    """
    try:
        service = get_plc_sync_service()
        result = await service.sync_from_plc()
        
        if result["success"]:
            return {
                "status": "success",
                "message": result.get("message", "Sync completed"),
                "data": {
                    "mo_id": result.get("mo_id"),
                    "updated": result.get("updated", False),
                },
            }
        else:
            raise HTTPException(
                status_code=404 if "not found" in result.get("error", "").lower() else 500,
                detail=result.get("error", "Sync failed"),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error syncing data from PLC: %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync from PLC: {str(exc)}",
        ) from exc

