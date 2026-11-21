# BharatSim — final product audit

**Audit date:** 2026-11-21  
**Audited ref:** `main` at `529d308532f042a3ba4092171370cd4c29a068cb`  
**Working branch:** `fix/production-capability-gates-2026-11`  
**Decision:** controlled-beta MVP; **not approved for production arbitrary-APK execution**.

This is a repository and evidence audit. It does not imply access to private Vercel/Supabase credentials, production customer data, a live isolated worker host, or a physical Android test fleet. Items are classified by what the checked-in implementation and recorded CI evidence establish.

## Executive summary

BharatSim is materially beyond a static hackathon mock-up. It contains a React 19/Vite dashboard, FastAPI API, Supabase Auth integration, PostgreSQL adapter and migrations, private APK storage/signing flow, lease-based worker protocol, Android ADB smoke runner with bounded monkey exploration and gfxinfo/meminfo collection, persona/risk planner, evidence-linked log analysis, a portable TF-IDF centroid classifier, statistical baseline comparison, Sarvam text translation/TTS endpoints, evaluator fixtures, run-comparison UI, Playwright tests, PostgreSQL integration tests and dependency audits.

The key issue is not absence of all engineering. It is the gap between a carefully guarded controlled-beta application and the production product described in the completion brief. The public deployment was explicitly configured to fail closed where server-side persistence and worker isolation are unavailable. Live capability inspection confirms `database_persistence=false`, `apk_upload=false`, `direct_apk_upload=false`, `analysis_persistence=false`, `android_execution=false`, `worker_dispatch=false`, and `network_shaping=false`. Risk planning, personas and stateless log analysis remain available. Authentication is configured. The main capability payload incorrectly advertised TTS and run comparison as enabled despite missing provider/database dependencies; this branch corrects those capability flags. That is correct security behaviour, but it means the full customer journey is not presently enabled.

## Repository and delivery baseline

| Check | Finding | Classification |
|---|---|---|
| Repository | Public `kaustubhdua/Bharat-Sim`; default branch `main`; connected account has push permission | Verified |
| Main SHA | `4a1381db9d21e05a5f351bdac5d5710377839c1c` (2026-11-21) | Verified |
| Branch inventory | Numerous feature/fix/docs branches exist; branch names and heads were inspected. A branch existing is not proof it is merged or current. | Reviewed |
| PR inventory | PRs through #130 inspected; #130 merged 2026-11-03. Latest relevant integration PRs #126/#127 merged 2026-11-02. | Reviewed |
| CI on audited main | Run #44907739421 completed 2026-11-21: backend, frontend build, PostgreSQL integration, worker guards, container build and unified build passed; Playwright E2E had 11 passing tests and one failure in the submitted-log analysis journey (the results heading did not appear after submission). | Mixed; E2E blocker |
| Dependency audit | Run #44906460952 completed successfully 2026-11-21; Python and JavaScript dependency jobs succeeded. | Verified on audited main |
| Android emulator CI | Latest main emulator smoke #44907739403 failed during the Appium/UiAutomator2 primary-action journey with a stale element reference. The fixture traffic-path setup and proxy checks passed before the UI action failure. This branch adds locator re-resolution and retry tests. | Earlier fixture only; current run unverified |
| Main deployment status | Vercel status for audited SHA `5ab14c8` reports deployment completed successfully. This proves provider deployment status, not live application health or full product readiness. | Deployment reported successful |
| Current live HTTP | Production homepage returns HTTP 200; `/api/v1/personas` and `/api/v1/capabilities` return 200. `/health/ready` returns 503: database and private storage unavailable, worker not configured, execution disabled. Preview deployment returns the same readiness result. | Runtime inspected; not ready |

## Feature audit

Legend: **Working (bounded)** means code and automated evidence support the stated scope, not unrestricted production use. **Partial** means a narrower implementation exists than the requested product capability.

