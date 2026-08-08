#!/usr/bin/env python3

"""Generate or edit images through Advoo OpenPlatform."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


ORIGIN = "https://open.advoo.ai"
TOKEN_ENV = "ADVOO_OPENPLATFORM_TOKEN"
TOKEN_FILE_ENV = "ADVOO_OPENPLATFORM_TOKEN_FILE"
AUTH_INVALID = "Advoo OpenPlatform 授权无效"
AUTH_FAILURE_CODES = {1005, 9997}
MODELS_PATH = "/v1/image-edit/models"
EDIT_PATH = "/v1/image-edit"
TEMP_UPLOAD_PATH = "/v1/files/temp-upload-url"
MAX_REFERENCE_IMAGES = 4
MAX_REFERENCE_IMAGE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class Credential:
    token: str


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


def credential(path: Path) -> Credential:
    token = read_token(path)
    if not token:
        raise CommandError(AUTH_INVALID, 3)
    return Credential(token)


def request_api(method: str, path: str, token: str, body: Optional[bytes], timeout: int) -> tuple[int, bytes]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Advoo-Image-Edit-Skill/1.0",
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
    current = credential(token_file)
    status, response = request_api(method, path, current.token, body, timeout)
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


def read_limited(stream: Any, limit: int) -> bytes:
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("reference image must not exceed 20 MB")
    if not data:
        raise ValueError("reference image must not be empty")
    return data


def detect_image_content_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("reference image must be PNG, JPEG, or WebP")


def load_reference_image(value: str, timeout: int) -> tuple[bytes, str]:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() in ("http", "https"):
        request = urllib.request.Request(
            value,
            headers={"Accept": "image/*", "User-Agent": "Advoo-Image-Edit-Skill/1.0"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_REFERENCE_IMAGE_BYTES:
                    raise ValueError("reference image must not exceed 20 MB")
                data = read_limited(response, MAX_REFERENCE_IMAGE_BYTES)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"reference image download failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError("reference image download failed") from error
    else:
        if "://" in value:
            raise ValueError("reference image URL must use http or https")
        path = Path(value).expanduser()
        try:
            if path.stat().st_size > MAX_REFERENCE_IMAGE_BYTES:
                raise ValueError("reference image must not exceed 20 MB")
            with path.open("rb") as source:
                data = read_limited(source, MAX_REFERENCE_IMAGE_BYTES)
        except FileNotFoundError as error:
            raise ValueError(f"reference image does not exist: {path}") from error
    return data, detect_image_content_type(data)


def success_result(status: int, body: bytes, operation: str) -> dict[str, Any]:
    if not 200 <= status < 300:
        raise RuntimeError(f"{operation} failed with HTTP {status}")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError(f"{operation} returned an invalid response") from error
    if not isinstance(payload, dict) or payload.get("code") != 0:
        message = payload.get("msg") if isinstance(payload, dict) else None
        raise RuntimeError(message or f"{operation} was rejected")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"{operation} response did not contain a result")
    return result


def upload_reference(token_file: Path, data: bytes, content_type: str,
                     timeout: int) -> str:
    body = json.dumps({"contentType": content_type}, separators=(",", ":")).encode("utf-8")
    status, response = authorized_request(token_file, "POST", TEMP_UPLOAD_PATH, body, timeout)
    result = success_result(status, response, "temporary image upload initialization")
    upload_url = result.get("url")
    file_key = result.get("fileKey")
    if not isinstance(upload_url, str) or not isinstance(file_key, str):
        raise RuntimeError("temporary image upload response is incomplete")
    parsed_url = urllib.parse.urlsplit(upload_url)
    if parsed_url.scheme.lower() != "https" or not parsed_url.netloc:
        raise RuntimeError("temporary image upload URL is not secure")
    request = urllib.request.Request(
        upload_url,
        data=data,
        headers={"Content-Type": content_type, "Content-Length": str(len(data))},
        method="PUT",
    )
    try:
        with urllib.request.build_opener(RejectRedirects()).open(request, timeout=timeout) as uploaded:
            if not 200 <= uploaded.status < 300:
                raise RuntimeError(f"temporary image upload failed with HTTP {uploaded.status}")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"temporary image upload failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("temporary image upload failed") from error
    return file_key


def edit_body(args: argparse.Namespace, image_keys: list[str]) -> bytes:
    prompt = sys.stdin.read() if args.prompt_stdin else args.prompt
    prompt = prompt.strip() if isinstance(prompt, str) else ""
    if not prompt:
        raise ValueError("image prompt must not be empty")
    payload: dict[str, Any] = {"model": args.model, "prompt": prompt}
    if image_keys:
        payload["imageOssKeys"] = image_keys
    if args.resolution:
        payload["resolution"] = args.resolution
    if args.aspect_ratio:
        payload["aspectRatio"] = args.aspect_ratio
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, default=default_token_file())
    subparsers = parser.add_subparsers(dest="command", required=True)
    models = subparsers.add_parser("models", help="list supported models and credit prices")
    models.add_argument("--timeout", type=positive_int, default=60)
    edit = subparsers.add_parser("edit", help="generate or edit one image")
    edit.add_argument("--model", required=True)
    prompt = edit.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt")
    prompt.add_argument("--prompt-stdin", action="store_true")
    edit.add_argument("--resolution")
    edit.add_argument("--aspect-ratio")
    edit.add_argument("--image", action="append")
    edit.add_argument("--timeout", type=positive_int, default=180)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token_file = args.token_file.expanduser()
    try:
        if args.command == "models":
            status, response = authorized_request(token_file, "GET", MODELS_PATH, None, args.timeout)
            return emit_response(status, response)
        images = args.image or []
        if len(images) > MAX_REFERENCE_IMAGES:
            raise ValueError("at most 4 reference images are allowed")
        image_keys = []
        for value in images:
            data, content_type = load_reference_image(value, args.timeout)
            image_keys.append(upload_reference(token_file, data, content_type, args.timeout))
        body = edit_body(args, image_keys)
        status, response = authorized_request(token_file, "POST", EDIT_PATH, body, args.timeout)
        return emit_response(status, response)
    except CommandError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
