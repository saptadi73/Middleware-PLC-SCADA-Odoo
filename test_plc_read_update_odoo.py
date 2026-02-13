"""
PLC READ to ODOO Consumption Update Test
=========================================

Script ini melakukan:
1. Read data dari PLC memory menggunakan FINS protocol
2. Extract consumption data untuk semua silo (A-M)
3. Direct update ke Odoo MO consumption menggunakan /api/scada/mo/update-with-consumptions
4. Auto mark-done jika status_manufacturing = 1

Workflow:
  PLC (FINS) -> PLCReadService -> Batch Process -> OdooConsumptionService -> Odoo MO
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.odoo_consumption_service import get_consumption_service
from app.services.plc_read_service import get_plc_read_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
DEBUG_RESPONSE_BODY = True
ENABLE_MARK_DONE = False


def print_section(title: str) -> None:
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_step(step_num: int, description: str) -> None:
    """Print formatted step."""
    print(f"\n[STEP {step_num}] {description}")
    print("-" * 80)


def print_debug_response(label: str, data: dict) -> None:
    """Print full response body for debugging."""
    if not DEBUG_RESPONSE_BODY:
        return
    print(f"\n[DEBUG] {label} response body:")
    try:
        print(json.dumps(data, indent=2, ensure_ascii=True, default=str))
    except Exception:
        print(str(data))


def read_plc_data() -> dict:
    """
    Read batch data dari PLC.

    Returns:
        Dictionary dengan MO data dan consumption info
    """
    print_step(1, "Read Batch Data from PLC")

    try:
        service = get_plc_read_service()
        batch_data = service.read_batch_data()

        print(f"[OK] MO ID: {batch_data.get('mo_id')}")
        print(f"[OK] Product: {batch_data.get('product_name')}")
        print(f"[OK] BoM: {batch_data.get('bom_name')}")
        print(f"[OK] Quantity: {batch_data.get('quantity')}")
        print(f"[OK] Status Manufacturing: {batch_data['status'].get('manufacturing')}")
        print(f"[OK] Status Operation: {batch_data['status'].get('operation')}")
        print(f"[OK] Weight Finished: {batch_data.get('weight_finished_good')}")

        # Display silos
        print("\n[OK] Silos Consumption:")
        for letter, silo_data in batch_data.get("silos", {}).items():
            consumption = silo_data.get("consumption", 0)
            silo_id = silo_data.get("id", "")
            if consumption > 0:
                print(f"    Silo {letter.upper()} (ID {silo_id}): {consumption}")

        return batch_data

    except Exception as exc:
        logger.exception(f"[ERROR] Error reading PLC data: {exc}")
        raise


def format_batch_for_odoo(batch_data: dict) -> dict:
    """
    Format batch data untuk Odoo consumption update.

    Args:
        batch_data: Dictionary dari PLC

    Returns:
        Dictionary dengan format untuk update_consumption_with_odoo_codes()
    """
    print_step(2, "Format Batch Data for Odoo")

    # Extract consumption data keyed by SCADA tag (silo_a, silo_b, etc.)
    consumption_data = {}
    for letter, silo_data in batch_data.get("silos", {}).items():
        consumption = silo_data.get("consumption", 0)
        scada_tag = f"silo_{letter}"
        if consumption > 0:
            consumption_data[scada_tag] = consumption

    formatted_data = {
        "mo_id": batch_data.get("mo_id"),
        "equipment_id": "PLC01",  # Default equipment ID
        "quantity": batch_data.get("quantity"),
        "consumption_data": consumption_data,
        "status_manufacturing": batch_data["status"].get("manufacturing", False),
        "finished_qty": batch_data.get("weight_finished_good", 0),
        "batch_data": batch_data,  # Pass full batch for reference
    }

    print(f"[OK] Formatted MO ID: {formatted_data['mo_id']}")
    print(f"[OK] Equipment: {formatted_data['equipment_id']}")
    print(f"[OK] Quantity: {formatted_data['quantity']}")
    print(f"[OK] Consumption entries: {len(consumption_data)}")
    for scada_tag, qty in consumption_data.items():
        print(f"    - {scada_tag}: {qty}")
    print(f"[OK] Status Manufacturing: {formatted_data['status_manufacturing']}")
    print(f"[OK] Finished Qty: {formatted_data['finished_qty']}")

    return formatted_data


async def update_odoo_consumption(formatted_data: dict) -> dict:
    """
    Update MO consumption di Odoo menggunakan /mo/update-with-consumptions endpoint.

    Args:
        formatted_data: Dictionary dengan MO dan consumption data

    Returns:
        Dictionary dengan response dari Odoo
    """
    print_step(3, "Update MO Consumption in Odoo")

    try:
        service = get_consumption_service()

        mo_id = formatted_data.get("mo_id")
        consumption_data = formatted_data.get("consumption_data", {})

        if not mo_id:
            raise ValueError("MO ID tidak ditemukan dalam PLC data")

        if not consumption_data:
            print("[WARN] Tidak ada consumption data untuk diupdate")
            return {"success": False, "error": "No consumption data"}

        print(
            "Calling update_consumption_with_odoo_codes() with "
            "/mo/update-with-consumptions endpoint..."
        )
        print(f"  - MO ID: {mo_id}")
        print(f"  - Total Entries: {len(consumption_data)}")

        result = await service.update_consumption_with_odoo_codes(
            mo_id=mo_id,
            consumption_data=consumption_data,
            quantity=formatted_data.get("quantity"),
        )

        if result.get("success"):
            print("[OK] Consumption updated successfully")
            consumed_items = result.get("consumed_items", []) or []
            print(f"  - Total items updated: {len(consumed_items)}")
            if result.get("partial_success"):
                print("  - Status: PARTIAL SUCCESS")
            if result.get("errors"):
                print(f"  - Errors: {result.get('errors')}")
            if result.get("message"):
                print(f"  - Message: {result.get('message')}")
        else:
            print(f"[ERROR] Error: {result.get('error')}")

        print_debug_response("Update consumption", result)
        return result

    except Exception as exc:
        logger.exception(f"[ERROR] Error updating Odoo consumption: {exc}")
        raise


async def mark_mo_done_if_needed(formatted_data: dict) -> dict:
    """
    Mark MO as done jika status_manufacturing = 1.

    Args:
        formatted_data: Dictionary dengan batch data

    Returns:
        Dictionary dengan response
    """
    print_step(4, "Mark MO as Done (if status_manufacturing=1)")

    try:
        if not ENABLE_MARK_DONE:
            print("[INFO] ENABLE_MARK_DONE = False, skip mark done")
            return {"success": True, "skipped": True}

        if not formatted_data.get("status_manufacturing"):
            print("[WARN] status_manufacturing = 0, skip mark done")
            return {"success": True, "skipped": True}

        service = get_consumption_service()
        mo_id = formatted_data.get("mo_id")
        finished_qty = formatted_data.get("finished_qty", 0)

        if not mo_id:
            raise ValueError("MO ID tidak ditemukan")

        if finished_qty <= 0:
            print("[WARN] finished_qty <= 0, skip mark done")
            return {"success": True, "skipped": True}

        print("Calling mark_mo_done()...")
        print(f"  - MO ID: {mo_id}")
        print(f"  - Finished Qty: {finished_qty}")

        result = await service.mark_mo_done(
            mo_id=mo_id,
            finished_qty=finished_qty,
            equipment_id="PLC01",
            auto_consume=True,
        )

        if result.get("success"):
            print("[OK] MO marked as done successfully")
            print(f"  - Message: {result.get('message')}")
        else:
            print(f"[ERROR] Error: {result.get('error')}")

        print_debug_response("Mark MO done", result)
        return result

    except Exception as exc:
        logger.exception(f"[ERROR] Error marking MO as done: {exc}")
        raise


async def main():
    """Main test flow."""
    print_section("PLC READ -> ODOO CONSUMPTION UPDATE")

    print("\nThis test will:")
    print("1. Read batch data from PLC memory")
    print("2. Format data for Odoo consumption update")
    print("3. Update MO consumption in Odoo (/api/scada/mo/update-with-consumptions)")
    print("4. Optional mark-done (controlled by ENABLE_MARK_DONE)")
    print("\nPrerequisites:")
    print("- PLC reachable (FINS UDP)")
    print("- Odoo API reachable with valid credentials")
    print("- Database migration applied")

    try:
        # Step 1: Read PLC data
        batch_data = read_plc_data()

        # Step 2: Format for Odoo
        formatted_data = format_batch_for_odoo(batch_data)

        # Step 3: Update Odoo consumption
        update_result = await update_odoo_consumption(formatted_data)

        # Step 4: Mark done if needed
        mark_done_result = await mark_mo_done_if_needed(formatted_data)

        # Summary
        print_section("SUMMARY")

        print("\n[OK] PLC Read: OK")
        print("[OK] Format: OK")
        print(f"[OK] Odoo Update: {'OK' if update_result.get('success') else 'FAILED'}")
        print(f"[OK] Mark Done: {'OK' if mark_done_result.get('success') else 'SKIPPED'}")

        print("\nWorkflow completed: PLC -> Odoo MO Consumption")
        print(f"  MO ID: {formatted_data.get('mo_id')}")
        print(f"  Consumption Entries: {len(formatted_data.get('consumption_data', {}))}")
        print(f"  Status: {'COMPLETED' if update_result.get('success') else 'PARTIAL'}")

    except KeyboardInterrupt:
        print("\n\n[WARN] Test cancelled by user")
        sys.exit(1)
    except Exception as exc:
        logger.exception(f"\n\n[ERROR] Test failed with error: {exc}")
        print_section("ERROR")
        print(f"Exception: {type(exc).__name__}")
        print(f"Message: {str(exc)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