| Area | Status | Evidence / gap |
|---|---|---|
| React/Vite application shell | Working (bounded) | Single application shell and client-side routes in `frontend/src/App.tsx`. |
| Landing page | Partial | Current root route is an authenticated workspace/overview, not a separate public marketing landing page with product narrative, FAQ and conversion flow. |
| Authentication | Partial | Supabase password sign-in/sign-up, refresh, sign-out and session persistence exist in `AuthGate.tsx`/`auth.ts`. Password reset, email-verification resend and a dedicated reset flow are not evidenced. Live provider configuration and production sign-in remain unverified. |
| Guest preview | Working (bounded) | Explicit UI-only guest mode; personas and risk planning are public. Private run, worker and report endpoints are intentionally not called. |
| Overview dashboard | Partial | Live persona count, API/capability/worker status, runs and latest log-analysis signals are shown. It is not a historical observability dashboard with persisted time-series metrics and charts. |
| APK validation/intake | Working (bounded) | API validates APK-like ZIP metadata and size; frontend supports direct signed resumable upload when capability is enabled. Production storage credentials are absent per latest checked-in operational audit. |
| APK metadata | Partial | APK parser/metadata validation exists; the frontend flow does not establish a rich metadata inspection and upload library experience. |
| Persona profiles | Working (bounded) | API-backed predefined profiles and selection are implemented. Profiles are configuration targets, not measurements from a representative physical-device fleet. |
| Risk planner | Working (bounded) | Public planning and configurable scenario hypotheses exist. A plan is not an executed test. |
| Test configuration | Partial | APK/persona run registration exists. Requested rich scenario builder, baseline/constrained paired run orchestration and full telemetry controls are not demonstrated as an end-to-end product workflow. |
| Live execution | Partial | Lease-based worker states, heartbeats, polling and event timeline exist. No live isolated production worker is attested; UI should not be interpreted as a hosted emulator console or real-time stream. |
| Run history | Partial | Owner-scoped history, search and status filters exist. Production persistence is currently unavailable according to release evidence; pagination/date/persona filters are not established. |
| Run detail/evidence | Working (bounded) | Detailed run evidence, smoke steps, condition application/readback, events and JSON report download are implemented. Detail quality is limited by actual worker evidence and inline artifact model. |
| Findings | Working (bounded) | Deterministic signal detection, severity, source-line evidence, Failure DNA grouping and conservative evidence fusion exist. Root-cause statements remain hypotheses. |
| ML failure classification | Partial | Main contains a portable TF-IDF weighted class-centroid classifier trained on 58 curated examples. The trainer calculates accuracy on those same training examples; the reported 100% is resubstitution, not independent holdout evidence. Model registry and external validation are absent. |
| ML anomaly detection | Partial | Baseline/constrained comparison uses fixed metric thresholds and a hand-coded reference z-score. It is not IsolationForest or a trained ML model. Only persisted metrics present in both runs are valid inputs. |
| Report export | Partial | JSON export exists for log analysis and worker run reports. PDF export is not evidenced. |
| Sarvam translation | Partial | Server-side Sarvam text translation supports Hindi, Tamil and Marathi; English is the source language. A limited deterministic fallback exists for common summaries; real provider translation requires the server-only API key. |
| Audio generation/playback | Partial | PR #131 aligned the Bulbul TTS response contract and the player refuses silent fixture WAVs. The live capability payload still advertises TTS while `SARVAM_API_KEY` is absent; this branch gates the capability and disables the voice control until the provider is configured. |
| Evaluator quick tour | Partial | Curated scenario fixture endpoint/component exists. The endpoint returns an `items` envelope while the original frontend expected `scenarios`, and the banner was not mounted. This branch corrects the response contract, mounts it and labels scenario content as fixtures. |
| Run comparison | Partial | Modal and endpoint exist, but audited main queried a non-existent `report_json` column, lacked owner scoping, substituted invented metrics and returned a mismatched nested contract. This branch corrects these issues and refuses comparisons without shared persisted telemetry. |
| Settings | Missing | No dedicated settings route for profile, security, notifications, language or account management was found. |
| Theme | Working (UI) | Merged PR #131 adds navy/graphite/electric-blue tokens, a persisted light/dark toggle and pre-paint theme bootstrap. User-level server profile sync is not implemented. |
| Responsive design | Partial | Responsive CSS exists, but breakpoint-by-breakpoint verification at the requested 360–1920px widths was not performed. |
| Motion system | Partial | CSS transitions and loading indicators exist. No consistent route-transition/motion system or reduced-motion audit is established. |
| Accessibility | Partial | Some labels, live regions, focus styling and semantic elements exist. Full keyboard, screen-reader, contrast and reduced-motion audit is outstanding. |
| API integration | Working (bounded) | Central API helpers and typed domain contracts exist; backend capabilities gate operations. |
| Database migrations | Working (CI verified) | Supabase migrations and PostgreSQL clean-database integration path exist; CI migration/restart persistence suite passed on audited main. Live production DB is not configured/verified. |
| Tenant isolation | Implemented; live proof outstanding | JWT verification, owner scoping, private schema/storage design and regression tests exist. Production Auth/DB cross-user verification remains a release gate. |
| Android worker | Working (fixture/local scope) | Authenticated polling, leases, heartbeats, ADB install/launch, bounded monkey exploration, logcat, gfxinfo jank and meminfo PSS collection, callback and cleanup logic exist. It does not capture all requested metrics (notably startup latency) and is not a sandbox. |
| Network shaping | Partial / environment-dependent | Controlled CI fixture and Linux netem checks exist. Arbitrary APK traffic and all requested network controls are not established. Packet loss/CPU/RAM fidelity have documented limitations. |
| Worker isolation | Missing in production | Firecracker/KVM per-job isolation, default-deny egress, resource limits and cleanup attestation are not provisioned/verified. Execution flags must remain false. |
| Performance | Partial | Vite production build and test infrastructure exist. No current Lighthouse/Web Vitals, bundle budget, mobile performance or large-log virtualization evidence was found. |
| E2E testing | Blocked by current regression | Playwright dashboard E2E exists. On audited main SHA, 10 tests failed and 2 passed because assertions timed out waiting for the API-connected UI state; exact root cause is not yet isolated. Earlier CI passed on 2026-11-08. |
| Security tests | Working (bounded) | Backend security, upload, worker protocol, auth and dependency audit suites exist. A passing dependency audit is not a penetration test or production security certification. |
| Production deployment | Provider reports success; runtime unverified | Vercel reports a READY production deployment for audited SHA `529d308`. The public site was not independently fetched and production database/storage/worker readiness remains unverified. |

