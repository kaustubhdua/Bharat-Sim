# Roadmap to a credible BharatSim release

## Implemented in the current draft

- [x] Repository scaffold and setup instructions.
- [x] Four named persona definitions and deterministic risk-ranked test planning.
- [x] APK upload size cap, ZIP/APK-like archive metadata checks, and SHA-256 fingerprint.
- [x] SQLite persistence for run metadata and log analyses, with backward-compatible worker columns.
- [x] Crash, ANR, memory, network, StrictMode and storage log markers; failure fingerprints and evidence-linked diagnostics.
- [x] Transparent heuristic BharatScore with explicit limitations.
- [x] Responsive dashboard for persona selection, run registration/history, log analysis, worker heartbeat status, and report inspection.
- [x] Authenticated worker claim protocol, short-lived leases, heartbeat extension, authorized APK download, result callbacks, stale-result rejection, and bounded inline results.
- [x] Polling worker agent using the Python standard library and a guarded ADB smoke runner.
- [x] Backend API/security/worker protocol tests, frontend production build CI, and worker guard/compile checks.
- [x] Local Docker Compose stack for API + dashboard, loopback-only port binding, persistent data volume, health checks, and container-build CI.
- [x] Security model, worker setup, open-source references, and explicit feature/limitation documentation.
- [x] Network shaper apply parses and compares `tc`-reported delay, jitter, loss and rate settings; end-to-end traffic-path validation remains open.

## Remaining before calling execution fully functional

### P0 — Prove real Android execution

- [ ] Provision a disposable emulator worker with Android SDK platform-tools and build-tools.
- [ ] Run a real, authorized APK end to end through the dashboard/API → queue → worker → ADB → callback → saved report.
- [ ] Exercise install failure, launch failure, worker crash, timeout, stale lease, duplicate callback, and retry recovery on a real worker.
- [ ] Verify worker heartbeats and run evidence survive API restarts.
- [ ] Capture screenshots and structured crash/ANR/exit evidence; distinguish a completed smoke procedure from a passing app journey.

### P0 — Make constraints truthful

- [ ] Implement Appium/UiAutomator2 journeys with explicit steps, assertions, screenshots, and repeatable checkpoints.
- [ ] Wire network profiles to an isolated emulator traffic path and verify actual traffic traverses the shaper.
- [ ] Run baseline, latency, bandwidth, packet-loss, outage, and recovery experiments; record requested vs verified conditions.
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
- [ ] Add browser E2E tests for upload → queued → running → report and all error states.
- [ ] Deploy frontend/API/worker and verify a real public URL, health/readiness, TLS, persistence, and deployed commit SHA.
- [ ] Add Sarvam translation only as an optional, consent-aware feature with server-side secrets, redaction, timeout, and fallback; it is not wired yet.
- [ ] Review license obligations and record provenance for any adopted open-source code/models.

## Demo truth policy

Never label an uploaded APK as tested until a worker reports actual execution evidence. CI protocol fixtures are not emulator execution. Never fabricate crashes, network graphs, performance measurements, or population impact estimates. Distinguish measured facts, heuristic scores, simulations, and unsupported assumptions.
