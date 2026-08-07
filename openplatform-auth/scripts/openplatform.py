#!/usr/bin/env python3

"""Authorize and call Advoo OpenPlatform without exposing access tokens."""

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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional


ORIGIN = "https://www.advoo.ai"
AUTHORIZE_URL = f"{ORIGIN}/oauth/authorize"
TOKEN_URL = f"{ORIGIN}/api/advoo/v1/openplatform/auth/oauth/token"
OPENPLATFORM_PATH_PREFIX = "/api/advoo/v1/openplatform/"
CLIENT_ID = "dotai-skill"
TOKEN_ENV = "ADVOO_OPENPLATFORM_TOKEN"
TOKEN_FILE_ENV = "ADVOO_OPENPLATFORM_TOKEN_FILE"
CONFIRMATION_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ACCESS_TOKEN_LIFETIME = timedelta(days=7)
AUTH_FAILURE_CODES = {1005, 9997}


@dataclass(frozen=True)
class Credential:
    token: str
    source: str


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        raise urllib.error.HTTPError(newurl, code, "redirect rejected", headers, fp)


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
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "advoo" / "openplatform" / "token.json"


def read_saved_token(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if not value:
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        # Accept the original plain-text token format for a smooth upgrade.
        return value
    token = payload.get("access_token") if isinstance(payload, dict) else None
    return token.strip() if isinstance(token, str) and token.strip() else None


def load_credential(path: Path) -> Optional[Credential]:
    environment_token = os.environ.get(TOKEN_ENV, "").strip()
    if environment_token:
        return Credential(environment_token, "environment")
    saved_token = read_saved_token(path)
    if saved_token:
        return Credential(saved_token, "file")
    return None


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


def delete_saved_token(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


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
            body = ("<!doctype html><meta charset='utf-8'><title>Advoo authorization</title>"
                    f"<p>{message}</p>").encode("utf-8")
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
    print("Browser authorization is required. Complete the Advoo page to continue.",
          file=sys.stderr, flush=True)
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


def authorize_and_save(path: Path, timeout: int, app_name: str) -> Credential:
    token = browser_login(timeout, app_name)
    write_token(path, token)
    print(f"Advoo authorization completed. Credential saved to {path}.", file=sys.stderr)
    return Credential(token, "file")


def normalize_api_path(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError("request target must be a relative OpenPlatform API path")
    if not parsed.path.startswith(OPENPLATFORM_PATH_PREFIX):
        raise ValueError(f"request path must start with {OPENPLATFORM_PATH_PREFIX}")
    decoded_path = urllib.parse.unquote(parsed.path)
    if any(segment in (".", "..") for segment in decoded_path.split("/")):
        raise ValueError("request path must not contain traversal segments")
    if not decoded_path.startswith(OPENPLATFORM_PATH_PREFIX):
        raise ValueError("encoded request path must remain inside OpenPlatform")
    return urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, ""))


def perform_request(method: str, path: str, token: str, body: Optional[bytes],
                    timeout: int) -> tuple[int, bytes]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Advoo-OpenPlatform-Skill/1.0",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{ORIGIN}{path}", data=body, headers=headers, method=method
    )
    opener = urllib.request.build_opener(RejectRedirects())
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("OpenPlatform API request failed") from error


def is_auth_failure(status: int, body: bytes) -> bool:
    if status == 401:
        return True
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("code") in AUTH_FAILURE_CODES


def request_body(args: argparse.Namespace) -> Optional[bytes]:
    if args.json is not None:
        raw = args.json
    elif args.json_file is not None:
        raw = args.json_file.read_text(encoding="utf-8")
    elif args.stdin:
        raw = sys.stdin.read()
    else:
        return None
    json.loads(raw)
    return raw.encode("utf-8")


def emit_response(status: int, body: bytes) -> int:
    if body:
        sys.stdout.buffer.write(body)
        if not body.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
    if 200 <= status < 300:
        return 0
    print(f"OpenPlatform API returned HTTP {status}.", file=sys.stderr)
    return 1


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, default=default_token_file())
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="authorize in a browser and save a token")
    login_parser.add_argument("--timeout", type=positive_int, default=180)
    login_parser.add_argument("--app-name", default="Local Application")

    ensure_parser = subparsers.add_parser("ensure", help="ensure a usable credential exists")
    ensure_parser.add_argument("--timeout", type=positive_int, default=180)
    ensure_parser.add_argument("--app-name", default="Local Application")

    request_parser = subparsers.add_parser("request", help="call an OpenPlatform API endpoint")
    request_parser.add_argument("method", choices=("GET", "POST", "PUT", "PATCH", "DELETE"))
    request_parser.add_argument("path")
    request_parser.add_argument("--timeout", type=positive_int, default=60)
    request_parser.add_argument("--login-timeout", type=positive_int, default=180)
    request_parser.add_argument("--app-name", default="Local Application")
    request_parser.add_argument("--no-login", action="store_true")
    body_group = request_parser.add_mutually_exclusive_group()
    body_group.add_argument("--json")
    body_group.add_argument("--json-file", type=Path)
    body_group.add_argument("--stdin", action="store_true")

    subparsers.add_parser("logout", help="delete the saved local credential")
    return parser


def clean_app_name(value: str) -> str:
    return value.strip()[:80] or "Local Application"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    path = args.token_file.expanduser()
    try:
        if args.command == "logout":
            removed = delete_saved_token(path)
            print("Saved Advoo credential removed." if removed else "No saved Advoo credential found.",
                  file=sys.stderr)
            if os.environ.get(TOKEN_ENV, "").strip():
                print(f"{TOKEN_ENV} remains set and still takes precedence.", file=sys.stderr)
            return 0
        if args.command == "login":
            if os.environ.get(TOKEN_ENV, "").strip():
                print(f"{TOKEN_ENV} is already set and takes precedence; no local token was written.",
                      file=sys.stderr)
                return 0
            authorize_and_save(path, args.timeout, clean_app_name(args.app_name))
            return 0
        if args.command == "ensure":
            credential = load_credential(path)
            if credential is None:
                authorize_and_save(path, args.timeout, clean_app_name(args.app_name))
            else:
                print(f"Advoo credential is available from {credential.source}.", file=sys.stderr)
            return 0

        api_path = normalize_api_path(args.path)
        body = request_body(args)
        credential = load_credential(path)
        if credential is None:
            if args.no_login:
                print("Advoo credential is missing; browser authorization is required.", file=sys.stderr)
                return 3
            credential = authorize_and_save(
                path, args.login_timeout, clean_app_name(args.app_name)
            )
        status, response = perform_request(args.method, api_path, credential.token, body, args.timeout)
        if not is_auth_failure(status, response):
            return emit_response(status, response)
        if credential.source == "environment":
            print(f"The managed {TOKEN_ENV} credential is invalid or expired; update it in the runtime.",
                  file=sys.stderr)
            return 4
        delete_saved_token(path)
        if args.no_login:
            print("The saved credential is invalid or expired; browser authorization is required.",
                  file=sys.stderr)
            return 3
        credential = authorize_and_save(path, args.login_timeout, clean_app_name(args.app_name))
        status, response = perform_request(args.method, api_path, credential.token, body, args.timeout)
        if is_auth_failure(status, response):
            print("The newly authorized credential was rejected; the request was not retried again.",
                  file=sys.stderr)
            return 4
        return emit_response(status, response)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Advoo OpenPlatform error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
