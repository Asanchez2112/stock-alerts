"""Require dashboard protection and persistent storage before starting."""
import base64
import hashlib
import os
from pathlib import Path
import sys


def environment(source):
    env = dict(source)
    if "MONITOR_PASSWORD" not in env:
        raise ValueError("MONITOR_PASSWORD is MISSING from this running container. Check this service's variables in the deployed Railway environment and apply pending changes.")
    password = env.pop("MONITOR_PASSWORD")
    if not password:
        raise ValueError("MONITOR_PASSWORD is present but EMPTY. Enter its value directly in this service's Variables tab and deploy the change.")
    if len(password) < 16:
        raise ValueError("MONITOR_PASSWORD is present but SHORTER THAN 16 characters. Replace its value and deploy the change.")
    if env.get("RAILWAY_VOLUME_MOUNT_PATH") != "/datastore":
        raise ValueError("Attach a Railway volume with mount path /datastore.")
    salt = os.urandom(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    env["SALTED_PASS"] = base64.b64encode(salt + digest).decode("ascii")
    # Keep public-page monitoring separate from private-network/file access.
    env["ALLOW_FILE_URI"] = "false"
    env["ALLOW_IANA_RESTRICTED_ADDRESSES"] = "false"
    env["LLM_FEATURES_DISABLED"] = "true"
    env.pop("DISCORD_WEBHOOK_URL", None)
    env.pop("KEEPA_API_KEY", None)
    return env


def main():
    print("Monitor startup diagnostic v2 (password values are never logged)", file=sys.stderr)
    try:
        env = environment(os.environ)
        if Path("/datastore/removepassword.lock").exists():
            raise ValueError("Remove the password-reset marker before starting this protected service.")
    except ValueError as error:
        print(f"Setup needed: {error}", file=sys.stderr)
        return 1
    # Upstream accepts PORT and LISTEN_HOST from the environment.
    os.execve(sys.executable, [sys.executable, "/app/changedetection.py", "-d", "/datastore"], env)


if __name__ == "__main__":
    raise SystemExit(main())
