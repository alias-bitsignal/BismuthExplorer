#!/usr/bin/env python3

import sqlite3
import configparser as cp
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "explorer.ini"
DEFAULT_BIS = BASE_DIR / "static" / "ledger.db"


def _get_config():
    config = cp.ConfigParser()
    config.read(CONFIG_PATH)
    return config


def _resolve_path(value, default_path):
    if not value:
        return str(default_path)
    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


def get_bis_root():
    config = _get_config()
    try:
        return _resolve_path(config.get("My Explorer", "bisroot"), DEFAULT_BIS)
    except Exception:
        return str(DEFAULT_BIS)


def _explain(conn, sql, params):
    cur = conn.cursor()
    cur.execute("EXPLAIN QUERY PLAN " + sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def _print_plan(label, rows):
    print(label)
    for row in rows:
        print("  ", row)


def main():
    db_path = get_bis_root()
    print(f"Database: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA case_sensitive_like=ON;")

        # fetch_address_data
        _print_plan(
            "fetch_address_data: sum(amount) recipient",
            _explain(
                conn,
                "SELECT sum(amount) FROM transactions WHERE recipient = ?;",
                ("SAMPLE_ADDRESS",),
            ),
        )
        _print_plan(
            "fetch_address_data: sum(amount),sum(fee),sum(reward) address",
            _explain(
                conn,
                "SELECT sum(amount),sum(fee),sum(reward) FROM transactions WHERE address = ?;",
                ("SAMPLE_ADDRESS",),
            ),
        )
        _print_plan(
            "fetch_address_data: count rewards",
            _explain(
                conn,
                "SELECT count(*) FROM transactions WHERE address = ? AND (reward != 0);",
                ("SAMPLE_ADDRESS",),
            ),
        )
        _print_plan(
            "fetch_address_data: max/min reward timestamps",
            _explain(
                conn,
                "SELECT MAX(timestamp), MIN(timestamp) FROM transactions WHERE recipient = ? AND (reward != 0);",
                ("SAMPLE_ADDRESS",),
            ),
        )

        # fetch_address_transactions
        _print_plan(
            "fetch_address_transactions: address/recipient",
            _explain(
                conn,
                """
                SELECT block_height, timestamp, address, recipient, amount, signature
                FROM transactions
                WHERE address = ? OR recipient = ?
                ORDER BY timestamp DESC, signature DESC
                LIMIT ?;
                """,
                ("SAMPLE_ADDRESS", "SAMPLE_ADDRESS", 21),
            ),
        )

        # get_the_details (signature lookup)
        _print_plan(
            "get_the_details: signature LIKE prefix",
            _explain(
                conn,
                "SELECT * FROM transactions WHERE signature LIKE ?;",
                ("SAMPLE_SIG%",),
            ),
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
