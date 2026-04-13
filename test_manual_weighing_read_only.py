#!/usr/bin/env python3
"""
Read-only test untuk memory manual weighing.

Script ini sengaja hanya:
1. Membaca memory manual weighing dari PLC
2. Menampilkan hasil pembacaan yang valid

Script ini TIDAK:
- Menjalankan scheduler task lain
- Sync ke Odoo
- Update database
- Mark/reset handshake
"""

import argparse
from typing import Any, Dict, List, Optional

from app.services.plc_manual_weighing_service import get_manual_weighing_service


def _print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _get_layouts(
    all_layouts: List[Dict[str, Any]],
    slot: Optional[int],
) -> List[Dict[str, Any]]:
    if slot is None:
        return all_layouts

    expected_key = f"MANUAL{slot:02d}"
    return [
        layout
        for layout in all_layouts
        if str(layout.get("reference_key", "")).upper() == expected_key
    ]


def run(slot: Optional[int], show_empty: bool) -> int:
    service = get_manual_weighing_service()
    layouts = _get_layouts(service.layouts, slot)

    _print_section("TEST MANUAL WEIGHING READ ONLY")
    print("Mode baca PLC manual weighing saja")
    print("Tidak sync ke Odoo")
    print("Tidak update database")
    print("Tidak mark/reset handshake")

    if not layouts:
        print("\nTidak ada layout manual weighing yang cocok.")
        if slot is not None:
            print(f"Slot yang diminta: MANUAL{slot:02d}")
        return 1

    print(f"\nTotal layout dibaca: {len(layouts)}")

    valid_results: List[Dict[str, Any]] = []

    for index, layout in enumerate(layouts, start=1):
        reference_key = str(layout.get("reference_key") or f"LAYOUT_{index}")
        start_addr = int(layout.get("manual_start_addr") or 0)
        word_count = int(layout.get("manual_word_count") or 0)
        handshake_addr = int(layout.get("handshake_address") or 0)

        _print_section(f"READ {reference_key}")
        print(f"Address range : D{start_addr}-D{start_addr + word_count - 1}")
        print(f"Handshake     : D{handshake_addr}")

        data = service.read_manual_weighing_data(layout=layout)
        if not data:
            if show_empty:
                print("Hasil         : tidak ada data baru / handshake sudah terbaca / data tidak valid")
            continue

        valid_results.append(data)
        print(f"Batch         : {data.get('batch')}")
        print(f"MO ID         : {data.get('mo_id')}")
        print(f"Product ID    : {data.get('product_id')}")
        print(f"Consumption   : {data.get('consumption')}")
        print(f"Handshake Flag: {data.get('handshake_flag')}")
        print(f"Timestamp     : {data.get('timestamp')}")

    _print_section("RINGKASAN")
    print(f"Layout discan : {len(layouts)}")
    print(f"Data valid    : {len(valid_results)}")

    if not valid_results:
        print("\nTidak ada hasil manual weighing baru yang bisa ditampilkan.")
        return 0

    print("\nHasil manual weighing:")
    for item in valid_results:
        print(
            f"  {item.get('reference_key')} | "
            f"batch={item.get('batch')} | "
            f"mo_id={item.get('mo_id')} | "
            f"product_id={item.get('product_id')} | "
            f"consumption={item.get('consumption')}"
        )

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only test untuk PLC manual weighing"
    )
    parser.add_argument(
        "--slot",
        type=int,
        choices=range(1, 11),
        help="Baca slot tertentu saja (1-10), contoh: --slot 1",
    )
    parser.add_argument(
        "--show-empty",
        action="store_true",
        help="Tampilkan juga slot yang tidak punya data baru",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(run(slot=args.slot, show_empty=args.show_empty))
