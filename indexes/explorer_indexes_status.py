#!/usr/bin/env python3

import sqlite3
import configparser as cp
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "explorer.ini"
DEFAULT_BIS = BASE_DIR / "static" / "ledger.db"
DEFAULT_HYPER = BASE_DIR / "static" / "hyper.db"

INDEXES = [
    "idx_tx_reward_ts_sig",
    "idx_tx_reward_block",
    "idx_tx_block_height",
    "idx_tx_address_ts_sig",
    "idx_tx_recipient_ts_sig",
    "idx_tx_address",
    "idx_tx_recipient",
    "idx_tx_signature",
]


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


def get_hyper_root():
    config = _get_config()
    try:
        return _resolve_path(config.get("My Explorer", "hyperroot"), DEFAULT_HYPER)
    except Exception:
        return str(DEFAULT_HYPER)


def list_indexes(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='transactions';")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    by_name = {name: sql for name, sql in rows}
    return by_name


def report(db_path):
    print(f"Database: {db_path}")
    try:
        indexes = list_indexes(db_path)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return
    for name in INDEXES:
        sql = indexes.get(name)
        if sql:
            print(f"  OK   {name}: {sql}")
        else:
            print(f"  MISSING {name}")


def main():
    db_path = get_bis_root()
    report(db_path)
    hyper_path = get_hyper_root()
    if hyper_path and hyper_path != db_path:
        report(hyper_path)


if __name__ == "__main__":
    main()
