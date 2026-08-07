#!/usr/bin/env python3

"""Perform Advoo OpenPlatform PKCE login without printing the resulting token."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


ORIGIN = "https://www.advoo.ai"
AUTHORIZE_URL = f"{ORIGIN}/oauth/authorize"
TOKEN_URL = f"{ORIGIN}/api/advoo/v1/openplatform/auth/oauth/token"
CLIENT_ID = "dotai-skill"
APP_NAME = "Social Post Query"
CONFIRMATION_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ACCESS_TOKEN_LIFETIME = timedelta(days=7)


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def pkce_pair() -> tuple[str, str]:
    verifier = base64url(secrets.token_bytes(64))
    challenge = base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def write_token(path: Path, token: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(token)
            output.write("\n")
    finally:
        os.chmod(path, 0o600)


def exchange_code(code: str, verifier: str, redirect_uri: str) -> str:
    payload = json.dumps(
        {
            "grantType": "authorization_code",
            "code": code,
            "clientId": CLIENT_ID,
            "redirectUri": redirect_uri,
            "codeVerifier": verifier,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Advoo-OpenPlatform-Skill/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"token exchange failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("token exchange request failed") from error

    if body.get("code") != 0:
        raise RuntimeError(body.get("msg") or "token exchange was rejected")
    result = body.get("result")
    token = result.get("access_token") if isinstance(result, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("token exchange response did not contain access_token")
    return token


def login(timeout_seconds: int) -> str:
    verifier, challenge = pkce_pair()
    state = base64url(secrets.token_bytes(32))
    confirmation_code = "".join(
        secrets.choice(CONFIRMATION_ALPHABET) for _ in range(4)
    )
    expire_at = (
        datetime.now(timezone.utc) + ACCESS_TOKEN_LIFETIME
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    callback: dict[str, Any] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_error(404)
                return
            values = urllib.parse.parse_qs(parsed.query)
            callback["state"] = values.get("state", [""])[0]
            callback["code"] = values.get("code", [""])[0]
            callback["error"] = values.get("error", [""])[0]
            message = (
                "Authorization received. You may close this window."
                if callback["code"]
                else "Authorization was not completed. You may close this window."
            )
            body = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>Advoo authorization</title>"
                f"<p>{message}</p>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    server.timeout = 1
    redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"
    query = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "confirmation_code": confirmation_code,
            "app_name": APP_NAME,
            "expireAt": expire_at,
        }
    )
    authorization_url = f"{AUTHORIZE_URL}?{query}"

    print(
        "Browser authorization is required. Complete the Advoo page to continue.",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"Terminal confirmation code: {confirmation_code}",
        file=sys.stderr,
        flush=True,
    )
    if not webbrowser.open(authorization_url):
        print(f"Open this URL in a browser: {authorization_url}", file=sys.stderr)

    deadline = time.monotonic() + timeout_seconds
    try:
        while not callback and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()

    if not callback:
        raise RuntimeError("authorization timed out")
    if callback.get("error"):
        raise RuntimeError("authorization was denied")
    if not hmac.compare_digest(str(callback.get("state", "")), state):
        raise RuntimeError("authorization state mismatch")
    code = callback.get("code")
    if not isinstance(code, str) or not code:
        raise RuntimeError("authorization callback did not contain a code")
    return exchange_code(code, verifier, redirect_uri)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        token = login(args.timeout)
        write_token(args.token_file, token)
        return 0
    except Exception as error:
        print(f"Advoo authorization failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
