import logging
from typing import Any, Dict

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def authenticate_odoo(client: httpx.AsyncClient) -> Dict[str, Any]:
    """
    Authenticate ke Odoo dan return session info.
    Endpoint: POST /web/session/authenticate
    
    Args:
        client: Persistent httpx.AsyncClient untuk menyimpan cookies
    """
    settings = get_settings()

    base_url = settings.odoo_base_url.rstrip("/")
    auth_url = f"{base_url}/web/session/authenticate"

    auth_payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "db": settings.odoo_db,
            "login": settings.odoo_username,
            "password": settings.odoo_password,
        },
    }

    try:
        response = await client.post(auth_url, json=auth_payload)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            logger.error("Odoo auth error: %s", data.get("error"))
            raise RuntimeError(f"Odoo auth failed: {data.get('error')}")

        result = data.get("result") or {}
        logger.info("Odoo auth success for user: %s", result.get("login"))
        return result
    except httpx.ConnectError as exc:
        msg = f"Cannot connect to Odoo at {settings.odoo_base_url}: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc


async def fetch_mo_list_detailed(limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    """
    Fetch detailed MO list from Odoo SCADA API.
    Maintains session across authenticate + fetch requests.
    """
    settings = get_settings()

    base_url = settings.odoo_base_url.rstrip("/")
    mo_list_url = f"{base_url}/api/scada/mo-list-detailed"

    mo_list_payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "limit": limit,
            "offset": offset,
        },
    }

    # Use persistent client to maintain cookies across requests
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Authenticate and get session cookie
        await authenticate_odoo(client)

        # Step 2: Fetch MO list using same client (cookies preserved)
        try:
            response = await client.post(mo_list_url, json=mo_list_payload)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as exc:
            msg = f"Cannot connect to Odoo at {base_url}: {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc
