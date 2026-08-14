#!/usr/bin/env python3

"""List verified recipients and send email through Advoo OpenPlatform."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


DEFAULT_BASE_URL = "https://open.advoo.ai"
BASE_URL_ENV = "ADVOO_OPENPLATFORM_BASE_URL"
ORIGIN = os.environ.get(BASE_URL_ENV, "").strip().rstrip("/") or DEFAULT_BASE_URL
TOKEN_ENV = "ADVOO_OPENPLATFORM_TOKEN"
TOKEN_FILE_ENV = "ADVOO_OPENPLATFORM_TOKEN_FILE"
AUTH_INVALID = "Advoo OpenPlatform 授权无效"
AUTH_FAILURE_CODES = {1005, 9997}
RECIPIENTS_PATH = "/v1/email/recipients"
MESSAGES_PATH = "/v1/email/messages"
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


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


def request_api(method: str, path: str, token: str, body: Optional[bytes],
                content_type: Optional[str], timeout: int) -> tuple[int, bytes]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Advoo-Email-Send-Skill/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(
        f"{ORIGIN}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.build_opener(RejectRedirects()).open(
            request, timeout=timeout
        ) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("OpenPlatform API request failed; delivery status is unknown") from error


def is_auth_failure(status: int, body: bytes) -> bool:
    if status == 401:
        return True
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("code") in AUTH_FAILURE_CODES


def authorized_request(token_file: Path, method: str, path: str,
                       body: Optional[bytes], content_type: Optional[str],
                       timeout: int) -> tuple[int, bytes]:
    token = read_token(token_file)
    if not token:
        raise CommandError(AUTH_INVALID, 3)
    status, response = request_api(method, path, token, body, content_type, timeout)
    if is_auth_failure(status, response):
        raise CommandError(AUTH_INVALID, 3)
    return status, response


def emit_response(status: int, body: bytes) -> int:
    if body:
        sys.stdout.buffer.write(body)
        if not body.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
    if not 200 <= status < 300:
        print(f"OpenPlatform API returned HTTP {status}.", file=sys.stderr)
        return 1
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("OpenPlatform API returned an invalid response.", file=sys.stderr)
        return 1
    if not isinstance(payload, dict) or payload.get("code") != 0:
        print("OpenPlatform API rejected the request.", file=sys.stderr)
        return 1
    return 0


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def content_from_args(args: argparse.Namespace) -> str:
    if args.content_file is not None:
        return args.content_file.expanduser().read_text(encoding="utf-8")
    if args.content_stdin:
        return sys.stdin.read()
    return args.content


def message_payload(args: argparse.Namespace) -> bytes:
    recipients = list(dict.fromkeys(value.strip().lower() for value in args.to))
    if any(not value for value in recipients):
        raise ValueError("recipient email must not be empty")
    subject = args.subject.strip()
    if not subject or len(subject) > 255:
        raise ValueError("subject is required and must not exceed 255 characters")
    payload = {
        "to": recipients,
        "subject": subject,
        "content": content_from_args(args),
        "contentType": args.content_type,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def load_attachments(paths: list[Path]) -> list[tuple[str, str, bytes]]:
    if len(paths) > MAX_ATTACHMENTS:
        raise ValueError("attachments must not exceed 10 files")
    loaded: list[tuple[str, str, bytes]] = []
    total = 0
    for supplied in paths:
        path = supplied.expanduser()
        try:
            size = path.stat().st_size
        except FileNotFoundError as error:
            raise ValueError(f"attachment does not exist: {path}") from error
        if not path.is_file():
            raise ValueError(f"attachment is not a file: {path}")
        if size <= 0:
            raise ValueError(f"attachment must not be empty: {path}")
        if size > MAX_ATTACHMENT_BYTES or total > MAX_ATTACHMENT_BYTES - size:
            raise ValueError("each attachment and total attachments must not exceed 20 MiB")
        name = path.name
        if len(name) > 255 or any(char in name for char in ("/", "\\", "\r", "\n", '"')):
            raise ValueError(f"invalid attachment filename: {name}")
        data = path.read_bytes()
        if len(data) != size:
            raise RuntimeError(f"attachment changed while being read: {path}")
        total += size
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        loaded.append((name, content_type, data))
    return loaded


def multipart_body(message: bytes, attachments: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = f"advoo-email-{secrets.token_hex(16)}"
    marker = boundary.encode("ascii")
    parts = [
        b"--" + marker + b"\r\n",
        b'Content-Disposition: form-data; name="message"\r\n',
        b"Content-Type: application/json; charset=utf-8\r\n\r\n",
        message,
        b"\r\n",
    ]
    for name, content_type, data in attachments:
        parts.extend((
            b"--" + marker + b"\r\n",
            f'Content-Disposition: form-data; name="attachments"; filename="{name}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
            data,
            b"\r\n",
        ))
    parts.extend((b"--" + marker + b"--\r\n",))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, default=default_token_file())
    subparsers = parser.add_subparsers(dest="command", required=True)
    recipients = subparsers.add_parser("recipients", help="list verified recipients")
    recipients.add_argument("--timeout", type=positive_int, default=60)
    send = subparsers.add_parser("send", help="send one email")
    send.add_argument("--to", action="append", required=True)
    send.add_argument("--subject", required=True)
    content = send.add_mutually_exclusive_group(required=True)
    content.add_argument("--content")
    content.add_argument("--content-file", type=Path)
    content.add_argument("--content-stdin", action="store_true")
    send.add_argument("--content-type", choices=("text/plain", "text/html"), required=True)
    send.add_argument("--attachment", action="append", type=Path, default=[])
    send.add_argument("--timeout", type=positive_int, default=120)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token_file = args.token_file.expanduser()
    try:
        if args.command == "recipients":
            status, response = authorized_request(
                token_file, "GET", RECIPIENTS_PATH, None, None, args.timeout
            )
            return emit_response(status, response)
        message = message_payload(args)
        attachments = load_attachments(args.attachment)
        if attachments:
            body, content_type = multipart_body(message, attachments)
        else:
            body, content_type = message, "application/json"
        status, response = authorized_request(
            token_file, "POST", MESSAGES_PATH, body, content_type, args.timeout
        )
        return emit_response(status, response)
    except CommandError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
