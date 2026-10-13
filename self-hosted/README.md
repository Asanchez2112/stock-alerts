# Self-hosted ChangeDetection on Railway

Free monitoring software, paid Railway infrastructure. This folder is separate from the original Keepa worker. It uses official image ghcr.io/dgtlmoon/changedetection.io:0.60.9 and a startup wrapper. No secrets are included.

## Step 1: upload

Extract the ZIP and upload the entire self-hosted folder to the existing stock-alerts GitHub repository. The resulting paths must be self-hosted/Dockerfile, self-hosted/start.py, and self-hosted/README.md. Commit the upload.

## Step 2: create a service

In Railway add a new service from the same repository, name it changedetection, and set Settings -> Source -> Root Directory to /self-hosted. Leave the start command unset: the Docker image defines startup. Use one replica.

The initial startup will intentionally stop with a setup message until both the password and volume are configured. Do not generate a public domain yet.

## Step 3: storage and password

Attach a volume at /datastore. Set MONITOR_PASSWORD in this new service's Railway Variables to a unique password of at least 16 characters, saved in your password manager. Never put it in GitHub or chat. This is the password you will type at the dashboard login. The wrapper derives the upstream SALTED_PASS value at startup and removes the plain password from the app's inherited environment. The plain password remains protected by your Railway account's variable access.

No Keepa API key is needed. Configure Discord later through ChangeDetection's Notifications settings; the original worker's DISCORD_WEBHOOK_URL variable is not read by ChangeDetection. Store notification settings are saved on the volume, so keep backups private.

## Step 4: open dashboard

After startup succeeds, generate a Railway domain targeting port 5000. Open its HTTPS URL in a fresh signed-out session and verify it requires a password before showing monitors or settings. Only then configure notifications or watches. Set BASE_URL to the HTTPS domain if notification links need it.

## Step 5: test

Configure one public product page, a 15-minute interval, and Discord notifications. Send a test notification and inspect the fetched content. Test price/stock detection separately before relying on alerts. Watch search-page product titles for discovery; generic page changes are not necessarily new listings.

This first deployment uses the normal HTTP fetcher. Sites that rely on JavaScript may require a separate private browser service with additional memory and cost. We will verify the first page before adding that service. Do not expose the browser service publicly. Retailers may block requests, and we cannot guarantee monitoring of all four stores.

The official image is version-pinned for reproducibility; it will not automatically pick up security updates. Review releases and update the Dockerfile as needed. This wrapper has been checked locally for password derivation and fail-closed behavior, but the Docker image and live Railway deployment have not yet been tested in this session.

References:
- https://github.com/dgtlmoon/changedetection.io/releases/tag/0.60.9
- https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/flask_app.py
- https://github.com/dgtlmoon/changedetection.io/blob/master/docker-compose.yml
