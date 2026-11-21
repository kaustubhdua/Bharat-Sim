# BharatSim — master feature inventory and judge acceptance status

**Audit date:** 22 November 2026  
**Decision:** controlled-beta prototype with substantial implemented code and CI evidence; not fully production-complete.

This inventory is the judge-facing source of truth. “Implemented” means code exists; “CI verified” means automated tests cover the stated scope; “production accepted” requires live evidence from the intended production infrastructure.

## 1. Feature status

| Feature | Implemented | Automated / fixture evidence | Production acceptance remaining |
|---|---|---|---|
| Authentication | Supabase email/password/session code and protected workspace | JWT verification and auth regression tests | Real signup, confirmation, login, refresh, expiry, logout and recovery; two-user live test |
| Tenant isolation | Owner-scoped queries and RLS migrations | Cross-user API unit tests | Live two-user matrix for all private routes, signed URLs and objects |
| Personas | Authored device/network targets and custom persona schema | API and validation tests | Measure actual applied controls per run; profile target is not device measurement |
| Risk planner | Category-aware deterministic ranking, editable journeys and JSON export | Backend/frontend contract tests and Playwright planner test | Confirm exported plan matches UI and never imply execution |
| Logcat analysis | Deterministic signal detection, source-line evidence, recommendations and report generation | Backend tests and browser analysis journey | Authenticated live report journey, adversarial/large input review and persistence evidence |
| Failure DNA | Normalized signature grouping and occurrence counts | Unit coverage for normalization/evidence fusion | Stability across repeated runs, versions and independent samples |
| Backend classifier | Pure-Python TF-IDF centroid model (58 curated examples) | Known-signature regression tests | Independent labelled holdout, confusion matrix, calibration and external validation |
| Worker classifier | TF-IDF word/character + logistic regression | GroupKFold metrics on 9,140 mixed weak-rule/templated samples | Label-quality/leakage audit and independently labelled external holdout |
| Anomaly detection | Explicit thresholds + fixed-reference z-score heuristic | Regression tests for zero/partial telemetry | Validate thresholds, missing-data behavior and repeatability; not a trained covariance model |
| BharatScore | Transparent heuristic summary score | Known fixture/report tests | Publish implementation weights, validate against repeated controlled runs; not a probability/certification |
| APK validation | ZIP/manifest checks, bounded metadata and SHA-256 | Upload/security regression tests | Validate live uploads and malicious archive corpus |
| Private APK storage | Signed/resumable upload, worker download and cleanup code | Signed-upload and storage-auth tests | Real private bucket upload/hash/download/delete/expiry/retention round-trip |
| PostgreSQL persistence | Adapter and timestamped isolated migrations | CI applies all migrations to clean PostgreSQL and tests API restart persistence on PR #138 base | Confirm exact production DB target, apply reviewed migrations and verify live persistence |
| Worker queue | Claims, leases, heartbeat, hash-bound download and result callback | Worker protocol and PostgreSQL integration tests | Live worker registration, revocation, concurrent claim, retry and recovery tests |
| Legacy smoke worker | Install/launch, bounded observation and logcat capture | Worker unit/guard tests; the Android emulator workflow is a source-built proxy probe fixture, not a full customer-APK worker run | Dedicated host deployment and actual APK worker lifecycle evidence |
| Full engine worker | Baseline/persona passes, telemetry, proxy shaping, battery/storage and recovery checks | Engine/shaper unit tests plus source-built CI proxy fixture; CI does not execute the full engine against an uploaded APK | Dedicated isolated worker deployment; repeated app-specific traffic-path and cleanup evidence |
| Network shaping | Legacy emulator control-plane latency/bandwidth; engine proxy supports latency/bandwidth/loss stalls/resets for proxy traffic | CI measured source-built fixture HTTPS transfer and reset | Per-run arbitrary-app traffic evidence; default-deny egress; upload throughput and physical-device validation |
| CPU / RAM | CPU throttling unsupported; RAM depends on emulator provisioning/readback | Condition-planner and safety tests | Never claim CPU throttle; document actual RAM allocation per emulator |
| Speak-to-Test | Typed request, optional voice, schema-validated scenario plan, allowlisted scenario IDs | Backend/frontend tests with mocked provider and fixture builds | Live Sarvam credential, speech-to-text/interpretation and end-to-end scenario execution on deployed worker |
| JanJeevan packs | Executable BharatPay sample journey and planned pack definitions in API | Controlled original/fixed APK fixture tests | Additional public-service, education, health, delivery fixtures and assertions |
| FixProof | Original/candidate run comparison against scenario assertions | Backend/frontend contract tests | Two real completed runs of same scenario with persisted evidence |
| Run comparison | Owner-scoped completed-run comparison | API tests | Production PostgreSQL data and real reports |
| Reports / exports | Run detail, PDF and JSON export | Frontend unit/E2E and file-content checks | Durable report/artifact library, pagination and retention |
| Sarvam translation/TTS | Optional provider integration with fallback handling | Provider mocks plus live evidence artifact for selected languages | Production key scope, deployed endpoint, quota/error and audio playback tests |
| UI/theme/navigation | React/Vite workspace, theme provider, lazy routes and responsive layout | Unit tests, build and Playwright viewport checks | Manual keyboard, screen-reader, contrast, focus and mobile testing |
| Deployment | Unified FastAPI/Vite deployment configuration | CI unified build and container smoke | Exact merged SHA deployment, readiness and authenticated browser smoke |

