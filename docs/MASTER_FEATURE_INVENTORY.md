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
| Legacy smoke worker | Install/launch, bounded observation and logcat capture | Android emulator smoke workflow | Dedicated host deployment and production lifecycle evidence |
| Full engine worker | Baseline/persona passes, telemetry, proxy shaping, battery/storage and recovery checks | Engine and shaper unit tests; source-built CI proxy fixture | Dedicated isolated worker deployment; repeated app-specific traffic-path and cleanup evidence |
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
- A worker process on a developer laptop or generic shared VM is not a production sandbox.

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
