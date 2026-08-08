#!/usr/bin/env python3

"""Query connected social channels and posts through Advoo OpenPlatform."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


ORIGIN = "https://open.advoo.ai"
TOKEN_ENV = "ADVOO_OPENPLATFORM_TOKEN"
TOKEN_FILE_ENV = "ADVOO_OPENPLATFORM_TOKEN_FILE"
AUTH_INVALID = "Advoo OpenPlatform 授权无效"
AUTH_FAILURE_CODES = {1005, 9997}
PLATFORMS = ("facebook", "instagram", "linkedin", "threads")


class CommandError(RuntimeError):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


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
    config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "advoo" / "openplatform" / "token.json"


def read_token(path: Path) -> Optional[str]:
    environment = os.environ.get(TOKEN_ENV, "").strip()
    if environment:
        return environment
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    token = payload.get("access_token") if isinstance(payload, dict) else None
    return token.strip() if isinstance(token, str) and token.strip() else None


def request_api(method: str, path: str, token: str, body: Optional[bytes], timeout: int) -> tuple[int, bytes]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Advoo-Social-Post-Query-Skill/1.0",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{ORIGIN}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(RejectRedirects()).open(request, timeout=timeout) as response:
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


def authorized_request(token_file: Path, method: str, path: str,
                       body: Optional[bytes], timeout: int) -> tuple[int, bytes]:
    token = read_token(token_file)
    if not token:
        raise CommandError(AUTH_INVALID, 3)
    status, response = request_api(method, path, token, body, timeout)
    if is_auth_failure(status, response):
        raise CommandError(AUTH_INVALID, 3)
    return status, response


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


def post_limit(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return number


def parse_iso8601(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("since and until must be ISO-8601 timestamps") from error
    if parsed.tzinfo is None:
        raise ValueError("since and until must include a timezone")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, default=default_token_file())
    subparsers = parser.add_subparsers(dest="command", required=True)
    channels = subparsers.add_parser("channels", help="list connected channels")
    channels.add_argument("--platform", choices=PLATFORMS, required=True)
    channels.add_argument("--timeout", type=positive_int, default=60)
    posts = subparsers.add_parser("posts", help="query posts")
    posts.add_argument("--platform", choices=PLATFORMS, required=True)
    posts.add_argument("--channel-id", required=True)
    posts.add_argument("--since", required=True)
    posts.add_argument("--until", required=True)
    posts.add_argument("--limit", type=post_limit, default=50)
    posts.add_argument("--cursor")
    posts.add_argument("--timeout", type=positive_int, default=60)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token_file = args.token_file.expanduser()
    try:
        if args.command == "channels":
            path = f"/v1/social/{args.platform}/channels"
            status, response = authorized_request(token_file, "GET", path, None, args.timeout)
            return emit_response(status, response)
        since = parse_iso8601(args.since)
        until = parse_iso8601(args.until)
        if until <= since:
            raise ValueError("until must be later than since")
        if until - since > timedelta(days=366):
            raise ValueError("social post time range must not exceed 366 days")
        payload = {
            "channelId": args.channel_id,
            "since": args.since,
            "until": args.until,
            "limit": args.limit,
            "cursor": args.cursor,
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        path = f"/v1/social/{args.platform}/posts/query"
        status, response = authorized_request(token_file, "POST", path, body, args.timeout)
        return emit_response(status, response)
    except CommandError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