## 2. Worker mode distinction

- `BHARATSIM_WORKER_ENGINE=smoke` (default): legacy install/launch/logcat smoke worker. It does not provide the full engine's packet-loss/reset/outage behavior.
- `BHARATSIM_WORKER_ENGINE=engine`: full baseline-vs-persona engine. Its host proxy affects only app traffic routed through Android's system proxy. Reports with no proxy connections must not claim network conditions affected the app.
- CPU throttling is unsupported in both modes. RAM constraints are provisioning-dependent and must be evidenced from the actual emulator.
- A personal laptop worker is scoped to one account, but it still runs on the user's host. It is not a per-job VM/microVM sandbox or a substitute for a restricted production worker host.

## 3. Current verified repository evidence

- PR #138 base commit `8b2beac2`: CI run [44957776493](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44957776493) passed all seven jobs, including backend, frontend, E2E, PostgreSQL integration, worker guards, unified build and container smoke.
- Android emulator workflow [44957776524](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44957776524) passed on the same code line.
- The consolidated UI branch still requires a fresh CI and Android run after its changes.
- A passing CI fixture is not a production DB, tenant-isolation or worker-isolation acceptance test.

## 4. Release blockers

1. Reconcile browser Auth/Storage project and server-side PostgreSQL target; protect the shared GenomeGuard database.
2. Apply reviewed migrations to the confirmed production DB and verify persistence.
3. Complete private Storage lifecycle and retention round-trip.
4. Verify production Auth and tenant isolation with two real accounts.
5. Deploy a dedicated per-job isolated Android worker with default-deny egress and cleanup.
6. Complete APK → worker → report → reopen/export on production.
7. Validate Failure DNA, FixProof and all claimed network conditions across repeated real runs.
8. Independently validate ML and anomaly outputs.
9. Complete Sarvam live provider and accessibility acceptance.
10. Deploy and smoke-test the exact merged SHA.

## 5. Judge-safe claims

- Logcat analysis returns deterministic signals and source-line evidence.
- The risk planner ranks test priorities; it does not execute a plan.
- The legacy worker performs an Android smoke workflow; the full engine performs baseline/persona testing when explicitly configured.
- Network controls are reported as requested, applied, read back or observed; arbitrary APK traffic may bypass the system proxy.
- ML, Failure DNA, anomaly and BharatScore outputs are triage evidence, not certified diagnoses or field-accuracy guarantees.
- Public arbitrary APK execution remains disabled until production persistence, tenant isolation, worker isolation and egress controls pass independent acceptance.


