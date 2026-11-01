"""Opt-in Sarvam report translation. Raw logcat is never sent by this module."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SarvamProviderError(Exception):
    """The upstream translation service failed or returned an invalid response."""


class SarvamRateLimited(Exception):
    """Sarvam rejected the request due to rate limits."""


SUPPORTED_TARGETS = {"hi-IN", "ta-IN", "mr-IN"}
SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"


def translate_report_text(text: str, target_language_code: str) -> str:
    """Translate at most 2,000 characters using server-side credentials."""
    value = text.strip()
    if not value or len(value) > 2000:
        raise ValueError("Translation text must contain between 1 and 2,000 characters.")
    if target_language_code not in SUPPORTED_TARGETS:
        raise ValueError("Unsupported translation language.")
    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if len(api_key) < 16:
        raise SarvamProviderError("Sarvam API credentials are not configured.")

    payload = json.dumps({
        "input": value,
        "source_language_code": "en-IN",
        "target_language_code": target_language_code,
        "model": "sarvam-translate:v1",
    }).encode("utf-8")
    request = Request(
        SARVAM_TRANSLATE_URL,
        data=payload,
        headers={"Content-Type": "application/json", "api-subscription-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise SarvamProviderError("Sarvam returned an unexpected response.")
            result = json.loads(response.read(64 * 1024).decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise SarvamRateLimited() from None
        raise SarvamProviderError("Sarvam rejected the translation request.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise SarvamProviderError("Sarvam translation request failed.") from None

    translated = result.get("translated_text") if isinstance(result, dict) else None
    if not isinstance(translated, str) or not translated.strip() or len(translated) > 8000:
        raise SarvamProviderError("Sarvam returned an invalid translation.")
    return translated.strip()
