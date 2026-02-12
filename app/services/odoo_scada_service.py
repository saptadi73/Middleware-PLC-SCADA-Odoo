from typing import Any, Dict

import httpx

from app.core.config import get_settings


async def fetch_mo_list_detailed(limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    settings = get_settings()

    base_url = settings.odoo_base_url.rstrip("/")
    auth_url = f"{base_url}/api/scada/authenticate"
    mo_list_url = f"{base_url}/api/scada/mo-list-detailed"

    auth_payload = {
        "db": settings.odoo_db,
        "login": settings.odoo_username,
        "password": settings.odoo_password,
    }

    mo_list_payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "limit": limit,
            "offset": offset,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        auth_response = await client.post(auth_url, json=auth_payload)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        if auth_data.get("status") != "success":
            raise RuntimeError(f"Odoo auth failed: {auth_data}")

        mo_response = await client.post(mo_list_url, json=mo_list_payload)
        mo_response.raise_for_status()
        return mo_response.json()