## 2026-11-22 follow-up verification

### Database and Storage
- The connected Supabase project `common 1` (`hkyieaovolkethovyenb`) contains the isolated `bharatsim` schema and the existing GenomeGuard schema. The repository's BharatSim migrations are scoped to `bharatsim`; no GenomeGuard migration or table was changed in this operation.
- Applied the five missing BharatSim migrations: custom persona/APK metadata, worker claiming status, run scenario, 500 MiB APK metadata limit, and personal-worker ownership/key metadata. The connected project now records all nine BharatSim migrations.
- Verified a synthetic run insert/read/delete round-trip against `bharatsim.runs`; the test row was removed and the final run count is zero.
- Private bucket `bharatsim-private` exists, is non-public, and has a 150 MiB per-object cap. Multipart code uses 45 MiB objects for a 500 MiB total APK. No APK objects or Storage object policies exist yet.
- Updated Vercel's next-deployment Auth/Storage URL and browser publishable key to the connected project and raised `BHARATSIM_MAX_UPLOAD_MB` to 500. The currently running Production deployment has not been redeployed with those environment changes.
- Vercel does not have `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY` in its environment inventory. Private Storage therefore remains unavailable until an operator adds a server-only key. The production database URL is present as a sensitive variable but its value/target could not be inspected; production readiness returned `database=unavailable` at the last live check.

### Worker and APK journey
- The Android emulator CI workflow is more than a proxy-only check: it starts the local FastAPI control plane, registers an authenticated worker, uploads a source-built fixture APK, leases/downloads/installs/runs it, persists the report through the worker callback, and tests negative install/invalid-manifest cases. It also runs a separate measured HTTPS proxy fixture.
- This proves the controlled CI fixture journey using local test persistence. It does not prove production Supabase Storage, a user-uploaded APK, or per-job isolation.
- The worker agent and runner now share the 500 MiB APK size contract. A regression test was added to keep those limits aligned; the latest head still needs CI execution.
- A KVM host bootstrap and Firecracker-per-job design exist in the repository, but no production KVM host or disposable microVM service has been provisioned. Render's connected services do not provide the required KVM boundary.

### ML, Failure DNA, FixProof, Sarvam and accessibility
- Added a hand-authored 48-line holdout for the backend centroid classifier. A pre-CI evaluation of the checked-in model produced 79.2% accuracy and approximately 0.787 macro-F1. Normal-class recall was 0.50; this small curated set is a regression check, not a field-accuracy claim.
- The worker classifier's checked-in grouped cross-validation reports 78.43% accuracy (std 9.13%) and 0.7707 macro-F1 (std 10.24%) on weakly labelled LogHub plus templated examples; it is not production-field accuracy.
- Added repeated-input stability tests for Failure DNA fingerprints and repeated FixProof verdicts. These are synthetic deterministic tests, not repeated physical-device executions.
- The checked-in live Sarvam evidence from 2026-11-21 records successful non-fallback Sarvam interpretation, Hindi/Tamil TTS and STT. It was generated by the live-check script, not from a verified production Vercel endpoint.
- Added a Playwright baseline accessibility semantics check for main landmark, control names and image alt text. Existing E2E tests cover responsive widths from 320px to 1440px. Manual screen-reader, keyboard, focus, contrast and real-device testing remains outstanding.

### Latest code validation caveat
- The latest fully green CI, dependency audit and Android emulator workflow are on commit `13a829407433a24a9cd3f508fe0a41ed4838b6d4`.
- Additional readiness diagnostics, independent ML holdout, repeated Failure DNA/FixProof tests, 500 MiB worker limit alignment and accessibility checks were committed after that SHA. They have not yet been rerun in CI.
- A Vercel preview for `13a8294` built successfully, but its readiness endpoint returned 503 because preview intentionally does not receive the Production-only database URL or server Storage key. The Vercel deployment API then reached its 100-deployments/day limit, so the latest head could not be redeployed during this session.
