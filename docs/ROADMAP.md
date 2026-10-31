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
- [x] Real Chromium browser E2E against the actual local FastAPI service and isolated SQLite test database: connected API/profile loading, line-addressable log analysis, and disabled run registration until an APK is selected. The backend independently rejects run creation without an APK. These tests do not fabricate execution results.
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
- [x] Historical differential traffic-path experiment in a disposable emulator measured three baseline and three shaped HTTPS requests to `example.com` over CELLULAR (88 ms baseline median; 233 ms shaped median; 145 ms increase with 150 ms configured) and verified reset. This is historical fixture-only evidence, not a pass for the current release candidate.
- [ ] Current routed-probe candidate: verify repeated real HTTPS transfers over a supported emulator transport, require observed latency and bandwidth deltas, capture retries and exact bytes, and verify reset. The previous host-routable test endpoint failed with `ConnectException`; host-alias tests did not show repeatable latency effects. No current-candidate pass is claimed.
- [x] Add a separate CI workflow that boots an Android emulator, starts a local API and authenticated worker, verifies upload → queue → ADB execution → result callback → persisted report, then checks an Appium primary-action journey with a screenshot artifact.

## Remaining before calling execution fully functional

### P0 — Prove real Android execution

- [x] Provision a disposable Android emulator in GitHub Actions with Android SDK platform-tools and build-tools.
- [x] Execute a source-built, authorized fixture APK through local FastAPI upload → queue/lease → worker → ADB install/launch/logcat → result callback → persisted run report. The integrated pipeline and CI suite pass on the current main line; the separate Android fixture network data-plane candidate remains under revalidation and must pass repeated measurements/reset before network throughput is claimed verified.
- [x] The basic Appium/UiAutomator2 fixture primary-action assertion is implemented and passed on an earlier revision. The current extended journey also performs real HTTPS network probes; the latest recorded candidate failed while waiting for the network probe to finish. The primary-action fixture pass does not count as current end-to-end release evidence.
- [x] Exercise a real Android install-signature-conflict failure through API → worker → ADB → callback, and exercise an APK-shaped invalid-manifest failure through the real worker/API path. The workflow checks failed status, failure classification, and cleanup evidence.
- [ ] Exercise launch failure, worker crash, timeout, stale lease, and retry recovery on a real worker. Duplicate/stale callback and retry-exhaustion protocol behavior have unit-level coverage, but not all are yet proven as full emulator journeys.
- [ ] Verify worker heartbeat state and full run evidence/artifacts survive API restarts. Only run metadata persistence is currently covered by a process-restart integration test.
- [ ] Capture screenshots and structured crash/ANR/exit evidence; distinguish a completed smoke procedure from a passing app journey.

### P0 — Make constraints truthful

- [x] Implement and pass the Appium/UiAutomator2 fixture journey with explicit steps, assertions, screenshots, and repeatable checkpoints.
- [ ] Add app-specific journey authoring, broader assertions, and error-state coverage for arbitrary uploaded applications.
- [ ] Verify a real request from the source-built fixture is measurably slower under the active emulator profile than its baseline on the same supported transport on the current release candidate. Historical external-endpoint results are not sufficient to mark the current experiment complete.
- [ ] Verify latency and bandwidth shaping with repeated 2,000,000-byte HTTPS transfers, record actual payload bytes/retries, require observable median deltas, and verify reset. The current candidate uses Cloudflare's documented `https://speed.cloudflare.com/__down?bytes=500000` speed-test endpoint, resolves its IPv4 address on the CI host, pins that IP in the fixture socket, retains the URL hostname for TLS SNI/certificate validation, and explicitly enables the simulated cellular route. A bounded preflight requires Android to expose a cellular default route before probing; failed probes include device-side logcat. If the public endpoint remains unreachable or measurements do not pass, keep these controls marked partially verified rather than claiming full traffic-path support.
- [ ] Extend traffic-path verification to arbitrary app-specific requests and repeated baseline/latency/bandwidth/recovery experiments.
- [ ] Run real app-request baseline, latency, bandwidth, packet-loss, outage, and recovery experiments; record requested vs verified conditions. Delay/bandwidth control readback exists, but packet loss and outage are not implemented, and `constraints_applied=false` remains until the full persona is enforced.
- [ ] Add supported RAM/storage/CPU pressure controls or report those constraints as unsupported.
- [ ] Validate at least one low-cost physical Android device before making real-device fidelity claims.

### P0 — Secure public execution

- [x] Implement optional Supabase Auth JWT verification and owner-scoped run/analysis reads and writes, with cross-user regression tests. Live provider settings and deployed Auth/session verification remain pending.
- [ ] Run untrusted APKs in disposable, resource-limited VMs/containers with no production secrets and restricted egress.
- [ ] Add enforced quotas/concurrency limits, active-run cancellation with verified child-process teardown, durable report/log/screenshot object storage and retention, and a complete audit trail. Private APK Storage and owner-scoped run deletion/report export are implemented, but do not complete these remaining controls.
- [ ] Perform a threat-model review and security testing before public APK uploads.

### P1 — Production operations and quality

- [ ] Move multi-worker production metadata to PostgreSQL and use durable queue semantics.
- [ ] Complete durable report/log/screenshot artifact storage and lifecycle, backup/restore drills, and operational alerts. Owner-scoped JSON report export is implemented, but is generated from bounded database JSON rather than a durable object artifact.
- [ ] Extend browser E2E coverage to real APK upload validation, worker-connected queued → running → report lifecycle, and API/network error states; current browser tests cover actual API-backed profiles, log analysis, and no-worker registration.
- [ ] Deploy frontend/API/worker and verify a real public URL, health/readiness, TLS, persistence, and deployed commit SHA.
- [ ] Add Sarvam translation only as an optional, consent-aware feature with server-side secrets, redaction, timeout, and fallback; it is not wired yet.
- [ ] Review license obligations and record provenance for any adopted open-source code/models.

## Demo truth policy

Never label an uploaded APK as tested until a worker reports actual execution evidence. CI protocol fixtures are not emulator execution. Never fabricate crashes, network graphs, performance measurements, or population impact estimates. Distinguish measured facts, heuristic scores, simulations, and unsupported assumptions.
