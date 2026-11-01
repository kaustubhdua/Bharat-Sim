# Sarvam report translation

BharatSim optionally translates a **condensed finding summary** into Hindi, Tamil, or Marathi using Sarvam's Text Translation API (`sarvam-translate:v1`).

## Enable

Set `SARVAM_API_KEY` as a server-only environment variable on the backend. Never use a `VITE_*` or `NEXT_PUBLIC_*` variable for this credential and never commit it. The capability endpoint reports `sarvam_translation: true` only when a key is configured.

The integration uses the official `POST https://api.sarvam.ai/translate` endpoint and the `api-subscription-key` header. It uses a 15-second timeout, sends no more than 2,000 characters, permits only `hi-IN`, `ta-IN`, and `mr-IN`, and maps provider failures to sanitized API errors. There is no automatic retry, to avoid unexpected repeated usage charges.

## Privacy behavior

Translation is opt-in per report. The dashboard sends only a short summary of the BharatScore, finding titles, explanations, and recommendations after the user clicks **Translate report**. Raw logcat, APK contents, access tokens, and worker evidence files are not sent by this feature. The original English report is not modified or replaced.

When `BHARATSIM_AUTH_REQUIRED=true`, the translation endpoint is protected by the same verified Supabase access-token middleware as other report data.

## Verification

Run `pytest -q backend/tests/test_sarvam.py`. Tests mock the upstream HTTP response and cover supported languages, missing credentials, input limits, provider rate limiting, and authentication enforcement. A mocked test proves request construction and error handling; it does not claim a live Sarvam account/API key has been validated.

## Official API reference

- https://docs.sarvam.ai/api-reference/text/translate-text
- https://docs.sarvam.ai/api/getting-started/quickstart
