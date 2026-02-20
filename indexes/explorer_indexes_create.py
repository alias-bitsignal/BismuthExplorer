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

INDEX_SQL = {
    "idx_tx_reward_ts_sig": (
        "CREATE INDEX IF NOT EXISTS idx_tx_reward_ts_sig "
        "ON transactions(reward, timestamp DESC, signature DESC)"
    ),
    "idx_tx_reward_block": (
        "CREATE INDEX IF NOT EXISTS idx_tx_reward_block "
        "ON transactions(reward, block_height DESC)"
    ),
    "idx_tx_block_height": (
        "CREATE INDEX IF NOT EXISTS idx_tx_block_height "
        "ON transactions(block_height)"
    ),
    "idx_tx_address_ts_sig": (
        "CREATE INDEX IF NOT EXISTS idx_tx_address_ts_sig "
        "ON transactions(address, timestamp DESC, signature DESC)"
    ),
    "idx_tx_recipient_ts_sig": (
        "CREATE INDEX IF NOT EXISTS idx_tx_recipient_ts_sig "
        "ON transactions(recipient, timestamp DESC, signature DESC)"
    ),
    "idx_tx_address": (
        "CREATE INDEX IF NOT EXISTS idx_tx_address "
        "ON transactions(address)"
    ),
    "idx_tx_recipient": (
        "CREATE INDEX IF NOT EXISTS idx_tx_recipient "
        "ON transactions(recipient)"
    ),
    "idx_tx_signature": (
        "CREATE INDEX IF NOT EXISTS idx_tx_signature "
        "ON transactions(signature)"
    ),
}


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


def create_indexes(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for name in INDEXES:
        cur.execute(INDEX_SQL[name])
    conn.commit()
    cur.close()
    conn.close()


def main():
    db_path = get_bis_root()
    create_indexes(db_path)
    print(f"Created explorer indexes on {db_path}")
    hyper_path = get_hyper_root()
    if hyper_path and hyper_path != db_path:
        create_indexes(hyper_path)
        print(f"Created explorer indexes on {hyper_path}")


if __name__ == "__main__":
    main()
