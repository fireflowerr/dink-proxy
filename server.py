"""
Dink Proxy – Webhook Interception & Dynamic Routing Proxy

Receives webhooks from external services, inspects the payload to
dynamically determine which Discord webhook URL to forward to, and
optionally transforms the payload before forwarding.

Handlers inspect the incoming payload and return a (target_url, payload)
tuple. The target_url is the Discord webhook to forward to; the payload
is the modified Discord-compatible body.

Endpoints:
    POST /hook   – receive a webhook, inspect & transform, forward to Discord.
    GET  /health – health check.
"""

import json
import logging
import os
from typing import Callable
from urllib import parse

import requests
from flask import Flask, jsonify, request


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler chain
# ---------------------------------------------------------------------------
# Ordered list of (priority, fn).  Each fn receives (payload: dict, headers: dict).
# The first handler to return a non-None result wins.
#
# Return:  (discord_webhook_url: str, discord_payload: dict)
#      or  None  (skip — try the next handler)
#
# Register with the @handler decorator.
# ---------------------------------------------------------------------------

HANDLERS: list = []


def handler(fn=None, *, priority: int = 0):
    """Decorator to register a payload inspector / forwarder.

    Handlers are called in descending priority order. The first handler
    that returns a (url, payload) tuple wins.  Return None to pass.
    """
    def decorator(fn):
        HANDLERS.append((priority, fn))
        HANDLERS.sort(key=lambda x: x[0], reverse=True)
        return fn

    if fn is not None:
        return decorator(fn)
    return decorator


# ---------------------------------------------------------------------------
# DinkPlugin type routing config
# ---------------------------------------------------------------------------


dink_config: dict | None = None


# Set of valid NotificationType enum names from DinkPlugin (hardcoded for
# fast detection without touching the filesystem).
_ALLOWED_DINK_TYPES: frozenset = frozenset({
    "COLLECTION",
    "DEATH",
    "LEVEL",
    "LOOT",
    "PET",
    "COMBAT_ACHIEVEMENT",
    "ACHIEVEMENT_DIARY",
    "PLAYER_KILL",
})


_Dink_Handler = Callable[[dict], dict | None]


_DINK_HANDLERS: list[_Dink_Handler] = []


def _register_dink_handler(dink_handler: _Dink_Handler) -> None:
    """Register a handler for a dink type"""
    global _DINK_HANDLERS
    _DINK_HANDLERS.append(dink_handler)


@_register_dink_handler
def _dink_allowlist_handler(payload: dict) -> dict | None:
    """Drop disallowed dink types."""
    dink_type = payload.get('type', '')
    if dink_type in _ALLOWED_DINK_TYPES:
        return payload

    log.debug(f'Dropping disallowed type {dink_type}')
    return None


@_register_dink_handler
def _echo_handler(payload: dict) -> dict:
    log.info(json.dumps(payload, indent=2))
    return payload


@_register_dink_handler
def _dink_style_handler(payload: dict) -> dict:
    """Customize look of webhook embed"""
    embeds: list[dict] = payload.get('embeds', [])
    for embed in embeds:
        embed['color'] = 11674146
        del embed['footer']
        del embed['timestamp']

    return payload


@_register_dink_handler
def _dink_look_handler(payload: dict) -> dict | None:
    """Normalize loot embeds."""
    dink_type = payload.get('type', '')
    if dink_type != 'LOOT':
        return payload

    extra = payload.get('extra', {})
    items = extra.get('items', [])
    description = ''
    should_send: bool = False
    for item in items:
        name = item['name']
        raw_link = 'https://oldschool.runescape.wiki/w/Special:Search?' + parse.urlencode({'search': name})
        link = f'[{name}]({raw_link})'
        quantity = item['quantity']
        value = item['priceEach']

        if value < 600000:
            continue

        should_send = True
        pretty_value = f'{value:,}'
        description += f'• {quantity} x {link} ({pretty_value})\n'

    if not should_send:
        return None

    embeds: list[dict] = payload.get('embeds', [])
    embed = embeds[0]
    embed['description'] = description
    del embed['fields']

    return payload


