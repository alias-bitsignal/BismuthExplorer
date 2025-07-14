"""

Bismuth Explorer Tools DB Module

Version 2.0.2

"""

import os
import time
import sqlite3
import logging
from glob import glob
from logging.handlers import RotatingFileHandler
from configparser import ConfigParser
import toolsp

# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────
LOG_FILE = 'toolsdb.log'
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s'
)

handler = RotatingFileHandler(
    LOG_FILE,
    mode='a',
    maxBytes=5 * 1024 * 1024,
    backupCount=2,
    encoding='utf-8'
)
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
config = ConfigParser()
config.read('explorer.ini')
bis_root = config.get('My Explorer', 'bisroot', fallback='static/ledger.db')
bis_limit = config.getint('My Explorer', 'bis_limit', fallback=1)

def init_tools_db(db_path='tools.db'):
    """Create a fresh tools.db with the right schema."""
    if os.path.exists(db_path):
        logger.info("Removing existing %s", db_path)
        os.remove(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS richlist (
                address TEXT PRIMARY KEY,
                balance REAL,
                alias   TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS minerlist (
                address    TEXT PRIMARY KEY,
                blatest    INTEGER,
                bfirst     INTEGER,
                blockcount INTEGER,
                treward    REAL,
                mname      TEXT
            )
            """
        )
        logger.info("Initialized tools.db with WAL mode")


def gather_all_addresses(conn):
    """Get all unique recipients with non-zero amount or reward."""
    rows = conn.execute(
        "SELECT DISTINCT recipient FROM transactions WHERE amount != 0 OR reward != 0"
    )
    return [row[0] for row in rows]


def gather_delta_addresses(conn, limit):
    """Get unique recipients and senders from the last `limit` transactions."""
    cur = conn.execute(
        "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
    seen = set()
    for row in cur:
        recipient = row[2]
        if recipient and recipient.lower() not in {"hypernode payouts", "development reward"}:
            seen.add(recipient)
        sender = row[3]
        if sender:
            seen.add(sender)
    return list(seen)


def updatedb(do_full, last_block=None, db_path='tools.db'):
    """Update tools.db fully or incrementally based on last_block."""
    logger.info("Starting %s update (since=%s)", 'full' if do_full else 'delta', last_block)

    if do_full:
        init_tools_db(db_path)

    # 1) Gather addresses
    with sqlite3.connect(bis_root) as src_conn:
        src_conn.row_factory = lambda cursor, row: row
        if do_full:
            addresses = gather_all_addresses(src_conn)
        else:
            latest_block = int(toolsp.latest()[0])
            block_limit = latest_block - last_block
            if block_limit <= 0:
                logger.info("No new blocks since %s", last_block)
                return False
            addresses = gather_delta_addresses(src_conn, block_limit)

    if not addresses:
        logger.info("No addresses to process.")
        return False

    # 2) Delete old entries (incremental) and insert fresh rows
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN")
        if not do_full:
            conn.executemany(
                "DELETE FROM richlist WHERE address = ?",
                ((addr,) for addr in addresses),
            )
            conn.executemany(
                "DELETE FROM minerlist WHERE address = ?",
                ((addr,) for addr in addresses),
            )

        rich_rows = []
        miner_rows = []

        for addr in addresses:
            try:
                record = toolsp.refresh(addr, 2)
            except Exception:
                logger.exception("Error refreshing %r", addr)
                continue

            balance = float(record[4])
            reward  = float(record[2])
            alias   = record[8]

            if balance > bis_limit:
                rich_rows.append((addr, balance, alias))
            if reward > 0:
                miner_rows.append((
                    addr,
                    record[5],  # blatest
                    record[6],  # bfirst
                    record[7],  # blockcount
                    reward,
                    alias,
                ))

        if rich_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO richlist(address,balance,alias) VALUES (?,?,?)",
                rich_rows,
            )
        if miner_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO minerlist VALUES (?,?,?,?,?,?)",
                miner_rows,
            )

        conn.commit()

    logger.info("Completed %s update for %d addresses.", 'full' if do_full else 'delta', len(addresses))
    return True


def buildtoolsdb():
    fpath = 'blocks.txt'

    # First run: write latest block and do full update
    if not os.path.exists(fpath):
        latest = int(toolsp.latest()[0])
        with open(fpath, 'w') as f:
            f.write(f"{latest}\n")
        updatedb(do_full=True)

    # Main loop: incremental updates every 20 minutes
    while True:
        # Cleanup QR images
        for qr in glob('static/qr*.png'):
            os.remove(qr)

        # Determine last block threshold
        with open(fpath) as f:
            last_blk = int(f.readline().strip()) - 200

        # Write new latest
        latest = int(toolsp.latest()[0])
        with open(fpath, 'w') as f:
            f.write(f"{latest}\n")

        # Run incremental update
        updatedb(do_full=False, last_block=last_blk)
        logger.info("Sleeping for 20 minutes before next update.")
        time.sleep(20 * 60)


if __name__ == '__main__':
    buildtoolsdb()
