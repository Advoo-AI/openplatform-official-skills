---
name: image-edit
description: Generate an image from a text prompt through the billed Advoo OpenPlatform image-edit API. Use when an agent needs to discover supported image models and credit prices, select resolution or aspect ratio, generate an image, or recover from a missing or invalid OpenPlatform token.
---

# Image Edit

Generate one image from text with `curl`. The API origin is fixed to `https://www.advoo.ai`; each successful request consumes the authenticated Advoo user's credits.

## Workflow

1. Collect the prompt and optional model, resolution, and aspect ratio. The current public endpoint accepts text prompts only; do not send reference images.
2. Set the authorization-page label and invoke `$openplatform-auth` to load `ADVOO_OPENPLATFORM_TOKEN`:

   ```bash
   export ADVOO_OPENPLATFORM_APP_NAME="Image Edit"
   ```

3. Query the model list before generating. Use the requested supported model; if no model was requested and several are available, ask the user to select by display name and credit price.
4. Treat an explicit user request to generate an image as consent for one displayed-price invocation. Ask again only when the price cannot be determined or the chosen model materially differs from the user's request.
5. Build the request JSON with a JSON serializer, never by interpolating untrusted prompt text into shell syntax.
6. Call the image-edit endpoint once. If the request returns HTTP 401, unset the rejected token, invoke `$openplatform-auth`, and retry once.
7. Return or save the generated image immediately. The response URL is temporary; use `expiresAt` to communicate its expiry.

## Models

```bash
curl --silent --show-error --fail-with-body \
  --request GET \
  --url "https://www.advoo.ai/api/advoo/v1/openplatform/image-edit/models" \
  --header "Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}"
```

Each model includes `apiName`, `displayName`, `provider`, and `price`. Send `apiName` as the request's `model`; `price` is the current credit cost exposed by Advoo.

## Edit request

```bash
curl --silent --show-error --fail-with-body \
  --request POST \
  --url "https://www.advoo.ai/api/advoo/v1/openplatform/image-edit" \
  --header "Authorization: Bearer ${ADVOO_OPENPLATFORM_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "${request_json}"
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

- Read the JWT only from `ADVOO_OPENPLATFORM_TOKEN` and never display it.
- Never use `curl --verbose` or shell tracing.
- Do not claim that a temporary result URL is permanent storage.
- Do not retry billable failures automatically except for the single authorization retry, which only occurs when the original request was rejected before generation.
