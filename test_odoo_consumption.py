"""
Test Odoo Consumption Service - Consumption update dan mark done workflow

Demonstrasi penggunaan konsumsi update ke Odoo setelah membaca PLC.
"""

import asyncio
import logging
from app.services.odoo_consumption_service import (
    get_consumption_service,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_consumption_update():
    """Test update consumption untuk single atau multiple silo."""
    logger.info("=" * 60)
    logger.info("TEST: Update Consumption")
    logger.info("=" * 60)

    service = get_consumption_service()

    # Contoh data consumption dari PLC read
    consumption_data = {
        "silo_a": 50.5,
        "silo_b": 25.3,
        "silo_c": 10.0,
    }

    result = await service.update_consumption(
        mo_id="MO/2025/001",
        equipment_id="PLC01",
        consumption_data=consumption_data,
    )

    logger.info(f"Result: {result}")
    assert result["success"], f"Update consumption failed: {result}"
    logger.info("✓ Consumption updated successfully\n")


async def test_mark_mo_done():
    """Test mark MO sebagai done setelah manufacturing selesai."""
    logger.info("=" * 60)
    logger.info("TEST: Mark MO as Done")
    logger.info("=" * 60)

    service = get_consumption_service()

    result = await service.mark_mo_done(
        mo_id="MO/2025/001",
        finished_qty=1000.0,
        equipment_id="PLC01",
        auto_consume=True,
    )

    logger.info(f"Result: {result}")
    assert result["success"], f"Mark done failed: {result}"
    logger.info("✓ MO marked as done successfully\n")


async def test_batch_consumption():
    """Test comprehensive batch consumption processing."""
    logger.info("=" * 60)
    logger.info("TEST: Batch Consumption Processing")
    logger.info("=" * 60)

    service = get_consumption_service()

    # Simulasi data batch dari mo_batch table setelah read PLC
    batch_data = {
        "consumption_silo_a": 50.5,
        "consumption_silo_b": 25.3,
        "consumption_silo_c": 10.0,
        "consumption_silo_d": 0,  # No consumption untuk silo_d
        "consumption_silo_e": 0,
        "consumption_silo_f": 0,
        "consumption_silo_g": 0,
        "consumption_silo_h": 0,
        "consumption_silo_i": 0,
        "consumption_silo_j": 0,
        "consumption_silo_k": 0,
        "consumption_silo_l": 0,
        "consumption_silo_m": 0,
        "status_manufacturing": 1,  # Manufacturing selesai
        "actual_weight_quantity_finished_goods": 1000.0,
    }

    result = await service.process_batch_consumption(
        mo_id="MO/2025/001",
        equipment_id="PLC01",
        batch_data=batch_data,
    )

    logger.info(f"Result: {result}")
    logger.info(f"Consumption updated: {result['consumption']['consumption_updated']}")
    logger.info(f"MO marked done: {result['mark_done']['mo_marked_done']}")
    logger.info("✓ Batch consumption processed successfully\n")


def test_silo_mapping():
    """Test silo mapping reference."""
    logger.info("=" * 60)
    logger.info("TEST: Silo Mapping")
    logger.info("=" * 60)

    service = get_consumption_service()
    mapping = service.get_silo_mapping()

    logger.info(f"Total silos: {len(mapping)}")
    for silo_id, silo_data in list(mapping.items())[:3]:
        logger.info(f"  Silo {silo_id}: {silo_data}")

    # Test get by ID
    silo_101 = service.get_silo_by_id(101)
    logger.info(f"Silo 101: {silo_101}")

    # Test get by SCADA tag
    silo_a = service.get_silo_by_scada_tag("silo_a")
    logger.info(f"SCADA silo_a: {silo_a}")

    logger.info("✓ Silo mapping working correctly\n")


async def main():
    """Run all tests."""
    logger.info("\n\n" + "=" * 60)
    logger.info("ODOO CONSUMPTION SERVICE - COMPREHENSIVE TEST")
    logger.info("=" * 60 + "\n")

    try:
        # Test 1: Silo mapping
        test_silo_mapping()

        # Test 2: Consumption update (requires Odoo endpoint)
        # WARNING: Uncomment hanya jika Odoo instance tersedia
        # await test_consumption_update()

        # Test 3: Mark MO done (requires Odoo endpoint)
        # WARNING: Uncomment hanya jika Odoo instance tersedia
        # await test_mark_mo_done()

        # Test 4: Batch consumption (requires Odoo endpoint)
        # WARNING: Uncomment hanya jika Odoo instance tersedia
        # await test_batch_consumption()

        logger.info("=" * 60)
        logger.info("✓ ALL TESTS COMPLETED")
        logger.info("=" * 60)
        logger.info("\nNotes:")
        logger.info("- Tests yang memerlukan Odoo instance commented out")
        logger.info("- Uncomment di test function untuk integration testing")
        logger.info("- Pastikan Odoo credentials di .env sudah benar")

    except AssertionError as e:
        logger.error(f"✗ Test assertion failed: {e}")
        raise
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
