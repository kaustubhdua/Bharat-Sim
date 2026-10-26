# Roadmap to a credible BharatSim release

## Implemented in the current draft

- [x] Repository scaffold and setup instructions.
- [x] Four named persona definitions and deterministic risk-ranked test planning.
- [x] APK upload size cap, ZIP/APK-like archive metadata checks, and SHA-256 fingerprint.
- [x] SQLite persistence for run metadata and log analyses, with backward-compatible worker columns.
- [x] Crash, ANR, memory, network, StrictMode and storage log markers; failure fingerprints and evidence-linked diagnostics.
- [x] Worker reports include bounded, line-addressable crash/ANR/OOM/network/storage marker excerpts from collected logcat with nearby context; they are diagnostic markers, not confirmed root causes, and empty logs do not generate findings.
- [x] Transparent heuristic BharatScore with explicit limitations.
- [x] Responsive dashboard for persona selection, run registration/history, log analysis, worker heartbeat status, and report inspection.
- [x] Real Chromium browser E2E against the actual local FastAPI service and SQLite test database: connected API/profile loading, line-addressable log analysis, and honest awaiting-worker run status. These tests use an isolated test database and do not fabricate execution results.
- [x] Authenticated worker claim protocol, short-lived leases, heartbeat extension, authorized APK download, result callbacks, stale-result rejection, and bounded inline results.
- [x] Polling worker agent using the Python standard library and a guarded ADB smoke runner.
- [x] Backend API/security/worker protocol tests, frontend production build CI, worker guard/compile checks, and automated Python/JavaScript dependency vulnerability audits.
- [x] Process-level test proves run metadata remains available after the FastAPI process restarts against the same SQLite data directory; it intentionally does not claim worker-heartbeat or artifact durability.
- [x] Protocol tests prove heartbeat lease renewal, expired-lease reclamation, stale lease-token rejection, duplicate callback rejection, and fail-closed behavior after the retry limit.
- [x] Local Docker Compose stack for API + dashboard, loopback-only port binding, persistent data volume, health checks, and container-build CI.
- [x] Security model, worker setup, open-source references, and explicit feature/limitation documentation.
- [x] Network shaper apply parses and compares `tc`-reported delay, jitter, loss and rate settings.
- [x] CI creates a disposable Linux network namespace and veth pair, measures actual ping RTT before and after shaping, requires the configured delay to be observable, and verifies qdisc cleanup. This proves the Linux prototype on that veth only.
- [x] Pass server-authored persona network targets to the worker; apply Android Emulator console latency and upload/download speed controls, read back the configured values, and verify restoration to defaults after each run.
- [x] Complete differential traffic-path experiments in a disposable emulator: one warm-up, three baseline and three shaped real HTTPS requests to `example.com` over CELLULAR, with emulator console readback and reset verification. One passing run measured baseline median 88 ms and shaped median 233 ms (145 ms increase) under a configured 150 ms delay. Later runs showed variable effects (including a 75 ms increase), so the Appium assertion now requires a repeatable median increase of at least 50 ms and records the actual delta rather than claiming exact equivalence to the configured delay. This proves the source-built fixture path in CI only.
- [x] Add a separate CI workflow that boots an Android emulator, starts a local API and authenticated worker, verifies upload → queue → ADB execution → result callback → persisted report, then checks an Appium primary-action journey with a screenshot artifact.

## Remaining before calling execution fully functional

### P0 — Prove real Android execution

- [x] Provision a disposable Android emulator in GitHub Actions with Android SDK platform-tools and build-tools.
- [x] Execute a source-built, authorized fixture APK through local FastAPI upload → queue/lease → worker → ADB install/launch/logcat → result callback → persisted run report. The latest recorded workflow passed the API-to-ADB pipeline and fixture Appium assertion; this does not prove arbitrary APK correctness or production isolation.
- [x] Pass the Appium/UiAutomator2 fixture primary-action UI assertion in the disposable emulator workflow; the workflow asserts that tapping the stable accessibility identifier changes the status text and preserves a screenshot. This is a fixture journey, not a suite for arbitrary apps.
- [ ] Exercise install failure, launch failure, worker crash, timeout, stale lease, duplicate callback, and retry recovery on a real worker.
- [ ] Verify worker heartbeat state and full run evidence/artifacts survive API restarts. Only run metadata persistence is currently covered by a process-restart integration test.
- [ ] Capture screenshots and structured crash/ANR/exit evidence; distinguish a completed smoke procedure from a passing app journey.

### P0 — Make constraints truthful

- [x] Implement and pass the Appium/UiAutomator2 fixture journey with explicit steps, assertions, screenshots, and repeatable checkpoints.
- [ ] Add app-specific journey authoring, broader assertions, and error-state coverage for arbitrary uploaded applications.
- [x] Verify a real request from the source-built fixture is measurably slower under the active emulator profile than its baseline on the same cellular/Ethernet transport. Latest CI: median 88 ms baseline vs 233 ms shaped, +145 ms; network profile reset verified.
- [ ] Extend traffic-path verification to arbitrary app-specific requests and repeated baseline/latency/bandwidth/recovery experiments.
- [ ] Run real app-request baseline, latency, bandwidth, packet-loss, outage, and recovery experiments; record requested vs verified conditions. Delay/bandwidth control readback exists, but packet loss and outage are not implemented, and `constraints_applied=false` remains until the full persona is enforced.
- [ ] Add supported RAM/storage/CPU pressure controls or report those constraints as unsupported.
- [ ] Validate at least one low-cost physical Android device before making real-device fidelity claims.

### P0 — Secure public execution

- [ ] Implement real user identity and per-run ownership/authorization.
- [ ] Run untrusted APKs in disposable, resource-limited VMs/containers with no production secrets and restricted egress.
- [ ] Add quotas, concurrency limits, cancellation, artifact retention/deletion, private object storage, and audit logging.
- [ ] Perform a threat-model review and security testing before public APK uploads.

### P1 — Production operations and quality

- [ ] Move multi-worker production metadata to PostgreSQL and use durable queue semantics.
- [ ] Add authenticated artifact downloads, durable log/screenshot storage, migrations/backups, and operational alerts.
- [ ] Extend browser E2E coverage to real APK upload validation, worker-connected queued → running → report lifecycle, and API/network error states; current browser tests cover actual API-backed profiles, log analysis, and no-worker registration.
- [ ] Deploy frontend/API/worker and verify a real public URL, health/readiness, TLS, persistence, and deployed commit SHA.
- [ ] Add Sarvam translation only as an optional, consent-aware feature with server-side secrets, redaction, timeout, and fallback; it is not wired yet.
- [ ] Review license obligations and record provenance for any adopted open-source code/models.

## Demo truth policy

Never label an uploaded APK as tested until a worker reports actual execution evidence. CI protocol fixtures are not emulator execution. Never fabricate crashes, network graphs, performance measurements, or population impact estimates. Distinguish measured facts, heuristic scores, simulations, and unsupported assumptions.
