"""
Query Odoo PostgreSQL for stock_move / stock_move_line data by move_ids.

Usage:
  python query_odoo_moves.py --move-ids 23,24,25
"""

import argparse
import os
from typing import List

import psycopg2


def _parse_ids(raw: str) -> List[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--move-ids",
        required=True,
        help="Comma-separated stock_move IDs, e.g. 23,24,25",
    )
    args = parser.parse_args()

    move_ids = _parse_ids(args.move_ids)
    if not move_ids:
        print("No move_ids provided")
        return 1

    host = os.getenv("PGHOST", "localhost")
    port = int(os.getenv("PGPORT", "5432"))
    dbname = os.getenv("PGDATABASE", "manukanjabung")
    user = os.getenv("PGUSER", "openpg")
    password = os.getenv("PGPASSWORD", "openpgpwd")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )
    try:
        with conn.cursor() as cur:
            # Detect available columns (Odoo versions differ)
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'stock_move'
                """,
            )
            move_cols = {r[0] for r in cur.fetchall()}

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'stock_move_line'
                """,
            )
            move_line_cols = {r[0] for r in cur.fetchall()}

            move_select = ["id"]
            for c in ["quantity_done", "product_uom_qty", "state"]:
                if c in move_cols:
                    move_select.append(c)

            cur.execute(
                f"""
                SELECT {", ".join(move_select)}
                FROM stock_move
                WHERE id = ANY(%s)
                ORDER BY id
                """,
                (move_ids,),
            )
            print("stock_move:")
            for row in cur.fetchall():
                print(row)

            move_line_select = ["id", "move_id"]
            for c in ["qty_done", "quantity_done", "product_uom_qty", "state"]:
                if c in move_line_cols:
                    move_line_select.append(c)

            cur.execute(
                f"""
                SELECT {", ".join(move_line_select)}
                FROM stock_move_line
                WHERE move_id = ANY(%s)
                ORDER BY move_id, id
                """,
                (move_ids,),
            )
            print("\nstock_move_line:")
            for row in cur.fetchall():
                print(row)

            # Enriched view: product + UoM + rounding
            cur.execute(
                """
                SELECT sm.id AS move_id,
                       pt.name AS product_name,
                       uom.name AS uom_name,
                       uom.rounding AS uom_rounding,
                       sml.qty_done AS qty_done
                FROM stock_move sm
                LEFT JOIN product_product pp ON pp.id = sm.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN uom_uom uom ON uom.id = sm.product_uom
                LEFT JOIN stock_move_line sml ON sml.move_id = sm.id
                WHERE sm.id = ANY(%s)
                ORDER BY sm.id
                """,
                (move_ids,),
            )
            print("\nmove_uom_rounding:")
            for row in cur.fetchall():
                print(row)

            # Decimal precision overview (if installed)
            try:
                cur.execute(
                    """
                    SELECT name, digits
                    FROM decimal_precision
                    WHERE name IN ('Product Unit of Measure', 'Stock Weight')
                    ORDER BY name
                    """
                )
                print("\ndecimal_precision:")
                for row in cur.fetchall():
                    print(row)
            except Exception as exc:
                print("\n(decimal_precision table not available):", exc)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
