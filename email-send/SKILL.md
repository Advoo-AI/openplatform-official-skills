---
name: email-send
description: List verified recipient email addresses and send plain-text or HTML email, including group email and direct file attachments, through Advoo OpenPlatform. Use when Codex needs to inspect a user's authorized recipients or send email to one or more already verified recipients.
---

# Email Send

Use this Skill's own `scripts/email_send.py`. It calls `ADVOO_OPENPLATFORM_BASE_URL` when that environment variable is non-empty, otherwise `https://open.advoo.ai`, with an existing environment or local-file credential.

## Workflow

1. Resolve `scripts/email_send.py` under this Skill and select Python 3: use `python3` on macOS/Linux and `py -3` on Windows.
2. Query verified recipients before composing or sending:

   ```text
   <python> <email_send.py> recipients
   ```

3. Use only email addresses returned by that command. If a requested address is absent, tell the user to go to the Advoo platform, bind that recipient email address, and complete email verification before trying again. Never bypass recipient binding or attempt the send anyway.
4. Decide whether the send instruction is complete and unambiguous. If the user explicitly asks to send and clearly identifies the recipients and final content or files, proceed without a redundant confirmation. For example, "Email this specified file to this specified recipient" is sufficient when the file and recipient resolve uniquely.
5. Ask focused questions before composing or sending whenever an important detail is missing or requires material inference. Clarify ambiguous recipients, files, subject, body, dates, reasons, tone, content type, or attachment selection. For example, a request to "write an email asking Alex for leave" requires the missing leave dates, reason, and desired tone. Present materially drafted or inferred content for review before sending. A request to write or draft an email does not by itself authorize sending it.
6. Once the instruction is unambiguous or the user approves the clarified draft, send once. Repeat `--to` for group email and `--attachment` for multiple files:

   ```text
   <python> <email_send.py> send --to first@example.com --to second@example.com --subject "Subject" --content "Body" --content-type text/plain
   ```

   For long content, use exactly one of `--content`, `--content-file`, or `--content-stdin`:

   ```text
   <python> <email_send.py> send --to recipient@example.com --subject "Subject" --content-file ./message.html --content-type text/html --attachment ./report.pdf
   ```

7. Report the API result. Never retry a send automatically, including after timeouts, because delivery may already have occurred.

If the script exits with code `3` and prints exactly `Advoo OpenPlatform 授权无效`, preserve that message and the interrupted command. Do not open a browser or manipulate credentials from this Skill.

## Contract

- `GET /v1/email/recipients` returns only verified recipients.
- `POST /v1/email/messages` accepts one or more `--to` values; every address must be verified for the current Advoo user.
- Content type must be exactly `text/plain` or `text/html`.
- Attachments are uploaded directly in the request. Do not upload them to OSS or replace them with URLs.
- Allow at most 10 attachments. Each file and the combined raw files must not exceed 20 MiB. MIME encoding may make the delivered email larger.
- The script sends JSON when there are no attachments and `multipart/form-data` with a JSON `message` part plus repeated `attachments` file parts otherwise.

## Safety

- Never inspect, print, or manually construct the Token.
- Treat recipient details, message content, and attachments as user data. Return only what the user requested.
- Do not call another Skill's script.
- Never guess materially ambiguous recipients, message content, or attachments. Ask focused questions and obtain approval for content the Skill materially drafts or infers.
- Do not send a test or real email unless the user requested that delivery.
