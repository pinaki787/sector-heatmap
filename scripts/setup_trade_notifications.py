#!/usr/bin/env python3
"""Owner-run secure prerequisite collection; never starts services or trading."""
import getpass
import json
import os
import re
import secrets
import sqlite3
import ssl
import smtplib
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAILBOX = "pinaki.prasad.das@gmail.com"
BOT = "SectorPulsePinakiAlertsBot"


def prompt(label, default):
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def telegram(token, method):
    # Never log URLs: Telegram authenticates using a token in the URL path.
    request = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/" + method,
        data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as response:
            data = json.load(response)
        if not data.get("ok"):
            raise RuntimeError("Telegram rejected verification; no response details logged.")
        return data["result"]
    except Exception:
        raise RuntimeError("Telegram verification failed; check the token and network. No secret details logged.") from None


def owner_accounts():
    registry = ROOT / ".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri() + "?mode=ro", uri=True) as db:
        owner = db.execute("SELECT id FROM users WHERE username=?", ("pinaki87",)).fetchone()
        if not owner:
            raise RuntimeError("Expected owner login pinaki87 was not found.")
        return [dict(id=r[0], broker=r[1]) for r in db.execute(
            "SELECT id,broker FROM accounts WHERE user_id=? ORDER BY broker", (owner[0],))]


def private_destination(updates, challenge=None):
    candidates = {}
    for update in updates:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        text = message.get("text", "").strip()
        matches = text == "/start " + challenge if challenge else text.split("@")[0] == "/start"
        if chat.get("type") == "private" and matches:
            candidates[chat["id"]] = chat.get("first_name", "Private chat")
    if len(candidates) != 1:
        raise RuntimeError("Exactly one private /start destination is required. Open your new bot, send /start, and retry.")
    return next(iter(candidates.items()))


def wait_private_destination(token):
    # A per-setup challenge avoids expired updates and ambiguous old /start chats.
    challenge = secrets.token_hex(4)
    print("Open https://t.me/" + BOT + " in YOUR private Telegram chat.")
    print("Send this exact message to that bot: /start " + challenge)
    while True:
        input("After sending it, press Enter here to check (Ctrl+C cancels): ")
        updates = telegram(token, "getUpdates")
        try:
            return private_destination(updates, challenge)
        except RuntimeError:
            print("Fresh setup message not found uniquely yet. Check the bot and resend the exact message above.")
            print("Credentials remain only in this running setup process; you do not need to re-enter them.")


def save_private(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise RuntimeError("Credential directory must not be a symbolic link.")
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".setup-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic creation without replacing any existing credentials.
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main():
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise RuntimeError("Run from your own interactive SSH terminal; hidden entry requires a TTY.")
    target = ROOT / ".private/notifications/config.json"
    if target.exists() or target.is_symlink():
        raise RuntimeError("Notification configuration already exists; refusing to replace it.")
    accounts = owner_accounts()
    if not accounts:
        raise RuntimeError("No owner workspaces found.")
    print("Sector Pulse notification prerequisite setup")
    print("Owner: pinaki87; available brokers: " + ", ".join(a["broker"] for a in accounts))
    print("No service, trading runner or order action will be performed.")
    print("Configuration remains disabled. Credentials will never be printed.")
    sender = recipient = MAILBOX
    print("Email sender and recipient: " + MAILBOX)
    mode = prompt("Modes: BOTH, PAPER, LIVE", "BOTH").upper()
    if mode not in ("BOTH", "PAPER", "LIVE"):
        raise RuntimeError("Invalid Paper/Live mode.")
    selection = prompt("Brokers (ALL or comma-separated names)", "ALL").upper()
    selected = accounts if selection == "ALL" else [a for a in accounts if a["broker"] in selection.split(",")]
    if not selected or (selection != "ALL" and set(selection.split(",")) != {a["broker"] for a in selected}):
        raise RuntimeError("Select only brokers listed for your own login.")
    fills = prompt("Fill notifications: EACH or COMPLETE", "EACH").upper()
    if fills not in ("EACH", "COMPLETE"):
        raise RuntimeError("Invalid fill policy.")
    print("Paste credentials only into the following hidden prompts, never into chat.")
    gmail = "".join(getpass.getpass("Gmail app password (hidden): ").split())
    token = getpass.getpass("Existing new Telegram bot token (hidden): ").strip()
    if not re.fullmatch(r"[A-Za-z]{16}", gmail):
        raise RuntimeError("Expected a 16-letter Gmail app password, not your regular password.")
    if not re.fullmatch(r"[0-9]{5,}:[A-Za-z0-9_-]{20,}", token):
        raise RuntimeError("Telegram token format is invalid.")
    me = telegram(token, "getMe")
    if me.get("username", "").lower() != BOT.lower() or not me.get("is_bot"):
        raise RuntimeError("Token does not belong to the expected Sector Pulse alerts bot.")
    webhook = telegram(token, "getWebhookInfo")
    if webhook.get("url"):
        raise RuntimeError("This bot already has a webhook; no changes made. Review its existing use first.")
    chat_id, name = wait_private_destination(token)
    print(f"Detected private destination: {name}; chat ID {chat_id}")
    if input("Confirm this is YOUR private chat; type YES: ").strip() != "YES":
        raise RuntimeError("Destination not confirmed; no configuration saved.")
    # Verify authorization without sending a message or test email.
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20, context=ssl.create_default_context()) as smtp:
            smtp.login(sender, gmail)
    except Exception:
        raise RuntimeError("Gmail sending authorization failed; no configuration saved. Check your app password.") from None
    config = dict(version=1, enabled=False, owner_username="pinaki87",
                  accounts=selected, modes=["PAPER", "LIVE"] if mode == "BOTH" else [mode],
                  fill_policy=fills, email=dict(sender=sender, recipient=recipient,
                  smtp_host="smtp.gmail.com", smtp_port=465, app_password=gmail),
                  telegram=dict(username=BOT, token=token, chat_id=chat_id),
                  verified_credentials=True, notification_delivery_tested=False)
    save_private(target, config)
    print("Both credentials verified and saved together with owner-only permissions.")
    print("Saved: " + str(target))
    print("Notifications remain DISABLED; no messages sent and no services or runners changed.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled. No service or runner action performed.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Only our fixed messages may be printed; never external exception text.
        message = str(exc) if type(exc) is RuntimeError else "Setup failed safely; no secret details logged."
        print(message, file=sys.stderr)
        sys.exit(1)

