#!/usr/bin/env python3

import sqlite3
import json
import time
import configparser as cp


def _get_config():
    config = cp.ConfigParser()
    config.read("explorer.ini")
    return config


def get_bis_root():
    config = _get_config()
    try:
        return config.get("My Explorer", "bisroot")
    except Exception:
        return "static/ledger.db"


def get_cache_path():
    config = _get_config()
    try:
        return config.get("My Explorer", "circ_cache")
    except Exception:
        return "static/circ_cache.json"


def compute_totals(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT sum(reward) FROM transactions;")
    allcirc = cur.fetchone()[0] or 0

    cur.execute("SELECT sum(amount) FROM transactions WHERE address = 'Development Reward';")
    alldev = cur.fetchone()[0] or 0

    cur.execute("SELECT sum(amount) FROM transactions WHERE address = 'Hyperblock';")
    allhyp = cur.fetchone()[0] or 0

    cur.execute("SELECT sum(amount) FROM transactions WHERE address = 'Hypernode Payouts';")
    allmno = cur.fetchone()[0] or 0

    cur.close()
    conn.close()

    total = float(allcirc) + float(alldev) + float(allhyp) + float(allmno)
    circulating = float(allcirc) + float(allhyp) + float(allmno)

    return {
        "total": "{:.8f}".format(total),
        "circulating": "{:.8f}".format(circulating),
        "timestamp": time.time(),
    }


def main():
    db_path = get_bis_root()
    cache_path = get_cache_path()
    data = compute_totals(db_path)
    with open(cache_path, "w") as outfile:
        json.dump(data, outfile)
    print(f"Wrote circulating supply cache to {cache_path}")


if __name__ == "__main__":
    main()
