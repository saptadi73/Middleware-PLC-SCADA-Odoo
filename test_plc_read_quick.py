"""
Quick PLC Read to Odoo Sync Test
=================================

Simplified sync test untuk quick testing tanpa async complications.
Berguna untuk:
- Testing PLC connection
- Verifying consumption data mapping
- Quick development checks
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.plc_read_service import get_plc_read_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Simple PLC read test."""
    print("\n" + "=" * 80)
    print(" QUICK PLC READ TEST")
    print("=" * 80)
    
    try:
        # Get PLC read service
        service = get_plc_read_service()
        print(f"\n✓ PLCReadService initialized")
        print(f"✓ Loaded {len(service.mapping)} field definitions from mapping")
        
        # Read batch data
        print(f"\nReading batch data from PLC...")
        batch_data = service.read_batch_data()
        
        # Display results
        print(f"\n{'='*80}")
        print(" READ DATA FROM PLC:")
        print(f"{'='*80}")
        
        print(f"\nMO Information:")
        print(f"  ID: {batch_data.get('mo_id')}")
        print(f"  Product: {batch_data.get('product_name')}")
        print(f"  BoM: {batch_data.get('bom_name')}")
        print(f"  Quantity: {batch_data.get('quantity')}")
        
        print(f"\nStatus:")
        print(f"  Manufacturing: {batch_data['status'].get('manufacturing')}")
        print(f"  Operation: {batch_data['status'].get('operation')}")
        print(f"  Finished Weight: {batch_data.get('weight_finished_good')}")
        
        print(f"\nSilo Consumption:")
        total_consumption = 0
        for letter, silo_data in batch_data.get("silos", {}).items():
            consumption = silo_data.get("consumption", 0)
            silo_id = silo_data.get("id", "")
            total_consumption += consumption
            
            marker = "✓" if consumption > 0 else "○"
            print(f"  {marker} Silo {letter.upper()} (ID {silo_id:>3}): {consumption:>10}")
        
        print(f"\n  Total Consumption: {total_consumption}")
        
        print(f"\n{'='*80}")
        print(" JSON OUTPUT:")
        print(f"{'='*80}\n")
        
        import json
        print(json.dumps(batch_data, indent=2, default=str))
        
        print(f"\n{'='*80}")
        print(" ✓ PLC Read Test Completed Successfully")
        print(f"{'='*80}\n")
        
    except Exception as exc:
        logger.exception(f"✗ Error: {exc}")
        print(f"\n✗ Test failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
