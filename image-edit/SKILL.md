---
name: image-edit
description: Generate or edit an image through the billed Advoo OpenPlatform image-edit API. Use when an agent needs to discover supported image models and credit prices, generate from text, or transform up to four local or HTTP(S) reference images.
---

# Image Edit

Generate or edit one image with the shared cross-platform `auth.py` client. The API origin is fixed to `https://open.advoo.ai`; each successful request consumes the Advoo user's credits.

## Workflow

1. Collect the prompt, optional reference images, model, resolution, and aspect ratio. Accept up to four local PNG/JPEG/WebP paths or HTTP(S) image URLs.
2. Resolve the shared `auth.py` client distributed with the official Skills. Use its structured `image` commands; do not construct JSON or call the generic request command.

3. Query the model list before generating. Use the requested supported model; if no model was requested and several are available, ask the user to select by display name and credit price.
4. Treat an explicit user request to generate an image as consent for one displayed-price invocation. Ask again only when the price cannot be determined or the chosen model materially differs from the user's request.
5. Pass ordinary prompts with `--prompt`. For multiline prompts or prompts that are awkward to quote in the current shell, use `--prompt-stdin`; Python constructs the JSON internally.
6. Return or save the generated image immediately. The response URL is temporary; use `expiresAt` to communicate its expiry.

## Models

```text
<python> <auth.py> image models
```

Each model includes `apiName`, `displayName`, `provider`, and `price`. Send `apiName` as the request's `model`; `price` is the current credit cost exposed by Advoo.

## Edit request

```text
<python> <auth.py> image edit --model <api-name> --prompt <prompt> --resolution <resolution> --aspect-ratio <ratio> [--image <path-or-url>]...
```

`model` and `prompt` are required. `resolution` and `aspectRatio` are optional model-specific strings such as `2K` and `1:1`. Repeat `--image` for multiple references. The helper validates each image, uploads it through the authenticated temporary-file flow, and sends only the resulting user-bound OssKeys to image editing.

## Result and billing

The response contains `created`, `model`, and one image item with a signed `url` and Unix `expiresAt`. The URL is normally valid for one hour.

- The backend derives the credit price from the selected model and effective resolution.
- Model generation or URL-signing failures use the existing credit rollback path.
- Report insufficient credits as an Advoo balance issue; never switch to another billed model automatically.
- Do not automatically retry other 4xx, 5xx, or timeout responses because a request may have reached the billable operation.

## Safety

- Always use the shared Python client; never construct request headers manually.
- Do not claim that a temporary result URL is permanent storage.
- Do not retry billable failures automatically.
