from typing import Any, Dict, List

import httpx

from app.core.config import get_settings


def _auth_payload(settings) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "db": settings.odoo_db,
            "login": settings.odoo_username,
            "password": settings.odoo_password,
        },
    }


def _fetch_mo_payload(settings, limit: int) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "mrp.production",
            "method": "search_read",
            "args": [[]],
            "kwargs": {
                "fields": [
                    "id",
                    "name",
                    "state",
                    "product_qty",
                    "date_start",
                    "date_finished",
                    "product_id",
                ],
                "order": "id desc",
                "limit": limit,
            },
        },
    }


def main() -> int:
    settings = get_settings()

    base_url = settings.odoo_base_url.rstrip("/")
    auth_url = f"{base_url}/web/session/authenticate"
    dataset_url = f"{base_url}/web/dataset/call_kw/mrp.production/search_read"

    print("=" * 70)
    print("ODOO CONNECTION TEST + GET MO LIST")
    print("=" * 70)
    print(f"Base URL : {base_url}")
    print(f"DB       : {settings.odoo_db}")
    print(f"User     : {settings.odoo_username}")

    try:
        with httpx.Client(timeout=30.0) as client:
            auth_response = client.post(auth_url, json=_auth_payload(settings))
            auth_response.raise_for_status()
            auth_data = auth_response.json()

            if "error" in auth_data:
                print("\n❌ AUTH FAILED")
                print(auth_data["error"])
                return 1

            print("\n✅ Auth success")

            mo_response = client.post(dataset_url, json=_fetch_mo_payload(settings, limit=10))
            mo_response.raise_for_status()
            mo_data = mo_response.json()

            if "error" in mo_data:
                print("\n❌ Fetch MO failed")
                print(mo_data["error"])
                return 1

            records: List[Dict[str, Any]] = mo_data.get("result", [])
            print(f"\n✅ Fetch MO success. Total fetched: {len(records)}")

            if not records:
                print("\n(No MO records returned)")
                return 0

            print("\nTop MO list:")
            print("-" * 70)
            for record in records:
                product = record.get("product_id") or [None, "-"]
                product_name = product[1] if isinstance(product, list) and len(product) > 1 else "-"
                print(
                    f"ID={record.get('id')} | "
                    f"MO={record.get('name')} | "
                    f"State={record.get('state')} | "
                    f"Qty={record.get('product_qty')} | "
                    f"Product={product_name}"
                )

            return 0

    except httpx.HTTPStatusError as error:
        print("\n❌ HTTP error while connecting to Odoo")
        print(f"Status: {error.response.status_code}")
        print(f"Response: {error.response.text}")
        return 1
    except Exception as error:
        print("\n❌ Unexpected error")
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
