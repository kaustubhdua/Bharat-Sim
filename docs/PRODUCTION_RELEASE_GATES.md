# Production release gates

This document is the release checklist for turning BharatSim from a credible local/CI prototype into a safe, supportable Android resilience-testing service. It deliberately separates **implemented**, **measured**, **simulated**, and **not yet supported** behavior. A checked box requires a reproducible artifact or test result from the target revision; a code path existing is not proof that the feature works end to end.

## Current release decision

**Do not expose public APK execution yet.** The repository documents real fixture-only Android emulator runs and a local API → queue/lease → ADB → callback → saved-report path. Those results validate the source-built fixture in CI, not arbitrary uploaded APKs, multi-tenant security, physical-device fidelity, or a production deployment.

## P0 — Safety and tenant boundaries

- [ ] Add real user identity (or an explicitly scoped single-tenant access model) and enforce authorization on every run, report, log analysis, download, and artifact endpoint.
- [ ] Add cross-user denial tests: user A must not list, read, download, cancel, or infer user B's run or artifact. Test unauthenticated and expired sessions too.
- [ ] Run each untrusted APK only in a disposable VM or equivalently strong isolation boundary. No host secrets, privileged container, Docker socket, host filesystem mounts, or access to cloud metadata; default-deny egress except explicitly approved test targets.
- [ ] Enforce per-job CPU, memory, disk, process, wall-clock and network quotas. Ensure timeout/cancellation actually stops ADB, emulator, Appium and child processes.
- [ ] Add per-user upload/run/concurrency quotas, abuse controls, audit events, and documented artifact retention/deletion.
- [ ] Store reports, screenshots and logs in private object storage with generated object names, authorization checks, bounded retention, and integrity hashes. Do not rely on a local container filesystem for multi-instance production.
- [ ] Add security tests for malformed APK archives, decompression bombs, oversized multipart bodies/results, path traversal, package-name injection, malicious redirect targets, replayed callbacks, stale leases, worker crashes and cleanup failures.
- [ ] Obtain a documented threat-model/security review before enabling public execution.

**Acceptance evidence:** tests and review results attached to the exact release commit; isolation/egress policy verified from inside the worker environment; cross-tenant tests fail closed; cancellation and cleanup tests prove no active child process or artifact remains.

## P0 — Prove what a test actually did

- [ ] Maintain a real disposable-emulator CI journey: upload APK → validate/hash → queue → lease → install/launch → collect logcat → Appium assertions → authenticated callback → persisted report.
- [ ] Add negative real-worker journeys for invalid APK/manifest, install failure, launch failure, app crash, ANR/timeout, worker termination, expired lease, duplicate/stale callback and retry exhaustion.
- [ ] Test persistence across API restart for run state, worker heartbeat state, report JSON, screenshots/logs and artifact metadata. Include crash/restart during an active lease.
- [ ] Distinguish procedure status from app verdict. A smoke runner completing is not equivalent to an app journey passing. Show each authored assertion as pass/fail/not-run with evidence and timestamps.
- [ ] Record the exact APK SHA-256, emulator image/API, OS/worker revision, test profile, requested controls, observed controls, request measurements, retry counts, start/end times and report schema version.
- [ ] Keep baseline and constrained measurements paired on the same transport and endpoint. Use repeated samples and report medians/spread, sample count, failures and environmental caveats.
- [ ] For every control, distinguish requested, applied/read back, traffic-path verified and unsupported. A console setting alone does not prove the app's request used that path.
- [ ] Keep fixture/test data unmistakably labelled as fixture evidence. Never present fixture metrics as customer results or general device-population claims.

**Acceptance evidence:** downloadable report and CI artifacts generated from the same run, with hashes and a clear provenance chain; a clean run and a deliberately failing run both reach correct terminal states.

## P0 — Honest constraint support

- [ ] Complete repeatable latency-only and bandwidth-only traffic-path experiments on the supported emulator transports. Assert expected direction of effect using measured requests and verify reset even on failure.
- [ ] Implement and verify packet loss, outage/recovery and any advertised jitter controls; until then, mark them unsupported in both API capabilities and UI.
- [ ] Implement resource pressure controls (CPU/RAM/storage/battery) with observed state and cleanup, or keep them clearly unsupported. Do not infer low-storage or low-memory behavior from a persona label alone.
- [ ] Validate the declared profile on at least one physical low-cost Android device before claiming physical-device fidelity. Keep emulator and physical-device evidence separate.
- [ ] Add app-specific journey authoring with selectors, assertions, waits, screenshots, error-state checks and deterministic teardown. Document unsupported apps and Appium/UiAutomator2 limitations.

**Acceptance evidence:** profile-by-profile tests and reports with requested-versus-observed values; all claimed controls have automated regression tests; reset is verified in a cleanup path.

## P1 — Production operation

- [ ] Replace SQLite/local filesystem assumptions with a production database, migrations, durable job queue, and private artifact storage before horizontally scaling API/worker instances.
- [ ] Add readiness checks that accurately describe required dependencies and separate API readiness from worker availability. A ready API must not imply that an execution worker is online.
- [ ] Add structured logs, metrics, alerts, backup/restore drills, retention jobs, incident procedures, rate limiting, TLS and secret rotation.
- [ ] Deploy the API, frontend and isolated worker to a controlled environment; verify HTTPS, auth, persistence after restart, health/readiness, worker heartbeat, upload-to-report flow and deployed commit SHA from the public URL.
- [ ] Add browser E2E for APK selection/upload, queued → running → report states, worker offline, API errors, narrow mobile widths, keyboard/focus/accessibility and empty/error/loading states.
- [ ] Test install/build from a clean checkout and document pinned runtime versions, reproducible setup, upgrade/migration and rollback procedures.
- [ ] Add translation only if it is actually implemented, consent-aware, server-side secret handling is safe, and the product has timeout/fallback tests. Otherwise advertise it as unavailable.

## Release checklist

A release may be called **production-ready** only when all P0 items are complete, a reviewed deployment exists, and the exact deployed commit has passing CI and end-to-end evidence. P1 items must be completed or explicitly accepted by a named operator with a documented mitigation. If public deployment is not intended, label the product **local/controlled-beta only** and retain the public-execution guardrails.

For each checked item, record:
1. commit SHA and date;
2. command/workflow and environment;
3. result, including failures and skipped tests;
4. artifact link and SHA-256 where applicable;
5. known scope limits and reviewer.

## Upstream references

- [Android Emulator console networking controls](https://developer.android.com/studio/run/emulator-console) — documents delay/speed controls and network-status readback; it does not by itself prove application-level traffic measurements.
- [Android Emulator command-line options](https://developer.android.com/studio/run/emulator-commandline) — documents emulator startup options for latency and bandwidth.
- [Appium UiAutomator2 driver documentation](https://appium.github.io/appium-uiautomator2-driver/) — supported Android UI automation driver and setup.
- [Android app security best practices](https://source.android.com/docs/security/best-practices/app) — automated testing and isolation guidance.
- [GitHub Actions artifact documentation](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts) — retaining inspectable test evidence.

These upstream references inform the checklist; they do not certify BharatSim. Re-run and record the repository's own tests for every release.
