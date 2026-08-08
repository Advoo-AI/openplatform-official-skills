---
name: skill-auth
description: Authorize Advoo OpenPlatform through a cross-platform Python helper using browser-based PKCE. Use this skill whenever an agent or skill encounters or reports “Advoo OpenPlatform 授权无效”, or when OpenPlatform authorization is missing, invalid, or expired.
---

# OpenPlatform Auth

Use the bundled Python helper for authorization and API requests. The API origin is fixed to `https://open.advoo.ai`; interactive authorization uses the official page at `https://www.advoo.ai/oauth/authorize`.

## Workflow

When another skill reports that Advoo OpenPlatform authorization is missing, invalid, or expired, immediately perform this workflow. Do not ask the user to manually locate or copy a token.

1. Resolve `auth.py` to the absolute path under this skill's `scripts` directory.
2. Select an installed Python 3 launcher: prefer `python3` on macOS and `py -3` on Windows, falling back to `python` only when it is Python 3.
3. Retry the interrupted request through the helper. The helper uses the official `Advoo Open Skills` application label:

   ```text
   <python> <auth.py> request GET /v1/...
   ```

4. Let Python load the credential, open browser authorization when needed, and retry a rejected local credential once. Do not duplicate this control flow in the calling skill.
5. When authorization starts, immediately show the helper's exact `Terminal confirmation code: XXXX` value to the user and tell them to enter it on the Advoo authorization page. Keep the process running for the callback.

The helper resolves credentials in this order:

   - Non-empty `ADVOO_OPENPLATFORM_TOKEN` environment variable.
   - The OS-specific local token file.
   - Interactive browser authorization when neither exists.

When a managed `ADVOO_OPENPLATFORM_TOKEN` is present but rejected, browser login cannot override it. Tell the user to update or remove that environment variable in the runtime instead of repeatedly opening authorization.

Use `--json-file <path>` or `--stdin` for JSON request bodies. Do not place sensitive or untrusted content directly in shell syntax. The helper writes API response bodies to standard output and diagnostics to standard error.

Prefer structured business commands when available. They validate typed arguments and build request JSON internally:

```text
<python> <auth.py> social channels --platform facebook
<python> <auth.py> social posts --platform facebook --channel-id <id> --since <start> --until <end> --limit 50
<python> <auth.py> image models
<python> <auth.py> image edit --model <model> --prompt <prompt> [--image <path-or-url>]...
```

Explicit commands:

```text
<python> <auth.py> login
<python> <auth.py> ensure
<python> <auth.py> request GET /v1/...
<python> <auth.py> logout
```

The helper stores local credentials at `~/Library/Application Support/Advoo/OpenPlatform/token.json` on macOS and `%LOCALAPPDATA%\Advoo\OpenPlatform\token.json` on Windows. `ADVOO_OPENPLATFORM_TOKEN_FILE` overrides the file path. The requested token expires no later than seven days after authorization.

Use `Advoo Open Skills` as the authorization-page application name for every official Skill workflow.

## Safety

- Never print, inspect, decode, summarize, or log the JWT or token file contents.
- The four-character terminal confirmation code is short-lived and may be shown to the user; it is not the JWT.
- Never place the token in a URL, request body, command argument, or committed file.
- Do not bypass the helper to call a different origin or a path outside `/v1/`.
