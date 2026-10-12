import gzip
import json
import urllib.error
import urllib.request

class APIError(Exception):
    def __init__(self, service, status=None):
        super().__init__(f"{service} request failed" + (f" (HTTP {status})" if status else ""))


def request_json(url, service, payload=None):
    headers = {"Accept-Encoding": "gzip", "User-Agent": "MTGListingNotifier/1.0"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=45) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        raise APIError(service, error.code) from None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        # Never include raw exceptions: they may contain API keys/webhook URLs.
        raise APIError(service) from None