## Frontend route and interaction inventory

Observed routes/components:

- `/` — workspace overview; persona selection, APK upload, risk planner, logcat analysis, recent runs, capability/readiness panel.
- `/runs` — owner-scoped test history with client-side search and status filter.
- `/runs/:id` — run detail, event timeline, evidence and JSON report download; delete is guarded by confirmation and active-execution checks.
- `/analysis` — heuristic log-analysis report, findings, BharatScore limitations, Sarvam translation and JSON export.
- `/analyses` — compatibility redirect to `/analysis`.
- Unknown routes — not-found state.
- `AuthGate` — Supabase sign-in/sign-up and guest preview gate.

The brief's standalone marketing landing page, dedicated upload library, separate execution console, dedicated findings/history/report/settings pages and account recovery pages do not currently exist as distinct routes. Some capabilities are composed into the overview or detail views.

### Interaction inventory (observed)

| Control / location | Behaviour | Dependency | Result / coverage |
|---|---|---|---|
| Brand/home navigation | Navigate to overview | React Router | Implemented |
| Overview / runs / log analysis navigation | Route change | React Router | Implemented |
| Refresh buttons | Refetch personas, capabilities, runs, workers | FastAPI | Implemented; disabled while initial loading |
| Persona selection | Select profile for planner/run | React state/API persona list | Implemented |
| APK file selection/upload | Validate capability, sign/resume upload or multipart submit, register run | FastAPI + Supabase Storage when enabled | Implemented conditionally; production blocked by persistence/storage capability |
| Risk planner controls | Build risk plan | FastAPI planner endpoint | Implemented; planning is not execution |
| Log analysis form | Submit pasted log text | FastAPI analysis endpoint | Implemented; authenticated scope in production |
| Run search/status filter | Filter loaded runs by name, id, hash, persona, status | Client-side data | Implemented; no server pagination evidenced |
| Run detail refresh | Fetch detail and events; poll active run | FastAPI | Implemented |
| Run report download | Download JSON | FastAPI report endpoint | Implemented |
| Run deletion | Confirm, call DELETE, navigate back | FastAPI owner-scoped delete | Implemented; active execution guarded |
| Analysis export | Download JSON blob | Browser Blob | Implemented |
| Sarvam language/translate | Request translation of condensed findings | FastAPI + Sarvam API key | Implemented conditionally; no audio |
| Auth sign-in/sign-up | Supabase Auth requests | Supabase Auth | Implemented in code; live config not verified |
| Sign-out | Remote logout best-effort + clear local session | Supabase Auth | Implemented |
| Settings, PDF, TTS, run compare, pagination, advanced filters | No corresponding complete control/flow established | N/A | Missing |

