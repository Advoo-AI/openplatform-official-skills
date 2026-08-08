---
name: skill-auth
description: Authorize Advoo OpenPlatform through browser-based PKCE after another official Skill reports the exact message “Advoo OpenPlatform 授权无效”. Use only for missing, rejected, or expired OpenPlatform credentials, then retry the interrupted operation once.
---

# OpenPlatform Authorization

Use this Skill only after another official Skill returns:

```text
Advoo OpenPlatform 授权无效
```

## Workflow

1. Preserve the interrupted command and its arguments.
2. Resolve this Skill's own `scripts/auth.py` file.
3. Select Python 3: use `python3` on macOS and `py -3` on Windows.
4. Start authorization:

   ```text
   <python> <auth.py> login
   ```

5. Immediately show the exact `Terminal confirmation code: XXXX` value to the user and tell them to enter it on the Advoo page. Keep the process running for the localhost callback.
6. After authorization succeeds, retry the preserved business command exactly once.

The authorization page uses the application name `Advoo Open Skills`. The requested credential expires no later than seven days after authorization.

The script stores local credentials at `~/Library/Application Support/Advoo/OpenPlatform/token.json` on macOS and `%LOCALAPPDATA%\Advoo\OpenPlatform\token.json` on Windows. `ADVOO_OPENPLATFORM_TOKEN_FILE` overrides this location.

When `ADVOO_OPENPLATFORM_TOKEN` is set, it is managed by the runtime and takes precedence over the local file. Do not start repeated browser logins; tell the user that the runtime credential must be updated or removed.

## Commands

```text
<python> <auth.py> login
<python> <auth.py> logout
<python> <auth.py> path
```

## Safety

- Never print, inspect, decode, summarize, or log the JWT or token file contents.
- The four-character terminal confirmation code is short-lived and may be shown to the user.
- Never place the Token in a URL, request body, command argument, or committed file.
- Do not use this Skill for ordinary API calls.
