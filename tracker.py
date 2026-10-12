"""Shared state and alert rules, independent of any store's API."""
import json
from pathlib import Path
import re
import sqlite3


def normalize(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def matches(observation, item):
    title = normalize(observation["title"])
    return all(normalize(t) in title for t in item["required_terms"]) and not any(
        normalize(t) in title for t in item.get("exclude_terms", []))


def database(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS baselines(item TEXT,store TEXT,PRIMARY KEY(item,store));
        CREATE TABLE IF NOT EXISTS listings(
            item TEXT,store TEXT,product TEXT,stock INTEGER,price INTEGER,currency TEXT,
            PRIMARY KEY(item,store,product));
        CREATE TABLE IF NOT EXISTS outbox(
            id INTEGER PRIMARY KEY,payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0);
    """)
    return db


def ingest(db, item, store, observations, alert_existing=False):
    """None means unknown, never unavailable. A missing search result is not a stock change."""
    initialized = db.execute("SELECT 1 FROM baselines WHERE item=? AND store=?",
                             (item["id"], store)).fetchone()
    alerts = item["alerts"]
    target = item.get("target_price_cents")
    with db:
        for ob in observations:
            if not matches(ob, item):
                continue
            key = (item["id"], store, ob["id"])
            old = db.execute("SELECT stock,price,currency FROM listings WHERE item=? AND store=? AND product=?", key).fetchone()
            stock, price, currency = ob.get("in_stock"), ob.get("price_cents"), ob.get("currency")
            events = []
            if old is None:
                if (initialized or alert_existing) and "new_listing" in alerts:
                    events.append("new_listing")
            elif old[0] == 0 and stock is True and "restock" in alerts:
                events.append("restock")
            qualifies = (type(price) is int and price >= 0 and target is not None
                         and currency == item.get("currency", "USD") and price <= target)
            was_deal = bool(old and old[1] is not None and old[1] <= target
                            and old[2] == currency) if target is not None else False
            if "deal" in alerts and qualifies and not was_deal and (old is not None or initialized or alert_existing):
                events.append("deal")
            for event in events:
                payload = {"event": event, "store": store, "item": item["name"], **ob}
                db.execute("INSERT INTO outbox(payload) VALUES(?)", (json.dumps(payload),))
            # Preserve known state when a later response has incomplete fields.
            if old:
                if stock is None:
                    stock = old[0]
                if price is None:
                    price, currency = old[1], old[2]
            db.execute("INSERT OR REPLACE INTO listings VALUES(?,?,?,?,?,?)", (*key, stock, price, currency))
        db.execute("INSERT OR IGNORE INTO baselines VALUES(?,?)", (item["id"], store))


def deliver(db, webhook, sender):
    labels = {"new_listing": "New listing", "restock": "Restock", "deal": "Target price reached"}
    for event_id, raw in db.execute("SELECT id,payload FROM outbox WHERE sent=0 ORDER BY id").fetchall():
        event = json.loads(raw)
        fields = [{"name": "Tracked item", "value": event["item"][:1000]}]
        if event.get("price_cents") is not None:
            fields.append({"name": "Observed price", "value": f"{event.get('currency', 'USD')} {event['price_cents']/100:.2f}"})
        sender(webhook + "?wait=true", "Discord", {
            "allowed_mentions": {"parse": []},
            "embeds": [{"title": f"{labels[event['event']]} - {event['store'].title()}",
                        "description": event["title"][:1500], "url": event["url"], "fields": fields,
                        "footer": {"text": "Check the store for current availability, shipping and taxes."}}]})
        with db:
            db.execute("UPDATE outbox SET sent=1 WHERE id=?", (event_id,))