## Backend, data and security findings

- Production/serverless mode refuses to use temporary SQLite as persistent production storage.
- PostgreSQL persistence and migrations have automated clean-database and restart-persistence tests.
- Supabase Auth token verification uses the project's asymmetric JWKS and validates issuer, audience, role and user subject.
- Private APK Storage uses server-side credentials and signed upload tickets; credentials are explicitly prohibited from `VITE_*` variables.
- Worker claims use leases; stale/duplicate worker results are rejected.
- Worker protocol and ADB runner do not create an OS-level sandbox. A personal machine, shared container or Vercel function is not an acceptable public APK execution host.
- The latest checked-in release evidence (2026-11-08) says `BHARATSIM_DATABASE_URL` and `SUPABASE_SECRET_KEY`/legacy service-role key are absent from the relevant Vercel Production environment inventory; persistence and private storage consequently fail closed.
- Keep `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`, `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`, and `BHARATSIM_WORKER_EGRESS_RESTRICTED=false` until the dedicated isolation gate is independently met.
- Sarvam credentials are server-only; current integration only translates condensed report text, never raw logcat.

## Android and evidence scope

The CI Android emulator smoke is meaningful evidence: it covers a source-built fixture APK through local API intake, authenticated worker lease, ADB install/launch/logcat, callback, report persistence, negative install/invalid-APK cases and a controlled HTTPS network experiment. It does not prove arbitrary uploaded APKs can be safely executed, a real production worker exists, or physical low-end device fidelity. The runner README explicitly describes the worker as an execution prototype, not a production sandbox.

## Design assessment

Current frontend is a navy/graphite engineering workspace with restrained electric-blue accents, Manrope/DM Sans/DM Mono typography, a fixed sidebar, top bar, dense dashboard panels and responsive CSS. Merged PR #131 adds persistent local light/dark selection and pre-paint theme initialization. The overview remains a combined workflow screen rather than a complete SaaS information architecture. The overview remains a combined workflow screen rather than a complete SaaS information architecture. A proper redesign must preserve truthful capability gating and actual API data; never replace the existing live readiness card with decorative metrics or mock device activity.

Design work required:
1. Separate public marketing/preview experience from the authenticated product shell.
2. Introduce design tokens and light/dark theme persistence without theme flash.
3. Reorganize navigation around Overview, Apps/APKs, Test runs, Findings, Reports and Settings only when those screens have real backing flows.
4. Improve information density, hierarchy, responsive table treatment and accessible focus/contrast.
5. Add motion only for real transitions and respect `prefers-reduced-motion`.
6. Add visual regression snapshots at 360, 390, 768, 1024, 1440 and 1920px before claiming responsive completion.

