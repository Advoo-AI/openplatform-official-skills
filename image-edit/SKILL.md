---
name: image-edit
description: Generate an image from a text prompt through the billed Advoo OpenPlatform image-edit API. Use when an agent needs to discover supported image models and credit prices, select resolution or aspect ratio, or generate an image.
---

# Image Edit

Generate one image from text with the shared cross-platform `openplatform.py` client. The API origin is fixed to `https://www.advoo.ai`; each successful request consumes the Advoo user's credits.

## Workflow

1. Collect the prompt and optional model, resolution, and aspect ratio. The current public endpoint accepts text prompts only; do not send reference images.
2. Resolve the shared `openplatform.py` client distributed with the official Skills and make requests with `--app-name "Image Edit"`.

3. Query the model list before generating. Use the requested supported model; if no model was requested and several are available, ask the user to select by display name and credit price.
4. Treat an explicit user request to generate an image as consent for one displayed-price invocation. Ask again only when the price cannot be determined or the chosen model materially differs from the user's request.
5. Build the request JSON with a JSON serializer, never by interpolating untrusted prompt text into shell syntax.
6. Return or save the generated image immediately. The response URL is temporary; use `expiresAt` to communicate its expiry.

## Models

```text
<python> <openplatform.py> request GET /api/advoo/v1/openplatform/image-edit/models --app-name "Image Edit"
```

Each model includes `apiName`, `displayName`, `provider`, and `price`. Send `apiName` as the request's `model`; `price` is the current credit cost exposed by Advoo.

## Edit request

```text
<python> <openplatform.py> request POST /api/advoo/v1/openplatform/image-edit --app-name "Image Edit" --json-file <request.json>
```

Example payload:

```json
{
  "model": "seedream-5-0-pro",
  "prompt": "A clean studio product photograph on a soft neutral background",
  "resolution": "2K",
  "aspectRatio": "1:1"
}
```

Read [references/api.md](references/api.md) for response fields, billing behavior, and error handling.

## Safety

- Always use the shared Python client; never construct request headers manually.
- Do not claim that a temporary result URL is permanent storage.
- Do not retry billable failures automatically.
