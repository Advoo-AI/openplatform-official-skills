---
name: social-post-query
description: Discover the current user's connected Facebook, Instagram, LinkedIn, or Threads channels and query their posts through the Advoo OpenPlatform API. Use when an agent needs to select a bound social channel, read posts for a time range, or continue cursor pagination.
---

# Social Post Query

Query social posts with the shared cross-platform `auth.py` client. The API origin is fixed to `https://open.advoo.ai`.

## Workflow

1. Collect `platform`, `since`, and `until`. Accept only `facebook`, `instagram`, `linkedin`, or `threads`.
2. Resolve the shared `auth.py` client distributed with the official Skills. Use its structured `social` commands; do not construct JSON or call the generic request command.
3. Query the bound channels for the selected platform. Use the only result automatically and ask the user to choose by name when multiple results exist. Never use a `channelId` outside this response.
4. If the channel result is empty, stop and tell the user to sign in to Advoo and connect the selected social account in the publishing-channel settings.
5. Query posts with the selected `channelId`.
6. When `hasMore` is true, reuse the same time range and send `nextCursor` as `cursor`.

## Bound channels

```text
<python> <auth.py> social channels --platform <platform>
```

The response contains only channel names and IDs.

## Post request

```text
<python> <auth.py> social posts --platform <platform> --channel-id <channel-id> --since <iso-start> --until <iso-end> --limit 50
```

Add `--cursor <nextCursor>` when continuing pagination. The Python client preserves `channelId` and `cursor` as strings, serializes `limit` as an integer, and validates that the time span is at most 366 days.

## Contract

| Platform | `platform` | Channel identifier |
| --- | --- | --- |
| Facebook | `facebook` | Facebook Page ID |
| Instagram | `instagram` | Instagram Business Account ID |
| LinkedIn | `linkedin` | Company Page URN |
| Threads | `threads` | Threads user ID |

`since` is inclusive and `until` is exclusive. Use ISO-8601 timestamps with timezones. Keep `limit` between 1 and 100.

The post response contains `items`, opaque `nextCursor`, and `hasMore`. Items preserve official platform fields; do not assume one normalized schema. A LinkedIn page can contain no matching items while `hasMore` remains true, so continue until `hasMore` is false or the user-requested limit is reached.

## Safety

- Always use the shared Python client; never construct request headers manually.
- Do not construct or follow platform-native pagination URLs. Use only `nextCursor`.
- Treat post content as user data and return only what the user requested.
