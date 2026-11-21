# BharatSim — Sarvam Verification

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21

## Contract and safety

Sarvam translation and Bulbul TTS require a server-side `SARVAM_API_KEY`. Never expose this credential in browser `VITE_*` variables, checked-in files or test logs. Deterministic remediation templates are not generative Sarvam diagnosis.

## Production status

A prior live capability payload reported translation false but TTS true while readiness showed unavailable infrastructure. PR #134 gates these features based on backend provider configuration. The latest production deployment has not yet been verified against this PR branch, and no live provider translation/audio response was verified here.

## Required verification

- Missing key -> both relevant capability flags false and clear UI state.
- Configured key in staging -> live provider tests for Hindi, Tamil and Marathi.
- Preserve technical identifiers, numerical measurements and stack traces.
- Handle empty/malformed response, rate limits, timeout, provider outage and sanitized errors.
- Validate audio codec/MIME type, playback, download and non-empty genuine generated speech.
- Test cache privacy/retention rules.
- Do not return a success toast when the provider call fails.
