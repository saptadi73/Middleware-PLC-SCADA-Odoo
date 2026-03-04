#!/usr/bin/env python3
"""Verify LQ114/LQ115 values in PLC WRITE area (Task1 output)."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.plc_read_service import get_plc_read_service


def decode_real_scale100(high_word: int, low_word: int) -> float:
    raw = ((high_word & 0xFFFF) << 16) | (low_word & 0xFFFF)
    if raw > 2147483647:
        raw -= 4294967296
    return float(raw) / 100.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Task1 LQ values in WRITE area D7000+"
    )
    parser.add_argument("--from-batch", type=int, default=1)
    parser.add_argument("--to-batch", type=int, default=10)
    args = parser.parse_args()

    start_batch = max(1, args.from_batch)
    end_batch = min(30, args.to_batch)

    svc = get_plc_read_service()

    print("\n" + "=" * 84)
    print("TASK1 WRITE-AREA VERIFY: LQ114/LQ115")
    print("=" * 84)
    print("Address pattern per batch: D(7000 + (batch-1)*100 + 66..71)")
    print("Fields: [LQ114_ID, LQ114_CONS_H, LQ114_CONS_L, LQ115_ID, LQ115_CONS_H, LQ115_CONS_L]\n")

    for batch_no in range(start_batch, end_batch + 1):
        base = 7000 + (batch_no - 1) * 100
        addr = base + 66
        words = svc._read_from_plc(addr, 6)

        lq114_id = words[0] & 0xFFFF
        lq114_cons = decode_real_scale100(words[1], words[2])
        lq115_id = words[3] & 0xFFFF
        lq115_cons = decode_real_scale100(words[4], words[5])

        print(
            f"batch={batch_no:02d} | D{addr}-D{addr+5} | raw={words} | "
            f"LQ114(id={lq114_id},cons={lq114_cons:.2f}) | "
            f"LQ115(id={lq115_id},cons={lq115_cons:.2f})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
