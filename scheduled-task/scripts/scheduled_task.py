#!/usr/bin/env python3
"""Manage Advoo scheduled tasks through OpenPlatform."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


DEFAULT_BASE_URL = "https://open.advoo.ai"
ORIGIN = os.environ.get("ADVOO_OPENPLATFORM_BASE_URL", "").strip().rstrip("/") or DEFAULT_BASE_URL
AUTH_INVALID = "Advoo OpenPlatform 授权无效"


class CommandError(RuntimeError):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        raise urllib.error.HTTPError(newurl, code, "redirect rejected", headers, fp)


def default_token_file() -> Path:
    override = os.environ.get("ADVOO_OPENPLATFORM_TOKEN_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Advoo" / "OpenPlatform" / "token.json"
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA", "").strip()
        return (Path(root) if root else Path.home() / "AppData" / "Local") / "Advoo" / "OpenPlatform" / "token.json"
    root = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return (Path(root) if root else Path.home() / ".config") / "advoo" / "openplatform" / "token.json"


def read_token(path: Path) -> Optional[str]:
    value = os.environ.get("ADVOO_OPENPLATFORM_TOKEN", "").strip()
    if value:
        return value
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw or None
    value = payload.get("access_token") if isinstance(payload, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def request(token_file: Path, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    token = read_token(token_file)
    if not token:
        raise CommandError(AUTH_INVALID, 3)
    body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "Advoo-Scheduled-Task-Skill/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{ORIGIN}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(RejectRedirects()).open(req, timeout=60) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("OpenPlatform API request failed; operation status is unknown") from error
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError(f"OpenPlatform returned HTTP {status} with an invalid response") from error
    if status == 401 or (isinstance(result, dict) and result.get("code") in {1005, 9997}):
        raise CommandError(AUTH_INVALID, 3)
    if not 200 <= status < 300 or not isinstance(result, dict) or result.get("code") != 0:
        raise RuntimeError(result.get("msg", "OpenPlatform rejected the request") if isinstance(result, dict) else "OpenPlatform rejected the request")
    return result


def task_payload(args: argparse.Namespace, partial: bool = False) -> dict[str, Any]:
    values = {
        "employeeId": getattr(args, "employee_id", None), "name": getattr(args, "name", None),
        "prompt": getattr(args, "prompt", None), "scheduleType": getattr(args, "schedule", None),
        "runAt": getattr(args, "run_at", None), "intervalType": getattr(args, "interval", None),
        "endAt": getattr(args, "end_at", None), "timezone": getattr(args, "timezone", None),
        "project": getattr(args, "project", None), "projectEntryId": getattr(args, "project_entry_id", None),
    }
    if not partial:
        return {key: value for key, value in values.items() if value is not None}
    return {key: value for key, value in values.items() if value is not None and key != "employeeId"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, default=default_token_file())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("employees", help="list available digital employees")
    listing = commands.add_parser("list", help="list scheduled tasks")
    listing.add_argument("--page", type=int, default=1)
    listing.add_argument("--page-size", type=int, default=50)
    create = commands.add_parser("create", help="create a scheduled task")
    create.add_argument("--employee-id", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--prompt", required=True)
    create.add_argument("--schedule", choices=("once", "recurring"), required=True)
    create.add_argument("--run-at", required=True)
    create.add_argument("--interval", choices=("12h", "24h", "weekly"))
    create.add_argument("--end-at")
    create.add_argument("--timezone", required=True)
    create.add_argument("--project", default="")
    create.add_argument("--project-entry-id", default="")
    update = commands.add_parser("update", help="update a scheduled task")
    update.add_argument("task_id")
    update.add_argument("--name")
    update.add_argument("--prompt")
    update.add_argument("--run-at")
    update.add_argument("--interval", choices=("12h", "24h", "weekly"))
    update.add_argument("--end-at")
    update.add_argument("--timezone")
    update.add_argument("--project")
    update.add_argument("--project-entry-id")
    for name in ("pause", "resume", "delete"):
        command = commands.add_parser(name, help=f"{name} a scheduled task")
        command.add_argument("task_id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "employees":
        result = request(args.token_file, "GET", "/v1/employees")
    elif args.command == "list":
        query = urllib.parse.urlencode({"page": args.page, "pageSize": args.page_size})
        result = request(args.token_file, "GET", f"/v1/tasks?{query}")
    elif args.command == "create":
        if args.schedule == "recurring" and not args.interval:
            raise ValueError("--interval is required for recurring tasks")
        result = request(args.token_file, "POST", "/v1/tasks", task_payload(args))
    elif args.command == "update":
        result = request(args.token_file, "PUT", f"/v1/tasks/{urllib.parse.quote(args.task_id, safe='')}", task_payload(args, True))
    else:
        suffix = "" if args.command == "delete" else f"/{args.command}"
        method = "DELETE" if args.command == "delete" else "POST"
        result = request(args.token_file, method, f"/v1/tasks/{urllib.parse.quote(args.task_id, safe='')}{suffix}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CommandError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(error.exit_code) from error
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
