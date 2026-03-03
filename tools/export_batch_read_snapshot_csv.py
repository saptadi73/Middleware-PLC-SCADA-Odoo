#!/usr/bin/env python3
"""Export one live PLC READ batch snapshot to CSV using active mapping."""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is importable when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.plc_read_service import get_plc_read_service


def build_rows(batch_no: int) -> List[Dict[str, Any]]:
    read_service = get_plc_read_service()
    mapping = read_service._get_batch_mapping(batch_no)
    start_address = read_service._get_batch_start_address(batch_no)

    snapshot_words = read_service._read_batch_snapshot_words(batch_no=batch_no)
    if not snapshot_words:
        raise RuntimeError(f"Failed to read snapshot for batch {batch_no}")

    snapshot_time_utc = datetime.now(timezone.utc).isoformat()
    rows: List[Dict[str, Any]] = []

    for field_def in mapping:
        field_name = str(field_def.get("Informasi") or "")
        if not field_name:
            continue

        dm_str = read_service._resolve_dm_string(field_def)
        data_type = str(field_def.get("Data Type") or "")
        scale = field_def.get("scale")

        field_start, word_count = read_service._parse_dm_address(dm_str)
        start_index = field_start - start_address
        end_index = start_index + word_count
        if start_index < 0 or end_index > len(snapshot_words):
            raw_words: List[int] = []
            decoded_value: Any = None
            normalized_value: Any = None
            decode_error = f"DM {dm_str} out of snapshot range"
        else:
            raw_words = snapshot_words[start_index:end_index]
            try:
                decoded_value = read_service._convert_from_words(
                    words=raw_words,
                    data_type=data_type,
                    scale=scale,
                )
                normalized_value = read_service._decode_field_from_snapshot(
                    words=snapshot_words,
                    field_def=field_def,
                    batch_no=batch_no,
                )
                decode_error = ""
            except Exception as exc:
                decoded_value = None
                normalized_value = None
                decode_error = str(exc)

        rows.append(
            {
                "snapshot_time_utc": snapshot_time_utc,
                "batch_no": batch_no,
                "field_no": field_def.get("No"),
                "field_name": field_name,
                "dm_address": dm_str,
                "data_type": data_type,
                "scale": "" if scale is None else scale,
                "raw_words": "|".join(str(int(word) & 0xFFFF) for word in raw_words),
                "decoded_value": decoded_value,
                "normalized_value": normalized_value,
                "decode_error": decode_error,
            }
        )

    return rows


def export_csv(batch_no: int, output_path: Path) -> Path:
    rows = build_rows(batch_no=batch_no)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "snapshot_time_utc",
                "batch_no",
                "field_no",
                "field_name",
                "dm_address",
                "data_type",
                "scale",
                "raw_words",
                "decoded_value",
                "normalized_value",
                "decode_error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def export_all_batches(output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files: List[Path] = []
    for batch_no in range(1, 11):
        file_name = f"PLC_BATCH_READ_{batch_no:02d}_LIVE.csv"
        file_path = output_dir / file_name
        exported_files.append(export_csv(batch_no=batch_no, output_path=file_path))
    return exported_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export live PLC READ batch snapshot to CSV using active mapping"
    )
    parser.add_argument("--batch", type=int, default=1, help="Batch number (1..10)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export all batches (1..10)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("PLC_BATCH_READ_01_D6000_LIVE.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("."),
        help="Output directory used when --all is set",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.all:
        files = export_all_batches(output_dir=args.out_dir)
        print("Exported live snapshot CSV files:")
        for file_path in files:
            print(f"- {file_path}")
        return 0

    output = export_csv(batch_no=args.batch, output_path=args.out)
    print(f"Exported live snapshot CSV: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
