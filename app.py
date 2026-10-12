import argparse
import json
import logging
import os
from pathlib import Path
import re
import signal
import sqlite3
import threading
from connectors import CONNECTORS
from tracker import database, deliver, ingest, normalize
from transport import APIError, request_json

ROOT = Path(__file__).resolve().parent
STORES = {"amazon", "walmart", "target", "best_buy"}
EVENTS = {"new_listing", "restock", "deal"}


def load_items(path):
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("products.json needs at least one item")
    seen = set()
    for item in items:
        for field in ("id", "name", "search_term"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Each item needs {field}")
        if item["id"] in seen:
            raise ValueError("Item IDs must be unique")
        seen.add(item["id"])
        for field in ("required_terms", "exclude_terms"):
            terms = item.get(field, [])
            if not isinstance(terms, list) or any(not isinstance(t, str) or not normalize(t) for t in terms):
                raise ValueError(f"Invalid {field}")
        if not item.get("required_terms"):
            raise ValueError("Each item needs required_terms")
        if not isinstance(item.get("alerts"), list) or not item["alerts"] or not set(item["alerts"]) <= EVENTS:
            raise ValueError("Invalid alert types")
        if "deal" in item["alerts"] and (type(item.get("target_price_cents")) is not int or item["target_price_cents"] < 0):
            raise ValueError("Deal alerts need nonnegative integer target_price_cents")
        if not isinstance(item.get("stores"), dict) or not item["stores"]:
            raise ValueError("Each item needs stores")
        for store, options in item["stores"].items():
            if store not in STORES or not isinstance(options, dict):
                raise ValueError("Invalid store configuration")
            if type(options.get("enabled", False)) is not bool:
                raise ValueError("Store enabled must be true or false")
            if not item.get("active", True) or not options.get("enabled", False):
                continue
            if store not in CONNECTORS:
                raise ValueError(f"{store} connector is not implemented yet; leave enabled=false")
            unsupported = set(item["alerts"]) - CONNECTORS[store].capabilities
            if unsupported:
                raise ValueError(f"{store} does not yet provide: {', '.join(sorted(unsupported))}")
    return [item for item in items if item.get("active", True)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    items = load_items(os.getenv("PRODUCTS_FILE", str(ROOT / "products.json")))
    jobs = [(item, store, options) for item in items for store, options in item["stores"].items() if options.get("enabled", False)]
    if not jobs:
        raise ValueError("Enable at least one implemented store for an active item")
    if args.demo:
        for item, store, _ in jobs:
            print(f"{item['name']} -> {store}: {', '.join(item['alerts'])}")
        print("Offline preview only. No requests, alerts or state changes.")
        return 0
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not re.fullmatch(r"https://(?:discord\.com|discordapp\.com)/api/webhooks/\d+/[A-Za-z0-9_-]+", webhook):
        raise ValueError("Set DISCORD_WEBHOOK_URL in Railway variables")
    clients = {store: CONNECTORS[store](os.getenv("KEEPA_API_KEY", "").strip()) for _, store, _ in jobs}
    interval = int(os.getenv("CHECK_EVERY", "900"))
    if interval < 60:
        raise ValueError("CHECK_EVERY must be at least 60")
    volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if os.getenv("RAILWAY_ENVIRONMENT_ID") and not volume:
        raise ValueError("Attach a Railway volume at /data")
    db = database(Path(os.getenv("DATA_DIR") or volume or ROOT / "data") / "stock-alerts.sqlite3")
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        while not stop.is_set():
            failed = False
            try:
                deliver(db, webhook, request_json)
            except APIError as error:
                logging.error("%s; queue retained", error)
                failed = True
            for item, store, options in jobs:
                if stop.is_set():
                    break
                try:
                    observations = clients[store].fetch(item, options)
                    ingest(db, item, store, observations, os.getenv("ALERT_EXISTING", "0") == "1")
                except APIError as error:
                    logging.error("%s/%s: %s", store, item["id"], error)
                    failed = True
            try:
                deliver(db, webhook, request_json)
            except APIError as error:
                logging.error("%s; queue retained", error)
                failed = True
            if args.once:
                return int(failed)
            stop.wait(interval)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, sqlite3.Error) as error:
        logging.error("Configuration/state error: %s", error)
        raise SystemExit(1)
