---
name: image-edit
description: Generate or edit one image through the billed Advoo OpenPlatform API. Use to discover supported image models and credit prices, generate from text, or transform up to four local or HTTP(S) reference images.
---

# Image Edit

Use this Skill's own `scripts/image_edit.py`. It is self-contained and calls `https://open.advoo.ai` with an existing environment or local-file credential.

## Workflow

1. Resolve `scripts/image_edit.py` under this Skill.
2. Select Python 3: use `python3` on macOS and `py -3` on Windows.
3. Query models before generation:

   ```text
   <python> <image_edit.py> models
   ```

4. Use the requested supported model. If none was requested and several are available, ask the user to select by display name and credit price.
5. Treat an explicit generation request as consent for one displayed-price invocation. Never retry a billable request automatically.
6. Generate or edit:

   ```text
   <python> <image_edit.py> edit --model <api-name> --prompt <prompt> [--resolution <resolution>] [--aspect-ratio <ratio>] [--image <path-or-url>]...
   ```

Use `--prompt-stdin` for multiline or shell-sensitive prompts. Repeat `--image` for up to four local PNG/JPEG/WebP files or HTTP(S) URLs. The script uploads reference images through the authenticated temporary-file flow.

If the script exits with code `3` and prints exactly `Advoo OpenPlatform 授权无效`, preserve that message and the interrupted command. Do not open a browser or manipulate credentials from this Skill.

## Result and billing

The models response exposes `apiName`, `displayName`, `provider`, and `price`. The generation response contains `created`, `model`, and a temporary signed image URL with `expiresAt`.

- Report insufficient credits as an Advoo balance issue.
- Do not switch models automatically.
- Do not retry other 4xx, 5xx, or timeout responses because the request may have reached the billable operation.
- Save or return a successful temporary image immediately.

## Safety

- Never inspect, print, or manually construct the Token.
- Do not claim that a temporary result URL is permanent storage.
- Do not call another Skill's script.
