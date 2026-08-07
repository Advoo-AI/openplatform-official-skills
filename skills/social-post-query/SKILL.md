---
name: social-post-query
description: Discover the current user's connected Facebook, Instagram, LinkedIn, or Threads channels and query their posts through the Advoo OpenPlatform API. Use when an agent needs to select a bound social channel, read posts for a time range, continue cursor pagination, or recover from a missing or invalid OpenPlatform token.
---

# Social Post Query

Query social posts with `curl`. The API origin is fixed to `https://www.advoo.ai`.

## Workflow

1. Collect `platform`, `since`, and `until`. Accept only `facebook`, `instagram`, `linkedin`, or `threads`.
2. Load a previously saved local credential when the environment variable is absent, then call the API immediately. A cloud-injected environment variable always takes precedence:

   ```bash
   source scripts/login.sh --load-only || true
   ```

3. If the variable is missing, HTTP status is `401`, or the response indicates an expired/unauthorized login, tell the user that browser authorization is required. On `401`, unset the rejected variable before continuing. A cloud runtime with a centrally injected token should report an invalid centrally managed token instead of starting an interactive login unless it supports a local browser callback.
4. In the same shell session, source the login helper and keep the process running while it waits for the browser callback:

   ```bash
   source scripts/login.sh
   ```

5. Read the helper's `Terminal confirmation code: XXXX` output and immediately show that exact four-character code to the user. Tell the user to enter it on the Advoo authorization page. The confirmation code is short-lived and may be shown; it is not the JWT.
6. Query the bound channels for the selected platform. Use the only result automatically, ask the user to choose by name when multiple results exist, and stop with reconnection guidance when the result is empty. Never use a `channelId` outside this response.
7. Query posts with the selected `channelId`. After a successful browser login, retry the interrupted API request once in that same shell session. Do not loop on authorization failure.
8. When `hasMore` is true, reuse the same time range and send `nextCursor` as `cursor`.

The login helper opens the cloud authorization page, prints a four-character terminal confirmation code, completes PKCE on a random `127.0.0.1` port, saves the token to `${ADVOO_OPENPLATFORM_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/advoo/openplatform/token}` with user-only permissions, and exports `ADVOO_OPENPLATFORM_TOKEN` into the current shell. A later shell loads it with `source scripts/login.sh --load-only`. The user must enter the same code on the authorization page. The requested token expires no later than seven days after authorization. Never print, inspect, summarize, or log the token.

## Bound channels

List channels already bound by the current user:

```bash
curl --silent --show-error --fail-with-body \
  --request GET \
  --url "https://www.advoo.ai/api/advoo/v1/openplatform/social/${platform}/channels" \
  --header "Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}"
```

The response contains only channel names and IDs. It never contains platform access tokens.

## Post request

Select the endpoint by platform:

```text
https://www.advoo.ai/api/advoo/v1/openplatform/social/{platform}/posts/query
```

Call it with:

```bash
curl --silent --show-error --fail-with-body \
  --request POST \
  --url "https://www.advoo.ai/api/advoo/v1/openplatform/social/${platform}/posts/query" \
  --header "Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "${request_json}"
```

Build `request_json` as JSON, never by interpolating untrusted text into shell syntax:

```json
{
  "channelId": "123456789",
  "since": "2026-07-01T00:00:00Z",
  "until": "2026-08-01T00:00:00Z",
  "limit": 50,
  "cursor": null
}
```

Keep `limit` between 1 and 100 and the time span within 366 days. Read [references/api.md](references/api.md) when handling platform fields, pagination, or errors.

## Safety

- Read the JWT only from `ADVOO_OPENPLATFORM_TOKEN`.
- Never use `curl --verbose`, shell tracing, or commands that echo request headers.
- Never expose platform access tokens; DotAI resolves channel credentials server-side.
- Do not construct or follow platform-native pagination URLs. Use only `nextCursor`.
- Treat post content as user data and return only what the user requested.
