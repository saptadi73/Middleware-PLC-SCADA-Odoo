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
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from app.services.fins_client import FinsUdpClient
from app.services.fins_frames import (
    MemoryReadRequest,
    build_memory_read_frame,
    parse_memory_read_response,
)
from app.services.plc_manual_weighing_service import get_manual_weighing_service


_ILLEGAL_EXCEL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


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

    expected_slot = int(slot)
    expected_keys = {f"SLOT{slot:02d}", f"MANUAL{slot:02d}"}
    return [
        layout
        for layout in all_layouts
        if (
            int(layout.get("slot") or -1) == expected_slot
            or str(layout.get("reference_key", "")).upper() in expected_keys
        )
    ]


def _build_export_rows(raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in raw_results:
        rows.append(
            {
                "reference_key": item.get("reference_key"),
                "batch": item.get("batch"),
                "mo_id": item.get("mo_id"),
                "product_id": item.get("product_id"),
                "consumption": item.get("consumption"),
                "handshake_flag": item.get("handshake_flag"),
                "handshake_address": item.get("handshake_address"),
                "timestamp": item.get("timestamp"),
                "status": item.get("status"),
                "error": item.get("error"),
            }
        )
    return rows


def _write_csv(rows: List[Dict[str, Any]], output_path: Path) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "reference_key",
        "batch",
        "mo_id",
        "product_id",
        "consumption",
        "handshake_flag",
        "handshake_address",
        "timestamp",
        "status",
        "error",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return str(output_path)


def _export_results(raw_results: List[Dict[str, Any]], output_file: Optional[str]) -> str:
    rows = _build_export_rows(raw_results)
    default_name = f"manual_weighing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    target = Path(output_file) if output_file else Path("outputs") / default_name

    if target.suffix.lower() == ".csv":
        written = _write_csv(rows, target)
        return f"CSV tersimpan: {written}"

    try:
        from openpyxl import Workbook
    except ModuleNotFoundError:
        fallback = target.with_suffix(".csv")
        written = _write_csv(rows, fallback)
        return (
            "openpyxl belum terpasang, fallback ke CSV: "
            f"{written} (install openpyxl untuk output .xlsx)"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "manual_weighing"

    headers = [
        "reference_key",
        "batch",
        "mo_id",
        "product_id",
        "consumption",
        "handshake_flag",
        "handshake_address",
        "timestamp",
        "status",
        "error",
    ]
    sheet.append(headers)
    for row in rows:
        sheet.append([_sanitize_excel_value(row.get(col)) for col in headers])

    workbook.save(target)
    return f"Excel tersimpan: {target}"


def _sanitize_excel_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    return _ILLEGAL_EXCEL_CHAR_RE.sub("", text)


def _read_raw_snapshot(service: Any, layout: Dict[str, Any]) -> Dict[str, Any]:
    reference_key = str(layout.get("reference_key") or "MANUAL")
    start_addr = int(layout.get("manual_start_addr") or 0)
    word_count = int(layout.get("manual_word_count") or 0)
    handshake_index = int(layout.get("handshake_index") or 0)
    handshake_address = int(layout.get("handshake_address") or (start_addr + handshake_index))

    base_result: Dict[str, Any] = {
        "reference_key": reference_key,
        "batch": None,
        "mo_id": "",
        "product_id": None,
        "consumption": None,
        "handshake_flag": None,
        "handshake_address": handshake_address,
        "timestamp": datetime.now().isoformat(),
        "status": "raw",
        "error": "",
    }

    try:
        with FinsUdpClient(
            ip=service.settings.plc_ip,
            port=service.settings.plc_port,
            timeout_sec=service.settings.plc_timeout_sec,
        ) as client:
            request = MemoryReadRequest(area="DM", address=start_addr, count=word_count)
            frame = build_memory_read_frame(
                req=request,
                client_node=service.settings.client_node,
                plc_node=service.settings.plc_node,
            )
            client.send_raw_hex(frame.hex())
            response = client.recv()
            words = parse_memory_read_response(response.raw, word_count)

        batch_slice = cast(Tuple[int, int], layout["batch_slice"])
        mo_slice = cast(Tuple[int, int], layout["mo_slice"])
        product_slice = cast(Tuple[int, int], layout["product_slice"])
        consumption_slice = cast(Tuple[int, int], layout["consumption_slice"])

        batch = service._convert_from_words(
            words[batch_slice[0]:batch_slice[1]],
            str(layout.get("batch_type") or "INT"),
            scale=int(layout.get("batch_scale") or 1),
        )
        mo_raw = service._convert_from_words(words[mo_slice[0]:mo_slice[1]], "ASCII")
        product_raw = service._convert_from_words(
            words[product_slice[0]:product_slice[1]],
            str(layout.get("product_type") or "INT"),
            scale=int(layout.get("product_scale") or 1),
        )
        consumption_raw = service._convert_from_words(
            words[consumption_slice[0]:consumption_slice[1]],
            str(layout.get("consumption_type") or "REAL"),
            scale=int(layout.get("consumption_scale") or 100),
        )

        handshake_flag = int(words[handshake_index])
        status = "ready" if handshake_flag == 0 else "already-read"

        base_result.update(
            {
                "batch": int(batch) if isinstance(batch, (int, float)) else batch,
                "mo_id": str(mo_raw).strip() if mo_raw is not None else "",
                "product_id": int(product_raw) if isinstance(product_raw, (int, float)) else product_raw,
                "consumption": float(consumption_raw) if isinstance(consumption_raw, (int, float)) else consumption_raw,
                "handshake_flag": handshake_flag,
                "status": status,
            }
        )
        return base_result

    except Exception as exc:  # noqa: BLE001
        base_result["status"] = "error"
        base_result["error"] = str(exc)
        return base_result


def run(
    slot: Optional[int],
    show_empty: bool,
    mark_handshake: bool,
    export_excel: bool,
    output_file: Optional[str],
) -> int:
    service = get_manual_weighing_service()
    layouts = _get_layouts(service.layouts, slot)

    _print_section("TEST MANUAL WEIGHING READ ONLY")
    print("Mode baca PLC manual weighing saja")
    print("Tidak sync ke Odoo")
    print("Tidak update database")
    print(
        "Mark handshake aktif setelah baca" if mark_handshake else "Tidak mark/reset handshake"
    )
    if export_excel:
        print("Export hasil ke Excel/CSV aktif")

    if not layouts:
        print("\nTidak ada layout manual weighing yang cocok.")
        if slot is not None:
            print(f"Slot yang diminta: SLOT{slot:02d}")
        return 1

    print(f"\nTotal layout dibaca: {len(layouts)}")

    valid_results: List[Dict[str, Any]] = []
    raw_results: List[Dict[str, Any]] = []
    handshake_marked = 0

    for index, layout in enumerate(layouts, start=1):
        reference_key = str(layout.get("reference_key") or f"LAYOUT_{index}")
        start_addr = int(layout.get("manual_start_addr") or 0)
        word_count = int(layout.get("manual_word_count") or 0)
        handshake_addr = int(layout.get("handshake_address") or 0)

        _print_section(f"READ {reference_key}")
        print(f"Address range : D{start_addr}-D{start_addr + word_count - 1}")
        print(f"Handshake     : D{handshake_addr}")

        raw = _read_raw_snapshot(service=service, layout=layout)
        raw_results.append(raw)

        if raw.get("status") == "error":
            print(f"Hasil         : ERROR ({raw.get('error')})")
            continue

        print(f"Batch         : {raw.get('batch')}")
        print(f"MO ID         : {raw.get('mo_id')}")
        print(f"Product ID    : {raw.get('product_id')}")
        print(f"Consumption   : {raw.get('consumption')}")
        print(f"Handshake Flag: {raw.get('handshake_flag')}")
        print(f"Status        : {raw.get('status')}")
        print(f"Timestamp     : {raw.get('timestamp')}")

        data = service.read_manual_weighing_data(layout=layout)
        if data:
            valid_results.append(data)
        elif show_empty and raw.get("status") != "error":
            print("Catatan       : data tidak lolos validasi business rule")

        if mark_handshake:
            handshake_address = raw.get("handshake_address")
            target_address = (
                int(handshake_address)
                if isinstance(handshake_address, (int, float))
                else None
            )
            marked = service.mark_handshake(target_address)
            if marked:
                handshake_marked += 1
                print(f"Handshake ACK : sukses (D{target_address})")
            else:
                print("Handshake ACK : gagal")

    _print_section("RINGKASAN")
    print(f"Layout discan : {len(layouts)}")
    print(f"Data valid    : {len(valid_results)}")
    print(f"Data raw      : {len(raw_results)}")
    if mark_handshake:
        print(f"Handshake ACK : {handshake_marked}")

    if export_excel:
        export_status = _export_results(raw_results, output_file)
        print(f"Export        : {export_status}")

    if not raw_results:
        print("\nTidak ada hasil manual weighing yang bisa ditampilkan.")
        return 0

    print("\nHasil raw manual weighing:")
    for item in raw_results:
        print(
            f"  {item.get('reference_key')} | "
            f"status={item.get('status')} | "
            f"batch={item.get('batch')} | "
            f"mo_id={item.get('mo_id')} | "
            f"product_id={item.get('product_id')} | "
            f"consumption={item.get('consumption')} | "
            f"handshake={item.get('handshake_flag')}"
        )

    if valid_results:
        print("\nHasil valid (lolos business rule):")
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
    parser.add_argument(
        "--mark-handshake",
        action="store_true",
        help="Set status_manual_weigh_read=1 setelah baca data valid (tetap tanpa sync Odoo)",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        default=True,
        help="Ekspor hasil ke file .xlsx (fallback .csv jika openpyxl belum terpasang). Default: aktif",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Nonaktifkan export file (override default export).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path file output, contoh: outputs/manual_weighing.xlsx atau outputs/manual_weighing.csv",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    export_excel = bool(args.export_excel and not args.no_export)
    raise SystemExit(
        run(
            slot=args.slot,
            show_empty=args.show_empty,
            mark_handshake=args.mark_handshake,
            export_excel=export_excel,
            output_file=args.output_file,
        )
    )
