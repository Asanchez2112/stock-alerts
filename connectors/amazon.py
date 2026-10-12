import logging
import re
import urllib.parse
from transport import APIError, request_json


class Amazon:
    capabilities = {"new_listing"}

    def __init__(self, key):
        if not key:
            raise ValueError("Amazon requires KEEPA_API_KEY")
        self.key = key

    def fetch(self, item, options):
        term = options.get("search_term") or item["search_term"]
        params = urllib.parse.urlencode({"key": self.key, "domain": 1,
                                        "type": "product", "term": term, "history": 0})
        result = request_json("https://api.keepa.com/search?" + params, "Keepa")
        if result.get("error") or not isinstance(result.get("products"), list):
            raise APIError("Keepa response")
        logging.info("Amazon/%s: %s results, %s tokens left", item["id"],
                     len(result["products"]), result.get("tokensLeft", "unknown"))
        observations = []
        for product in result["products"]:
            asin = product.get("asin", "")
            title = product.get("title", "")
            if not isinstance(title, str) or not isinstance(asin, str) or not re.fullmatch(r"[A-Z0-9]{10}", asin):
                continue
            observations.append({"id": asin, "title": title,
                                 "url": f"https://www.amazon.com/dp/{asin}",
                                 "in_stock": None, "price_cents": None, "currency": "USD"})
        return observations
