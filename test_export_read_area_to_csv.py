"""
Export PLC READ area (batch snapshot) to CSV.
Output file: app/reference/read_data_plc_input.csv

Important:
- Uses ONE snapshot read per batch to avoid mixed/torn values across fields.
- This keeps CSV values aligned with debug snapshot output.
"""

import csv
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.plc_read_service import get_plc_read_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_mapping(mapping_path: Path, batch_no: int) -> List[Dict[str, Any]]:
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping not found at {mapping_path}")

    plc_service = get_plc_read_service()
    if mapping_path.resolve() != (
        Path(__file__).parent / "app" / "reference" / "READ_DATA_PLC_MAPPING.json"
    ).resolve():
        raise ValueError(
            "This exporter uses READ_DATA_PLC_MAPPING.json loaded by PLCReadService"
        )
    return plc_service._get_batch_mapping(batch_no)


def _normalize_value(data_type: str, value: Any) -> str:
    if value is None:
        return ""

    data_type = data_type.upper()
    if data_type == "BOOLEAN":
        return "1" if bool(value) else "0"

    return str(value)


def export_plc_to_csv(mapping_path: Path, output_path: Path, batch_no: int = 1) -> Dict[str, Any]:
    plc_service = get_plc_read_service()
    rows = _load_mapping(mapping_path, batch_no=batch_no)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = ["No", "Informasi", "Data Type", "length", "Sample", "scale", "DM - Memory", "Value"]

    written = 0
    failed = 0
    errors: List[str] = []

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()

        snapshot_words, _, _ = plc_service._read_batch_snapshot_with_quality(batch_no=batch_no)
        if not snapshot_words:
            raise RuntimeError(f"Failed reading snapshot for batch {batch_no}")

        for row in rows:
            info = row.get("Informasi")
            data_type = row.get("Data Type")
            if not info or not data_type:
                continue

            try:
                value = plc_service._decode_field_from_snapshot(
                    words=snapshot_words,
                    field_def=row,
                    batch_no=batch_no,
                )
                row_out = {
                    "No": row.get("No"),
                    "Informasi": info,
                    "Data Type": data_type,
                    "length": row.get("length", ""),
                    "Sample": row.get("Sample"),
                    "scale": row.get("scale"),
                    "DM - Memory": row.get("DM") or row.get("DM - Memory"),
                    "Value": _normalize_value(data_type, value),
                }
                writer.writerow(row_out)
                written += 1
            except Exception as exc:
                failed += 1
                error_msg = f"Error reading {info}: {exc}"
                errors.append(error_msg)
                logger.error(error_msg)

    return {"written": written, "failed": failed, "errors": errors}


def main() -> None:
    mapping_path = Path(__file__).parent / "app" / "reference" / "READ_DATA_PLC_MAPPING.json"
    output_path = Path(__file__).parent / "app" / "reference" / "read_data_plc_input.csv"
    batch_no = 1

    print("\n" + "=" * 80)
    print("EXPORT PLC READ AREA TO CSV")
    print("=" * 80)
    print(f"Mapping: {mapping_path}")
    print(f"Output: {output_path}")
    print(f"Batch : {batch_no}")
    print("This will read one snapshot and overwrite the CSV file.")
    print("\nPress Ctrl+C to cancel or Enter to continue...")
    input()

    results = export_plc_to_csv(mapping_path, output_path, batch_no=batch_no)

    print("\n" + "=" * 80)
    print("EXPORT RESULTS")
    print("=" * 80)
    print(f"✓ Written: {results['written']} fields")
    print(f"✗ Failed: {results['failed']} fields")

    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - {error}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExport cancelled by user")