def _load_dink_config() -> dict:
    """Load dink.json (notification type → Discord webhook URL)."""
    global dink_config
    if dink_config is not None:
        return dink_config

    tmp = {}

    value: str | None = None
    value = os.environ.get('DINK_DEFAULT_HOOK')
    if value is not None:
        tmp['DEFAULT'] = value

    for dink_type in _ALLOWED_DINK_TYPES:
        value = os.environ.get(f'DINK_{dink_type}_HOOK')
        if value is not None:
            tmp[dink_type] = value

    dink_config = tmp
    return tmp


# ---------------------------------------------------------------------------
# Body parsing
# ---------------------------------------------------------------------------


def _extract_boundary(content_type: str) -> str | None:
    """Pull the boundary string from a multipart Content-Type header."""
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            return part.split("=", 1)[1].strip('"')
    return None


def _parse_body(raw_body: bytes, content_type: str) -> list[dict]:
    """Parse request body into a list of parts — *always* returns ``list[dict]``.

    Each part is ``{"name": str, "headers": str, "body": bytes}``.

    * Non-multipart   → one element with ``name="body"``.
    * multipart       → one element per MIME part.
    """
    if "multipart" in content_type:
        boundary = _extract_boundary(content_type)
        if boundary:
            return _split_multipart(raw_body, boundary)

    return [{"name": "body", "headers": "", "body": raw_body}]


def _split_multipart(body: bytes, boundary: str) -> list[dict]:
    """Split a multipart/form-data body into its constituent parts."""
    delimiter = f"--{boundary}".encode()
    raw_parts = body.split(delimiter)[1:]  # element 0 is preamble (empty if body starts with boundary)

    result: list[dict] = []
    for part in raw_parts:
        # Closing delimiter: --boundary--\r\n  →  after split we get "--\r\n"
        if part.startswith(b"--"):
            break

        # Strip leading \r\n left over from the split
        if part.startswith(b"\r\n"):
            part = part[2:]

        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        headers_block = part[:header_end].decode("utf-8", errors="replace")
        body_bytes = part[header_end + 4:].rstrip(b"\r\n")

        name = ""
        for hdr in headers_block.split("\r\n"):
            if "name=" in hdr:
                name = hdr.split("name=", 1)[1].strip('"').split('"')[0]
                break

        result.append({"name": name, "headers": headers_block, "body": body_bytes})

    return result


def _extract_payload_json(parts: list[dict]) -> tuple[dict, list[dict]]:
    """Pull the parsed ``payload_json`` dict and return the *remaining* parts.

    Returns ``(payload, remaining_parts)`` where *remaining_parts* has the
    ``payload_json`` entry removed (keeping only screenshots / files).
    """
    if len(parts) == 1 and parts[0]["name"] == "body":
        try:
            return json.loads(parts[0]["body"]), []
        except (json.JSONDecodeError, TypeError):
            text = parts[0]["body"].decode("utf-8", errors="replace")
            return {"content": text[:2000]}, []

    payload = {}
    remaining: list[dict] = []
    for part in parts:
        if part["name"] == "payload_json":
            payload = json.loads(part["body"].decode("utf-8"))
        else:
            remaining.append(part)

    if not payload:
        log.warning("No payload_json part found in multipart body")
    return payload, remaining


def _rebuild_multipart_from_parts(parts: list[dict], boundary: str, modified_payload: dict) -> bytes:
    """Rebuild a multipart body by prepending a ``payload_json`` part with
    *modified_payload* to *parts* (which should already exclude payload_json)."""
    serialized = json.dumps(modified_payload).encode("utf-8")

    # Find the original payload_json headers from a multipart parse to use as a template.
    # Since _extract_payload_json strips it, we reconstruct a standard header.
    payload_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="payload_json"\r\n'
        f"Content-Type: application/json\r\n"
        f"\r\n"
    ).encode()

    new_parts: list[bytes] = [payload_header + serialized]
    for part in parts:
        header = f"--{boundary}\r\n{part['headers']}\r\n\r\n".encode()
        new_parts.append(header + part["body"])

    new_parts.append(f"--{boundary}--\r\n".encode())
    return b"\r\n".join(new_parts)


