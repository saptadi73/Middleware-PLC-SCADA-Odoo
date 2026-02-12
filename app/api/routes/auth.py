import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.services.odoo_auth_service import authenticate_odoo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/scada/authenticate")
async def authenticate():
    """
    Authenticate user to Odoo and return session info.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await authenticate_odoo(client)
            return {
                "status": "success",
                "message": "Authenticated successfully",
                "data": result,
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Auth error: %s", str(exc))
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc
