import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.mo_batch_service import sync_mo_list_to_db
from app.services.odoo_auth_service import fetch_mo_list_detailed

logger = logging.getLogger(__name__)
router = APIRouter()


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
