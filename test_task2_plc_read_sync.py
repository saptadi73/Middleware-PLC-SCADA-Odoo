#!/usr/bin/env python3
"""
Task 2 test script (PLC -> mo_batch only).

Apa yang dilakukan script ini:
1. Menampilkan snapshot mo_batch sebelum Task 2
2. Menjalankan Task 2 (plc_read_sync_task)
3. Menampilkan snapshot mo_batch setelah Task 2

Catatan:
- Script ini TIDAK sync ke Odoo (itu Task 3).
- Fokusnya hanya read PLC dan update data ke PostgreSQL.
"""

import argparse
import asyncio
from typing import Any, Dict, List

from sqlalchemy import text

from app.core.scheduler import plc_read_sync_task
from app.db.session import SessionLocal


def _print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _get_snapshot(sample_limit: int = 10) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        total = db.execute(text("SELECT COUNT(*) FROM mo_batch")).scalar() or 0
        active = db.execute(
            text("SELECT COUNT(*) FROM mo_batch WHERE status_manufacturing = false")
        ).scalar() or 0
        completed = db.execute(
            text("SELECT COUNT(*) FROM mo_batch WHERE status_manufacturing = true")
        ).scalar() or 0

        rows = db.execute(
            text(
                """
                SELECT
                    batch_no,
                    mo_id,
                    status_manufacturing,
                    status_operation,
                    last_read_from_plc,
                    actual_weight_quantity_finished_goods,
                    actual_consumption_silo_a,
                    actual_consumption_silo_b,
                    actual_consumption_silo_c,
                    actual_consumption_silo_d,
                    actual_consumption_silo_e,
                    actual_consumption_silo_f,
                    actual_consumption_silo_g,
                    actual_consumption_silo_h,
                    actual_consumption_silo_i,
                    actual_consumption_silo_j,
                    actual_consumption_silo_k,
                    actual_consumption_silo_l,
                    actual_consumption_silo_m
                FROM mo_batch
                ORDER BY batch_no
                LIMIT :limit
                """
            ),
            {"limit": sample_limit},
        ).mappings().all()

        return {
            "total": int(total),
            "active": int(active),
            "completed": int(completed),
            "rows": [dict(row) for row in rows],
        }
    finally:
        db.close()


def _print_snapshot(label: str, snapshot: Dict[str, Any]) -> None:
    _print_section(label)
    print(f"Total rows    : {snapshot['total']}")
    print(f"Active rows   : {snapshot['active']}")
    print(f"Completed rows: {snapshot['completed']}")

    rows: List[Dict[str, Any]] = snapshot["rows"]
    if not rows:
        print("\n(no rows in mo_batch)")
        return

    print("\nSample rows:")
    for row in rows:
        total_consumption = 0.0
        for letter in "abcdefghijklm":
            value = row.get(f"actual_consumption_silo_{letter}")
            if value is not None:
                total_consumption += float(value)

        print(
            f"  batch_no={row.get('batch_no')} | "
            f"mo_id={row.get('mo_id')} | "
            f"status_mfg={row.get('status_manufacturing')} | "
            f"status_op={row.get('status_operation')} | "
            f"actual_fg={row.get('actual_weight_quantity_finished_goods')} | "
            f"sum_actual_cons={total_consumption:.3f} | "
            f"last_read={row.get('last_read_from_plc')}"
        )


async def run(sample_limit: int) -> int:
    _print_section("TASK 2 TEST: PLC READ -> UPDATE mo_batch")
    print("Task 2 behavior:")
    print("1) Cek batch aktif (status_manufacturing=false)")
    print("2) Read PLC sekali per cycle")
    print("3) Update actual consumption/status ke mo_batch")
    print("4) Tidak sync ke Odoo (Task 3 yang handle)")

    before = _get_snapshot(sample_limit=sample_limit)
    _print_snapshot("BEFORE TASK 2", before)

    _print_section("RUN TASK 2")
    await plc_read_sync_task()
    print("Task 2 executed.")

    after = _get_snapshot(sample_limit=sample_limit)
    _print_snapshot("AFTER TASK 2", after)

    if before["total"] == 0:
        print("\n⚠️ mo_batch kosong, jadi Task 2 tidak punya batch untuk diproses.")
        return 0

    if after["active"] <= before["active"]:
        print("\n✅ Task 2 run selesai. Cek kolom actual_* dan last_read_from_plc pada sample di atas.")
    else:
        print("\nℹ️ Task 2 run selesai, tapi jumlah active bertambah (kemungkinan ada proses lain paralel).")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Task 2 (PLC read sync)")
    parser.add_argument("--sample-limit", type=int, default=10, help="Jumlah sample row untuk ditampilkan")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(run(sample_limit=args.sample_limit)))
