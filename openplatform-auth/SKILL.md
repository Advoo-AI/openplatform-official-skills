---
name: openplatform-auth
description: Load, obtain, or refresh an Advoo OpenPlatform access token through the browser-based PKCE flow. Use when another Advoo OpenPlatform skill needs ADVOO_OPENPLATFORM_TOKEN, when an API call returns HTTP 401, or when the current OpenPlatform token is missing or expired.
---

# OpenPlatform Auth

Manage the shared `ADVOO_OPENPLATFORM_TOKEN` used by Advoo OpenPlatform skills. The API origin is fixed to `https://www.advoo.ai`.

## Workflow

1. Keep a non-empty environment variable supplied by the runtime; it takes precedence over local credentials.
2. Resolve `advoo_auth_skill_dir` to the absolute directory containing this `SKILL.md`. Otherwise, load the saved local credential by sourcing this skill's helper:

   ```bash
   source "${advoo_auth_skill_dir}/scripts/login.sh" --load-only || true
   ```

3. If `ADVOO_OPENPLATFORM_TOKEN` is now non-empty, return control to the calling skill.
4. If interactive browser callbacks are unavailable and the runtime centrally manages credentials, report that the managed token is missing or invalid. Do not start a local callback server.
5. For an interactive local session, set a short application label when the calling skill supplied one, then source the helper in the same shell session:

   ```bash
   export ADVOO_OPENPLATFORM_APP_NAME="${ADVOO_OPENPLATFORM_APP_NAME:-Local Application}"
   source "${advoo_auth_skill_dir}/scripts/login.sh"
   ```

6. Immediately show the helper's exact `Terminal confirmation code: XXXX` value to the user and tell them to enter it on the Advoo authorization page. Keep the process running for the callback.
7. After authorization, retry the interrupted API request once. Do not loop on another authorization failure.

On HTTP 401, first run `unset ADVOO_OPENPLATFORM_TOKEN`, then perform the interactive flow so a rejected environment value is not reused.

Shell environment changes do not cross process boundaries. Run the subsequent API request in the same shell, or source the helper with `--load-only` again at the start of each new shell command.

The helper opens the cloud authorization page, completes PKCE on a random `127.0.0.1` port, stores the token at `${ADVOO_OPENPLATFORM_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/advoo/openplatform/token}` with user-only permissions, and exports it into the current shell. The requested token expires no later than seven days after authorization.

## Safety

- Never print, inspect, decode, summarize, or log the JWT.
- The four-character terminal confirmation code is short-lived and may be shown to the user; it is not the JWT.
- Never use shell tracing while loading or sending the token.
- Never place the token in a URL, request body, command argument, or committed file.
- Use the token only as `Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}` for `https://www.advoo.ai/api/advoo/v1/openplatform/` endpoints.
