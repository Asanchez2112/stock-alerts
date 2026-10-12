import json
from pathlib import Path
import tempfile
import unittest
from app import load_items
from tracker import database, ingest, deliver
from transport import APIError

ITEM = {"id": "test", "name": "Test item", "required_terms": ["Collector"],
        "alerts": ["new_listing", "restock", "deal"], "target_price_cents": 15000}
OB = {"id": "123", "title": "Collector Box", "url": "https://example.com/item",
      "in_stock": False, "price_cents": 16000, "currency": "USD"}


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "state.sqlite3"
        self.db = database(self.path)

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def events(self):
        return [json.loads(row[0])["event"] for row in self.db.execute("SELECT payload FROM outbox")]

    def test_baseline_restock_deal_and_repeated_observations(self):
        ingest(self.db, ITEM, "test_store", [OB])
        self.assertEqual(self.events(), [])
        new = dict(OB, in_stock=True, price_cents=15000)
        ingest(self.db, ITEM, "test_store", [new])
        self.assertEqual(self.events(), ["restock", "deal"])
        ingest(self.db, ITEM, "test_store", [new])
        self.assertEqual(len(self.events()), 2)

    def test_unknown_or_missing_is_not_out_of_stock(self):
        ingest(self.db, ITEM, "test_store", [dict(OB, in_stock=None)])
        ingest(self.db, ITEM, "test_store", [])
        ingest(self.db, ITEM, "test_store", [dict(OB, in_stock=True)])
        self.assertEqual(self.events(), [])

    def test_unknown_price_does_not_rearm_deal(self):
        ingest(self.db, ITEM, "test_store", [dict(OB, price_cents=14000)])
        ingest(self.db, ITEM, "test_store", [dict(OB, price_cents=None)])
        ingest(self.db, ITEM, "test_store", [dict(OB, price_cents=14000)])
        self.assertEqual(self.events(), [])

    def test_store_isolation_and_new_unpriced_product(self):
        ingest(self.db, ITEM, "amazon", [])
        ingest(self.db, ITEM, "amazon", [dict(OB, price_cents=None)])
        ingest(self.db, ITEM, "target", [OB])
        self.assertEqual(self.events(), ["new_listing"])

    def test_pending_alert_survives_restart_and_failure(self):
        ingest(self.db, ITEM, "amazon", [OB], True)
        def fail(*args):
            raise APIError("Discord", 429)
        with self.assertRaises(APIError):
            deliver(self.db, "https://example.com", fail)
        self.db.close()
        self.db = database(self.path)
        sent = []
        deliver(self.db, "https://example.com", lambda *args: sent.append(args))
        deliver(self.db, "https://example.com", lambda *args: sent.append(args))
        self.assertEqual(len(sent), 1)

    def test_unsupported_store_rejected(self):
        config = [dict(ITEM, search_term="Collector", alerts=["new_listing"], stores={"target": {"enabled": True}})]
        path = Path(self.folder.name) / "products.json"
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "not implemented"):
            load_items(path)


if __name__ == "__main__":
    unittest.main()
