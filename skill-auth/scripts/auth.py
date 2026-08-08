#!/usr/bin/env python3

"""Authorize official Advoo Skills through browser-based PKCE."""

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


ORIGIN = "https://open.advoo.ai"
AUTHORIZE_URL = "https://www.advoo.ai/oauth/authorize"
TOKEN_URL = f"{ORIGIN}/oauth/token"
CLIENT_ID = "dotai-skill"
APPLICATION_NAME = "Advoo Open Skills"
TOKEN_ENV = "ADVOO_OPENPLATFORM_TOKEN"
TOKEN_FILE_ENV = "ADVOO_OPENPLATFORM_TOKEN_FILE"
CONFIRMATION_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ACCESS_TOKEN_LIFETIME = timedelta(days=7)


class CommandError(RuntimeError):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def default_token_file() -> Path:
    override = os.environ.get(TOKEN_FILE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Advoo" / "OpenPlatform" / "token.json"
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "Advoo" / "OpenPlatform" / "token.json"
    config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "advoo" / "openplatform" / "token.json"


def write_token(path: Path, token: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    payload = json.dumps(
        {
            "access_token": token,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        separators=(",", ":"),
    )
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(payload)
            output.write("\n")
        os.replace(temporary, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def pkce_pair() -> tuple[str, str]:
    verifier = base64url(secrets.token_bytes(64))
    challenge = base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


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


def browser_login(timeout_seconds: int, app_name: str) -> str:
    verifier, challenge = pkce_pair()
    state = base64url(secrets.token_bytes(32))
    confirmation_code = "".join(secrets.choice(CONFIRMATION_ALPHABET) for _ in range(4))
    expire_at = (datetime.now(timezone.utc) + ACCESS_TOKEN_LIFETIME).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    callback: dict[str, str] = {}

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
                "<!doctype html><meta charset='utf-8'><title>Advoo authorization</title>"
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
    authorization_query = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "confirmation_code": confirmation_code,
            "app_name": app_name,
            "expireAt": expire_at,
        }
    )
    authorization_url = f"{AUTHORIZE_URL}?{authorization_query}"
    print("Browser authorization is required. Complete the Advoo page to continue.", file=sys.stderr)
    print(f"Terminal confirmation code: {confirmation_code}", file=sys.stderr, flush=True)
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
    if not hmac.compare_digest(callback.get("state", ""), state):
        raise RuntimeError("authorization state mismatch")
    code = callback.get("code", "")
    if not code:
        raise RuntimeError("authorization callback did not contain a code")
    return exchange_code(code, verifier, redirect_uri)


def clean_app_name(value: str) -> str:
    return value.strip()[:80] or APPLICATION_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, default=default_token_file())
    subparsers = parser.add_subparsers(dest="command", required=True)
    login = subparsers.add_parser("login", help="authorize in a browser and save a token")
    login.add_argument("--timeout", type=int, default=180)
    login.add_argument("--app-name", default=APPLICATION_NAME)
    subparsers.add_parser("logout", help="delete the saved local credential")
    subparsers.add_parser("path", help="show the credential path without reading it")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    path = args.token_file.expanduser()
    try:
        if args.command == "path":
            print(path)
            return 0
        if args.command == "logout":
            try:
                path.unlink()
                print("Saved Advoo credential removed.", file=sys.stderr)
            except FileNotFoundError:
                print("No saved Advoo credential found.", file=sys.stderr)
            if os.environ.get(TOKEN_ENV, "").strip():
                print(f"{TOKEN_ENV} remains set and still takes precedence.", file=sys.stderr)
            return 0
        if os.environ.get(TOKEN_ENV, "").strip():
            raise CommandError(
                f"{TOKEN_ENV} is managed by the runtime; update or remove it before local authorization.",
                4,
            )
        if args.timeout <= 0:
            raise ValueError("timeout must be positive")
        token = browser_login(args.timeout, clean_app_name(args.app_name))
        write_token(path, token)
        print(f"Advoo authorization completed. Credential saved to {path}.", file=sys.stderr)
        return 0
    except CommandError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
