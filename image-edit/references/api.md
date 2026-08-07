# Image Edit API

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/advoo/v1/openplatform/image-edit/models` | List supported models and current credit prices |
| `POST` | `/api/advoo/v1/openplatform/image-edit` | Generate one image from a text prompt |

Both endpoints require `Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}`.

## Request

| Field | Required | Meaning |
| --- | --- | --- |
| `model` | yes | An `apiName` returned by the models endpoint |
| `prompt` | yes | Non-empty text instruction |
| `resolution` | no | Model resolution such as `2K` |
| `aspectRatio` | no | Ratio such as `1:1`, `16:9`, `9:16`, or `auto` |

The current OpenPlatform contract produces one image and does not accept reference images.

## Response

```json
{
  "code": 200,
  "msg": "OK",
  "data": {
    "created": 1786096800,
    "model": "seedream-5-0-pro",
    "data": [
      {
        "url": "https://temporary-image-url.example/image.png",
        "expiresAt": 1786100400
      }
    ]
  }
}
```

`url` is a signed temporary URL. `expiresAt` is a Unix timestamp in seconds and is normally one hour after creation.

## Billing and errors

- The backend calculates the price from the selected model and effective resolution.
- Credits are consumed through the authenticated Advoo account's existing billing system.
- Model generation or result-URL signing failures trigger the existing credit rollback path.
- Insufficient credits must be reported to the user as an Advoo balance issue; do not retry with another billed model automatically.
- HTTP 401 means the OpenPlatform token is missing or invalid. Invoke `$openplatform-auth` and retry once.
- Other 4xx responses indicate request or account problems. Correct the request or ask the user for direction.
- Do not automatically retry 5xx or timeout responses because the request may have reached the billable operation.
