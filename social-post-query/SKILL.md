---
name: social-post-query
description: Discover the current user's connected Facebook, Instagram, LinkedIn, or Threads channels and query their posts through the Advoo OpenPlatform API. Use when an agent needs to select a bound social channel, read posts for a time range, or continue cursor pagination.
---

# Social Post Query

Query social posts with `curl`. The API origin is fixed to `https://www.advoo.ai`.

## Workflow

1. Collect `platform`, `since`, and `until`. Accept only `facebook`, `instagram`, `linkedin`, or `threads`.
2. Set `ADVOO_OPENPLATFORM_APP_NAME="Social Post Query"` and invoke `$openplatform-auth` to load `ADVOO_OPENPLATFORM_TOKEN`.
3. Query the bound channels for the selected platform. Use the only result automatically and ask the user to choose by name when multiple results exist. Never use a `channelId` outside this response.
4. If the channel result is empty, stop and tell the user to sign in to Advoo and reconnect the selected social account in the publishing-channel settings. Do not repeat OpenPlatform login because it cannot repair an expired platform binding.
5. Query posts with the selected `channelId`.
6. If an API request returns HTTP 401, unset the rejected token, invoke `$openplatform-auth`, and retry the interrupted request once. Do not loop on another authorization failure.
7. When `hasMore` is true, reuse the same time range and send `nextCursor` as `cursor`.

## Bound channels

```bash
curl --silent --show-error --fail-with-body \
  --request GET \
  --url "https://www.advoo.ai/api/advoo/v1/openplatform/social/${platform}/channels" \
  --header "Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}"
```

The response contains only channel names and IDs. It never contains platform access tokens.

## Post request

```bash
curl --silent --show-error --fail-with-body \
  --request POST \
  --url "https://www.advoo.ai/api/advoo/v1/openplatform/social/${platform}/posts/query" \
  --header "Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "${request_json}"
```

Build `request_json` with a JSON serializer, never by interpolating untrusted text into shell syntax:

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
- Never expose platform access tokens; Advoo resolves channel credentials server-side.
- Do not construct or follow platform-native pagination URLs. Use only `nextCursor`.
- Treat post content as user data and return only what the user requested.