def _forward(discord_url: str, payload: dict) -> tuple[int, dict]:
    """POST *payload* as JSON to a Discord webhook URL."""
    try:
        resp = requests.post(discord_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            log.info("→ Forwarded to Discord: %d", resp.status_code)
            return resp.status_code, {}
        log.error("→ Discord rejected %d: %s", resp.status_code, resp.text)
        return resp.status_code, resp.json() if resp.text else {}
    except requests.RequestException as exc:
        log.exception("→ Could not reach Discord: %s", exc)
        return 502, {"error": str(exc)}


def _forward_multipart(discord_url: str, raw_body: bytes, content_type: str) -> tuple[int, dict]:
    """POST raw multipart/form-data body to a Discord webhook URL."""
    try:
        resp = requests.post(
            discord_url,
            data=raw_body,
            headers={"Content-Type": content_type},
            timeout=30,
        )
        if resp.status_code in (200, 204):
            log.info("→ Forwarded multipart to Discord: %d (%d bytes)", resp.status_code, len(raw_body))
            return resp.status_code, {}
        log.error("→ Discord rejected %d: %s", resp.status_code, resp.text)
        return resp.status_code, resp.json() if resp.text else {}
    except requests.RequestException as exc:
        log.exception("→ Could not reach Discord: %s", exc)
        return 502, {"error": str(exc)}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/hook", methods=["POST"])
def hook():
    """Receive any webhook, route dynamically, and forward to Discord."""

    raw_body = request.get_data()
    content_type = request.content_type or ""

    # Parse the body exactly once
    parts = _parse_body(raw_body, content_type)
    payload, remaining_parts = _extract_payload_json(parts)
    headers = dict(request.headers)

    log.info("← Received webhook (%d bytes)", len(raw_body))
    log.debug("  Headers: %s", headers)
    log.info("  Payload keys: %s", list(payload.keys()))
    log.info("  Payload preview: %s", json.dumps(payload, indent=2)[:500])

    # --- Try each registered handler in priority order ---
    for prio, fn in HANDLERS:
        try:
            result = fn(payload, headers)
        except Exception as exc:
            log.exception("Handler %s crashed: %s", fn.__name__, exc)
            continue

        if result is None:
            continue

        # Unpack (discord_url, discord_payload)
        if not isinstance(result, tuple) or len(result) != 2:
            log.error(
                "Handler %s returned %r — expected (url, payload) tuple",
                fn.__name__,
                result,
            )
            continue

        target_url, discord_payload = result
        log.info("  Routed by %s → %s", fn.__name__, _redact_url(target_url))
        log.debug(
            "  Discord payload: %s", json.dumps(discord_payload, indent=2)[:500]
        )

        # Forward as multipart if the original request was multipart (preserves screenshots)
        if "multipart" in content_type:
            boundary = _extract_boundary(content_type)
            if boundary is None:
                log.error("Failed to extract boundary from Content-Type: %s", content_type)
                return None

            rebuilt = _rebuild_multipart_from_parts(remaining_parts, boundary, discord_payload)
            status, body = _forward_multipart(target_url, rebuilt, content_type)
        else:
            status, body = _forward(target_url, discord_payload)
        if status >= 400:
            return jsonify(body), status
        return jsonify({"status": "forwarded", "discord_status": status})

    # --- No handler matched ---
    log.warning("No handler matched the incoming webhook")
    return jsonify({"error": "no handler matched the webhook payload"}), 422


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "handlers": len(HANDLERS)})


# ---------------------------------------------------------------------------
# Built-in handlers
# ---------------------------------------------------------------------------


@handler(priority=90)
def dink(payload: dict, headers: dict):
    """Route DinkPlugin OSRS notifications by type. """
    notification_type: str = payload.get("type", "")
    config = _load_dink_config()
    url = config.get(notification_type, config.get('DEFAULT'))
    if url is None:
        log.error("  Error processing config for %s", notification_type)
        return None

    log.info("  DinkPlugin type=%s → %s", notification_type, _redact_url(url))

    for dink_handler in _DINK_HANDLERS:
        new_payload = dink_handler(payload)
        if new_payload is None:
            return None

        payload = new_payload


    return url, payload


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------


def _redact_url(url: str) -> str:
    """Show only the first ~35 chars of a Discord webhook URL."""
    return url[:35] + "..." if len(url) > 35 else url


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(
        "Registered %d handler(s): %s",
        len(HANDLERS),
        [fn.__name__ for _, fn in HANDLERS],
    )

    port = int(os.environ.get("PORT", 5000))
    log.info("Starting dink-proxy on port %d", port)
    app.run(host="0.0.0.0", port=port)
