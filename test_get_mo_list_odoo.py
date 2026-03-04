#!/usr/bin/env python3
"""
Pre-check script: fetch MO list from Odoo before running Task 1.

Flow:
1. Fetch MO list from Odoo API
2. Validate basic response structure
3. Print summary and sample rows

No DB write and no PLC write.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings
from app.services.odoo_auth_service import fetch_mo_list_detailed


def _print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _safe_get(item: Dict[str, Any], *keys: str, default: Any = "-") -> Any:
    for key in keys:
        if key in item and item.get(key) not in (None, ""):
            return item.get(key)
    return default


def _print_rows(mo_list: List[Dict[str, Any]], sample_limit: int) -> None:
    print(f"\nSample MO rows (max {sample_limit}):")
    for index, mo in enumerate(mo_list[:sample_limit], start=1):
        mo_id = _safe_get(mo, "id", "mo_id")
        name = _safe_get(mo, "name", "mo_name")
        bom = _safe_get(mo, "bom", "bom_name", "no_bom")
        product = _safe_get(mo, "product", "finished_goods", "product_name")
        print(f"  {index:02d}. mo_id={mo_id} | name={name} | bom={bom} | product={product}")


async def run(limit: int, offset: int, sample_limit: int, save_json: str | None) -> int:
    settings = get_settings()

    _print_header("ODOO PRE-CHECK: GET MO LIST (BEFORE TASK 1)")
    print(f"Odoo base URL : {settings.odoo_base_url}")
    print(f"Fetch limit   : {limit}")
    print(f"Offset        : {offset}")

    print("\n[STEP 1] Fetch MO list from Odoo...")
    try:
        payload: Dict[str, Any] = await fetch_mo_list_detailed(limit=limit, offset=offset)
    except Exception as exc:
        print(f"❌ Failed to fetch MO list from Odoo: {exc}")
        return 1

    result = payload.get("result") or {}
    mo_list = result.get("data") or []

    if not isinstance(mo_list, list):
        print("❌ Invalid Odoo response: result.data is not a list")
        return 1

    print("[STEP 2] Validate response structure...")
    print(f"Returned MO count: {len(mo_list)}")

    if save_json:
        output_path = Path(save_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved raw payload: {output_path}")

    if not mo_list:
        print("⚠️ Odoo returned empty list. Task1 will have nothing to sync.")
        return 0

    _print_rows(mo_list, sample_limit=sample_limit)
    print("\n✅ Odoo MO list pre-check passed (safe to proceed to Task1)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-check Odoo MO list before Task1"
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of MO rows to fetch")
    parser.add_argument("--offset", type=int, default=0, help="Fetch offset")
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="How many rows to display in terminal",
    )
    parser.add_argument(
        "--save-json",
        type=str,
        default="",
        help="Optional output JSON path for raw Odoo payload",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        asyncio.run(
            run(
                limit=args.limit,
                offset=args.offset,
                sample_limit=args.sample_limit,
                save_json=args.save_json or None,
            )
        )
    )
