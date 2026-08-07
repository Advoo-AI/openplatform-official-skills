# API reference

## Platforms

| Platform | `platform` | `channelId` |
| --- | --- | --- |
| Facebook | `facebook` | Facebook Page ID |
| Instagram | `instagram` | Instagram Business Account ID |
| LinkedIn | `linkedin` | Company Page URN such as `urn:li:organization:123` |
| Threads | `threads` | Threads user ID |

List the current user's bound channels with `GET /api/advoo/v1/openplatform/social/{platform}/channels` on `https://www.advoo.ai`:

```json
{
  "code": 0,
  "msg": "suc",
  "result": [
    {
      "name": "Example Page",
      "channelId": "123456789"
    }
  ]
}
```

The channel list never returns platform access tokens. Query posts with `POST /api/advoo/v1/openplatform/social/{platform}/posts/query`.

## Request fields

| Field | Required | Meaning |
| --- | --- | --- |
| `channelId` | yes | A channel connected by the current user |
| `since` | yes | Inclusive ISO-8601 start time |
| `until` | yes | Exclusive ISO-8601 end time |
| `limit` | no | Page size, default 50, range 1-100 |
| `cursor` | no | Opaque `nextCursor` from the preceding page |

The maximum time span is 366 days.

## Response

```json
{
  "code": 0,
  "msg": "suc",
  "result": {
    "items": [],
    "nextCursor": "opaque-cursor",
    "hasMore": true
  }
}
```

Items preserve each platform's official fields. Do not assume one normalized post schema.

For LinkedIn, an intermediate page can contain no matching items while `hasMore` remains true. Continue with `nextCursor` until `hasMore` is false or the user-requested limit is reached.

## Authentication recovery

Treat these conditions as requiring one browser login and one retry:

- `ADVOO_OPENPLATFORM_TOKEN` is absent or empty.
- HTTP `401`.
- DotAI response code `1005` or `9997`.

Do not treat third-party channel authorization failures as an OpenPlatform login failure. Report that the selected social channel must be reconnected instead of repeating OpenPlatform login.
