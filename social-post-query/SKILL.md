---
name: social-post-query
description: Discover the current user's connected Facebook, Instagram, LinkedIn, or Threads channels and query their posts through the Advoo OpenPlatform API. Use when an agent needs to select a bound social channel, read posts for a time range, or continue cursor pagination.
---

# Social Post Query

Query social posts with the shared cross-platform `openplatform.py` client. The API origin is fixed to `https://www.advoo.ai`.

## Workflow

1. Collect `platform`, `since`, and `until`. Accept only `facebook`, `instagram`, `linkedin`, or `threads`.
2. Resolve the shared `openplatform.py` client distributed with the official Skills and make requests with `--app-name "Social Post Query"`.
3. Query the bound channels for the selected platform. Use the only result automatically and ask the user to choose by name when multiple results exist. Never use a `channelId` outside this response.
4. If the channel result is empty, stop and tell the user to sign in to Advoo and connect the selected social account in the publishing-channel settings.
5. Query posts with the selected `channelId`.
6. When `hasMore` is true, reuse the same time range and send `nextCursor` as `cursor`.

## Bound channels

```text
<python> <openplatform.py> request GET "/api/advoo/v1/openplatform/social/<platform>/channels" --app-name "Social Post Query"
```

The response contains only channel names and IDs.

## Post request

```text
<python> <openplatform.py> request POST "/api/advoo/v1/openplatform/social/<platform>/posts/query" --app-name "Social Post Query" --json-file <request.json>
```

Create the temporary request file with a JSON serializer, never by interpolating untrusted text into shell syntax. Delete it after the request:

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

- Always use the shared Python client; never construct request headers manually.
- Do not construct or follow platform-native pagination URLs. Use only `nextCursor`.
- Treat post content as user data and return only what the user requested.
