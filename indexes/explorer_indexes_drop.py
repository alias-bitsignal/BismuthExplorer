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

def drop_indexes(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for name in INDEXES:
        cur.execute(f"DROP INDEX IF EXISTS {name}")
    conn.commit()
    cur.close()
    conn.close()


def main():
    db_path = get_bis_root()
    drop_indexes(db_path)
    print(f"Dropped explorer indexes from {db_path}")
    hyper_path = get_hyper_root()
    if hyper_path and hyper_path != db_path:
        drop_indexes(hyper_path)
        print(f"Dropped explorer indexes from {hyper_path}")


if __name__ == "__main__":
    main()
