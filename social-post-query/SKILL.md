---
name: social-post-query
description: Discover connected Facebook, Instagram, LinkedIn, or Threads channels and query their posts through Advoo OpenPlatform. Use to select a bound social channel, read posts for a time range, or continue cursor pagination.
---

# Social Post Query

Use this Skill's own `scripts/social_post_query.py`. It is self-contained and calls `https://open.advoo.ai` with an existing environment or local-file credential.

## Workflow

1. Collect `platform`, `since`, and `until`. Accept only `facebook`, `instagram`, `linkedin`, or `threads`.
2. Resolve `scripts/social_post_query.py` under this Skill and select Python 3: use `python3` on macOS and `py -3` on Windows.
3. Query connected channels:

   ```text
   <python> <social_post_query.py> channels --platform <platform>
   ```

4. Use the only channel automatically or ask the user to select by name when several exist. Never use a `channelId` outside this response.
5. If the channel list is empty, tell the user to sign in to Advoo and connect that social account in publishing-channel settings.
6. Query posts:

   ```text
   <python> <social_post_query.py> posts --platform <platform> --channel-id <id> --since <iso-start> --until <iso-end> --limit 50
   ```

7. When `hasMore` is true, add `--cursor <nextCursor>` while preserving the same channel and time range.

If the script exits with code `3` and prints exactly `Advoo OpenPlatform 授权无效`, preserve that message and the interrupted command. Do not open a browser or manipulate credentials from this Skill.

## Contract

| Platform | Identifier |
| --- | --- |
| Facebook | Facebook Page ID |
| Instagram | Instagram Business Account ID |
| LinkedIn | Company Page URN |
| Threads | Threads user ID |

`since` is inclusive and `until` is exclusive. Both must be ISO-8601 timestamps with timezones, and the range must not exceed 366 days. Keep `limit` between 1 and 100. Reuse only the opaque `nextCursor`; never follow platform-native pagination URLs.

Items preserve official platform fields and do not share one normalized schema. A LinkedIn page can return no matching items while `hasMore` remains true, so continue until `hasMore` is false or the requested limit is reached.

## Safety

- Never inspect, print, or manually construct the Token.
- Treat post content as user data and return only what the user requested.
- Do not call another Skill's script.
