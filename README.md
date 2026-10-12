# Stock Alerts

One Railway worker, multiple products, pluggable store connectors, Discord alerts and persistent SQLite history. Python 3.12+, standard library only.

## Current status

Amazon US new-listing discovery through Keepa is implemented. Walmart, Target and Best Buy are reserved configuration entries, disabled until their integrations are built and verified. Shared rules for restocks and target-price deals are implemented and tested using offline observations. The Amazon connector currently reports neither stock nor prices; enabling those alert types fails configuration validation rather than silently pretending to monitor them.

This is the first repository version, not a live four-store monitor. No live API requests or Discord sends have been verified yet.

## GitHub upload (next step)

Extract the stock-alerts ZIP. In the empty GitHub repository, select **uploading an existing file**, drag the contents of the extracted folder into the upload area, and commit to main. Upload the contents, not the enclosing folder: Dockerfile and app.py must be at the repository root. Make sure the connectors folder is uploaded too. No credentials are included in this package.

## Railway setup (after upload)

Create a service from this GitHub repository. Railway builds the Dockerfile. Attach a volume at `/data`, run one replica, and set the following variables:

- `KEEPA_API_KEY`: requires Keepa API subscription.
- `DISCORD_WEBHOOK_URL`: your Discord channel webhook.
- `CHECK_EVERY=900`: seconds between completed cycles.
- `ALERT_EXISTING=0`: first successful check for each item/store establishes a quiet baseline. Set 1 before the first run to alert on existing matches too.

No public domain needed. Railway reads the code from GitHub; secrets stay in Railway variables and runtime history stays on the volume. Connect automatic deployments to your main branch. Changing code preserves history when the same volume is attached.

## Products and future connectors

Add items to products.json with unique stable IDs, search terms and title filters. Current example terms match Collector packs and boxes. To restrict boxes, add a suitable title term. Multiple differently named products can be tracked in the same file. Avoid broad terms if you want alerts for a specific package size.

Each store connector returns observations: id, title, url, in_stock (true/false/null), price_cents (integer/null), and currency. Unknown values stay null. Stock alerts require an observed unavailable-to-available transition; missing search results never count as unavailable. Deal alerts fire when the observed price crosses at or below target_price_cents in the configured currency. A future price connector must clearly define seller, shipping and freshness semantics before activation. New-listing alerts fire for newly observed IDs after baseline. Restock and price capabilities must be declared by the connector before their alert types can be enabled.

The shared tracker stores item/store/product state and a durable outgoing queue in one transaction. Failed sends are retried after the next cycle or restart. A timeout or crash after Discord accepts a message can still produce a duplicate. Use one worker replica. This version starts with a new stock-alerts.sqlite3 database; it does not migrate the earlier prototype's database.

## Local verification

Run `python app.py --demo` for an offline configuration preview. Run `python -m unittest -v` for the offline alert-rule and persistence tests. A live check uses `python app.py --once` with credentials in environment variables. .env.example is reference only; .env files are not automatically loaded.

## Discovery limitations

Keepa searches may lag Amazon and return limited ranked results; detection of every listing is not guaranteed. Two watches at 15-minute intervals use roughly 80 base search tokens/hour, plus any applicable refresh charges. API errors are logged without credential-bearing request URLs.

API reference: https://keepa.com/api-docs/product-search.html
Railway volumes: https://docs.railway.com/volumes