## Release blockers (P0)

1. Provision and verify production PostgreSQL using `BHARATSIM_DATABASE_URL` (pooler/SSL as documented).
2. Provision server-side Supabase Storage credentials and verify private bucket access, signed upload completion, download and deletion.
3. Verify production Supabase Auth issuer/JWKS, email confirmation, sign-in/refresh/sign-out and owner isolation with two independent users.
4. Provision a dedicated KVM host and per-job Firecracker isolation with default-deny egress, resource limits, watchdog and cleanup evidence.
5. Deploy the exact tested commit and verify deployed SHA, public routes, health/live, health/ready and capabilities.
6. Run authenticated APK upload → worker execution → report → delete journey on a controlled fixture and prove persisted state after API restart.
7. Keep arbitrary public APK execution disabled until all security and isolation checks pass.

## Product gaps (P1)

- Dedicated marketing landing page and onboarding.
- Password reset/email verification UX.
- Real persisted dashboard trends and metrics (only after telemetry schema and production persistence are live).
- First-class APK library and metadata inspection.
- Rich test configuration and baseline/constrained comparison.
- Findings and reports as discoverable resources with backend pagination/filtering.
- PDF export.
- Sarvam TTS/audio playback only if provider capability, privacy consent and caching are implemented.
- Settings and persistent theme preferences.
- Run comparison and date/persona filters.
- Accessible mobile navigation, visual regression and reduced-motion checks.

## Latest upstream additions and critical gaps

The audited main commit `529d308` added a portable classifier, statistical comparison, evaluator scenario fixtures, Bulbul TTS endpoint/player, run-comparison UI and additional Android telemetry. These features are real code additions, but the following gaps were found during review:

- `/api/v1/runs/compare` selected a non-existent `report_json` column (the schema uses `result_json`), did not scope both rows to the authenticated owner, substituted hardcoded telemetry values when measurements were absent, and returned a nested response that did not match the frontend contract.
- The evaluator scenarios API returns `items`, while the frontend client expected `scenarios`; the banner was imported but not mounted in the overview.
- The TTS response contract differed between the frontend and backend. The no-credential backend path returns a silent fixture WAV, not spoken audio.
- The classifier's reported 100% accuracy is training-set resubstitution on 58 curated examples. It is not an independent holdout result.
- The anomaly detector's code is a statistical threshold/z-score heuristic; references to IsolationForest are inaccurate.
- The new Playwright run #44906460960 had 10 failing tests and 2 passing tests. Failures timed out waiting for the API-connected UI state; root cause remains to be isolated. The emulator smoke job on that main commit was cancelled.
- Vercel reports a completed deployment for the audited SHA, but the live site was not independently fetched in this environment.

## Remediation implemented on this working branch

- Persistent light/dark theme with pre-paint initialization, semantic navy/graphite/electric-blue styling and reduced-motion handling.
- Run comparison now uses `result_json`, completed runs only, owner-scoped lookups, real persisted metrics only, a 422 response when no common telemetry exists, and a response matching the frontend comparison contract (merged in PR #131).
- Statistical anomaly scoring is labelled and scaled as a statistical heuristic rather than IsolationForest.
- Classifier metadata now describes the actual portable TF-IDF class-centroid implementation.
- Sarvam audio contract now matches the backend response; fixture audio is explicitly rejected by the player instead of being represented as speech.
- Evaluator fixture envelope is corrected, the quick-tour component is mounted in Overview, and fixture logcat/metrics are labelled as demonstration inputs rather than executed APK evidence.

## Verification limits

No local checkout, package installation, frontend build, backend test command, browser session, screenshot capture, Vercel project environment mutation or Supabase query was performed in this GitHub connector audit. CI results cited above are historical results attached to the exact recorded commits. The live website could not be fetched in this environment. Do not describe these as tests executed during this audit.
