# BharatSim — completion audit and judge-ready acceptance plan

**Audit date:** 2026-11-22 (IST)  
**Base commit reviewed:** `cfbb8abd`  
**Decision:** substantial controlled-beta implementation; **not yet fully production-complete**.

This audit separates source-code implementation, automated fixture evidence, live-provider configuration, and production acceptance. A route, button, API endpoint, CI fixture, or successful deployment alone does not make a feature complete.

## 1. Judge-ready user journeys

### Primary: APK to evidence report
1. Sign in with a real account.
2. Upload a valid APK through private storage; verify server-side validation, SHA-256 and APK metadata.
3. Select a persona and see which constraints are actually requested.
4. Observe queued → leased → running → completed/failed transitions from real worker heartbeats.
5. Verify install/launch on a disposable Android emulator.
6. Inspect measured Logcat, crash/ANR, startup, memory, frame and network evidence.
7. Distinguish measured, control-plane-only, report-only and unsupported conditions.
8. Reopen the persisted report and export it.
9. Verify cleanup and APK hash integrity.

**Status:** execution code and a controlled emulator fixture exist, but public production execution is not accepted. A separately provisioned and attested worker, production persistence, private storage, Auth ownership and durable artifact retention still require live acceptance.

### Secondary: Logcat to report
1. Paste real Logcat and submit it to the analysis API.
2. Inspect severity, evidence-linked source lines, findings, recommendations and BharatScore.
3. Export PDF and JSON.
4. Reopen the report and verify its persistence label is truthful.

**Status:** deterministic analysis and client-side export are implemented. Stateless/local analysis is not proof of durable server-side storage. Live authenticated lifecycle and persistence remain to be accepted.

### Supporting: risk planner
Validate category and journeys, generate an explainable API plan, export the exact JSON and confirm the UI does not claim the plan was executed.

**Status:** implemented; fresh Playwright verification is required.

## 2. Confirmed latest-main CI failures and fixes in this branch

Latest inspected main CI: [44954049465](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44954049465), commit `cfbb8abd`, 2026-11-21. Backend, frontend build, unified Vercel build, worker guards and container build passed. PostgreSQL integration and frontend E2E failed. Dependency audit passed. Android smoke [44954049500](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44954049500) failed.

### PostgreSQL migration drift
CI applied only the original core, FK-index and signed-upload migrations. Current inserts use `persona_json` and `scenario_json`, producing `UndefinedColumn: persona_json`.

**Branch fix:** create the minimal Supabase Storage bucket-metadata table in the disposable PostgreSQL service and apply every timestamped BharatSim migration in sorted order. This brings custom-persona, worker-status, scenario, large-APK and personal-worker DDL into integration tests.

### Baseline worker rejected zero-kbps arguments
The Android job failed before install because the baseline profile's `down_kbps=0` and `up_kbps=0` (unrestricted/full speed) were passed as explicit caps. The runner correctly rejects zero as a throughput cap.

**Branch fix:** the worker uses the shared persona argument translator. A zero/zero baseline sentinel emits no zero-kbps CLI override while preserving the full profile for condition planning and control-plane evidence. Packet-loss bounds remain validated. A regression test covers the sentinel.

### Frontend E2E assertions drifted from the actual UI
Five Playwright failures included an obsolete packet-loss badge, double-escaped PDF/JSON extension regexes, stale run-button text, a stale API-docs destination, and an obsolete landing-page heading/badge.

**Branch fix:** tests now target current UI labels/links and correctly match literal file extensions. They still assert API connectivity, evidence content, PDF bytes and JSON content; no unconditional pass assertions were added.

## 3. Feature inventory — what remains before full completion

| Feature | Implemented in source | Acceptance still required |
|---|---|---|
| Authentication | Supabase session/sign-in and protected workspace | Real sign-up, email confirmation, sign-in, refresh, expiry, sign-out and password recovery. |
| Tenant isolation | Owner-scoped API paths and private-schema/RLS migrations | Two-user cross-tenant read/write/delete denial for every private route and artifact on production DB. |
| Persona catalogue | API-authored profiles and custom persona UI | Measured emulator readback per profile; never equate profile targets with physical-device measurements. |
| Risk planner | Deterministic category/journey ranking and JSON export | Fresh E2E and continued separation of planning from execution. |
| Logcat analysis | Deterministic signals, source-line evidence, severity, recommendations and score | Malformed/large/adversarial logs, Unicode, redaction, multi-signature and authenticated-access tests. |
| PDF/JSON export | Browser-side report export | Stable schema, long/Unicode reports, file-content checks and export after session restoration. |
| APK intake | Validation, metadata, SHA-256, signed/resumable/chunked upload code | Live private Storage upload/verify/download/delete, size and interrupted-upload tests. |
| Run registration/history | PostgreSQL adapter and lifecycle/ownership code | Apply reviewed migrations to the intended DB; prove CRUD across API restarts. |
| Worker claiming | Token auth, lease, heartbeat and result callbacks | Expired leases, stale/duplicate callbacks, revocation, ownership and concurrent claims. |
| Personal laptop worker | Key creation/revocation UI and Windows/macOS/Linux installers | Real OS install/uninstall, rotation/revocation, owner-only claims and safe cleanup. A laptop is not a multi-tenant sandbox. |
| Android execution | ADB install/launch, bounded exploration, Logcat, memory/frame/startup capture and cleanup | Green emulator E2E; multi-APK, failure, timeout, process-tree cleanup, reset and artifact retrieval tests. |
| Engine worker | Baseline/persona engine, shaping proxy and measurements | Prove production uses engine mode; do not conflate legacy smoke runner with full engine. |
| Network simulation | Emulator latency/bandwidth controls with readback; proxy code for additional shaping | Measure app data-plane traffic for every claimed condition. Keep packet loss/outage/reset unsupported unless worker evidence proves them. |
| RAM/CPU | RAM reported; CPU throttling not implemented | Do not claim dynamic RAM/CPU throttling without a safe measured implementation. |
| Storage/battery controls | Bounded emulator controls and cleanup evidence | Low-space safety, pre-satisfied target, interrupted cleanup and emulator discard tests. |
| Failure DNA | Deterministic signature grouping/evidence fusion | Stable fingerprints across repeated runs/versions; similarity is not confirmed root cause. |
| ML classifier | Local TF-IDF classifier path | Independently labelled holdout, leakage-free validation, per-class metrics, confusion matrix and model version. Training fit is not field accuracy. |
| Anomaly detection | Statistical/threshold logic | Document formulas, minimum samples, missing-data behavior and confidence; don't call heuristics trained ML. |
| BharatScore | Transparent heuristic score | Publish weights/formula/missing-evidence treatment; verify fixtures; don't call it certification. |
| Sarvam / Speak-to-Test | Provider integration and capability-gated UI | Server-only key, real speech-to-text, structured-plan validation, translation/audio and outage/rate-limit tests. |
| FixProof | Route and old/new evidence workflow | Same scenario and comparable measured assertions on two completed builds. |
| Run comparison | Owner-scoped completed-run comparison | DB-backed history, shared measured metrics, missing telemetry and cross-user denial. |
| Reports/history/settings | Routes and components | Durable report library, pagination/filtering, artifact lifecycle, persistent preferences and account recovery. |
| Accessibility/responsive | Responsive layout, theme, reduced-motion support | Keyboard, screen-reader, contrast, focus, reduced-motion and small-screen manual audit. |
| Deployment | Vercel project and Render URL referenced | One canonical origin; exact release SHA deployed; frontend/API pairing, readiness and deployed browser E2E verified. |

## 4. Infrastructure and data gates

These cannot be closed by source changes alone.

1. **Choose the authoritative Supabase project.** The connected project inspected is `common 1` (`hkyieaovolkethovyenb`), shared with GenomeGuard. The Vercel environment inventory also contains a browser Supabase URL with a different project reference. Confirm exact project IDs behind server-side `SUPABASE_URL`, `BHARATSIM_DATABASE_URL` and browser `VITE_SUPABASE_URL` without exposing secrets.
2. **Do not run `supabase db push` blindly against common 1.** The live schema inspection did not show latest `persona_json`, `scenario_json` and personal-worker columns. Apply migrations only after confirming the target, backup and review with the owner of the shared GenomeGuard DB.
3. **Verify server-only credentials.** A non-decrypted Vercel environment inventory is not proof of connectivity. Confirm the PostgreSQL pooler URL, TLS mode and server-only Supabase secret in the correct Production scope. Never put server secrets in `VITE_*`, source control, screenshots or chat.
4. **Prove persistence and Storage.** `/health/ready` must report actual connected dependencies. Create/read/delete a run across separate invocations; upload, hash-verify, download and delete a private APK; verify cleanup.
5. **Provision an isolated worker host.** A personal laptop worker is useful for controlled private testing but does not replace disposable VM-grade isolation for untrusted public APKs. Require default-deny egress, quotas, per-job isolation, process-tree cleanup, patched emulator images, signed worker identity, lease expiry and artifact retention.
6. **Keep public APK execution disabled** until isolation, ownership, abuse controls, storage boundaries and worker attestation are independently demonstrated.

## 5. Evidence required for judge-ready release

- [ ] Green CI: backend, PostgreSQL with all migrations, worker guards, frontend build/E2E, unified deployment build and container smoke.
- [ ] Green Android emulator workflow with evidence artifact: install/launch/logcat, measured persona readback, cleanup and negative cases.
- [ ] Real authenticated journeys for primary and secondary flows.
- [ ] Two-user authorization report proving cross-tenant denial for every private route/artifact.
- [ ] Production DB and private Storage round-trip evidence.
- [ ] Worker isolation/egress attestation plus lease/revocation/cleanup evidence.
- [ ] Live Sarvam evidence if those features are claimed to judges.
- [ ] Independent ML holdout validation and documented BharatScore/anomaly methodology.
- [ ] Browser E2E and manual responsive/accessibility review on deployed origin.
- [ ] Release notes, limitations, architecture, API contract and demo script updated to exact release SHA.

## 6. Judge-facing claim language until acceptance

- "BharatSim provides deterministic Android Logcat analysis with source-line evidence."
- "The risk planner generates explainable test priorities; it does not execute tests."
- "The Android worker can execute a controlled APK fixture in CI; arbitrary public APK execution is not enabled."
- "Latency/bandwidth control readback is distinct from proof that arbitrary app traffic traversed the shaped path."
- "RAM is measured/reported, not dynamically restricted; CPU throttling is unsupported."
- "ML and anomaly outputs are triage signals, not confirmed root causes or production field-accuracy guarantees."

Do not describe the project as fully production-ready until the acceptance evidence above exists. This is an engineering release gate, not a judgement of the project's potential.


## 7. Follow-up live inventory — 22 Nov 2026

This section records read-only inspection of the connected Vercel, Render and Supabase control planes. It does not claim that masked credentials were tested or that production configuration was changed.

### Supabase project identity and migration drift

- The Vercel project `bharat-sim-81g2` has a Production/Preview browser variable `VITE_SUPABASE_URL` pointing to project reference `gpkyzastnibffyuxhtix`.
- The Supabase account currently connected to this audit exposes a different active project, `common 1` (`hkyieaovolkethovyenb`). The browser project reference is not in the connected account's project inventory, so the browser Auth/Storage target cannot be reconciled from this connection alone.
- The active `common 1` database contains both `bharatsim` and `genomeguard` schemas. Its migration history includes the BharatSim core, FK indexes, private APK bucket and signed-upload-size migrations, but not the five newer BharatSim migrations currently in the repository (custom persona, worker claiming/status, run scenario, large APK parts, personal workers).
- The live `bharatsim.runs` table does not currently expose the `persona_json` and `scenario_json` columns expected by the newer code path. The live worker table also predates the newer worker-claiming fields.
- Vercel metadata confirms a Production `BHARATSIM_DATABASE_URL` entry and server-side `SUPABASE_URL` entry exist, but their values were deliberately not retrieved. Their actual targets and connectivity remain unverified.

**Decision:** Do not apply the five pending migrations to `common 1` until the owner confirms that it is the intended BharatSim database and approves a backup/restore plan. It is shared with GenomeGuard; a blind migration push could affect another product. First reconcile the browser Auth/Storage project with the backend database target.

### Production execution and worker gates

Vercel's non-secret Production/Preview configuration currently records:
- `BHARATSIM_ENV=production`
- `BHARATSIM_AUTH_REQUIRED=true`
- `BHARATSIM_STORAGE_BUCKET=bharatsim-private`
- `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`
- `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`
- `BHARATSIM_WORKER_EGRESS_RESTRICTED=false`

These are appropriate fail-closed settings while production worker isolation and egress evidence are absent. Do not flip them to enable public APK execution as a shortcut.

The connected Render workspace still has legacy `bharatsim-api` and `bharatsim-web` services deployed from `main`; the latest recorded API deployment is from 2 Nov 2026. No dedicated Android worker service is present in the listed Render services. Treat those as legacy split services, not proof of the current unified Vercel release or of a production emulator worker.

### Latest Android CI failure and correction

The Android smoke workflow on PR head `7ca29fa1` completed with failure in the Appium traffic journey. The API worker successfully registered and completed the controlled APK smoke run; the later Appium fixture then failed when the Android app attempted to connect to host gateway `10.0.2.2:8888`, receiving `ENETUNREACH`.

The preflight previously treated an active ConnectivityManager transport as sufficient readiness. That is weaker than proving the emulator can route to the host and reach the proxy.

**Branch correction:** `prepare_proxy_path()` now requires (1) an active Android transport, (2) an IP route to `10.0.2.2`, and (3) a successful TCP connection to `10.0.2.2:8888` before Appium begins. Regression tests cover delayed route/proxy readiness. The rerun must pass before this gate can be closed.

### Other acceptance evidence that is still absent

- **Private APK retention:** unit tests cover signed resumable upload behavior and tampered URL rejection; no production private-bucket upload → hash verify → signed download → delete round trip has been accepted.
- **Tenant isolation:** source-level owner checks and RLS exist, but no live two-account matrix has proved cross-user read/write/delete denial across run history, reports, artifacts and signed URLs.
- **Sarvam:** the repository contains a 21 Nov live evidence artifact showing non-fallback Sarvam interpreter responses for Hindi, Hinglish, Tamil and English inputs, plus Bulbul TTS and Saaras STT round-trips for Hindi/Tamil. This is meaningful provider evidence, but it does not by itself verify the production report-translation endpoint, deployed credential scope, quota/rate-limit behavior or ongoing availability. Fallback fixtures must be labelled as fallback, not real Sarvam output.
- **ML classifier:** the worker model has a reported 5-fold GroupKFold evaluation over 9,140 mixed samples, with holdout accuracy 0.7843 and macro-F1 0.7707 (per-class F1 ranges from 0.5865 for ANR to 0.8889 for storage). The training notes explicitly disclose LogHub weak-rule labels plus templated failures and state that these scores are not field accuracy. Independently audit label quality/group leakage, publish a separately labelled external holdout and confusion matrix, and test calibration before presenting these numbers as real-world accuracy. The backend's separate pure-Python centroid/softmax model also needs its own evaluation.
- **Failure DNA and FixProof:** repeat-run stability and same-scenario before/after comparison need persisted, completed runs and evidence-based acceptance; UI availability alone is insufficient.
- **Accessibility:** automated responsive assertions are not a substitute for keyboard-only, screen-reader, contrast, focus-order and reduced-motion manual review.



## Addendum — personal laptop worker workflow on current main (22 Nov 2026)

The latest main line now includes per-user laptop workers:
- Personal worker keys are scoped to a signed-in owner; only a hash is stored server-side and the key is shown once.
- The account can connect up to three laptops and revoke an individual laptop key.
- Windows and macOS/Linux installers set up a private Python 3.12 environment, Java 17, Android SDK/Android 11 emulator and a lab supervisor.
- The supervisor restarts the emulator/worker and defaults to `BHARATSIM_WORKER_ENGINE=engine`.

This is a useful judge/demo path for a user's own laptop and owner-scoped jobs. It does **not** establish per-job isolation from the laptop owner, host compromise resistance, default-deny egress, or production multi-tenant safety. The installers currently download the repository's main-branch worker bundle; pinned release provenance, installer checksums/signatures, update/rollback and full Windows/macOS/Linux acceptance remain follow-up work. Keep public arbitrary APK execution disabled until the separate production isolation gates pass.


## Addendum — fresh read-only production configuration check (22 Nov 2026)

The Vercel Production environment-variable inventory was re-read without decrypting any secret values. The connected Supabase project list and the active `common 1` database were also inspected read-only.

### Vercel environment metadata
- `VITE_SUPABASE_URL` points to `https://gpkyzastnibffyuxhtix.supabase.co`.
- The connected Supabase account's project list does not contain project ref `gpkyzastnibffyuxhtix`; the only `ACTIVE_HEALTHY` project in that list is `common 1` (`hkyieaovolkethovyenb`). Do not assume they are the same project.
- Sensitive `BHARATSIM_DATABASE_URL` and `SUPABASE_URL` entries exist, but their values were not decrypted, so the server-side database and Storage project targets remain unverified.
- No `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY` entry appears in the complete Vercel environment listing. The backend sets `STORAGE_ENABLED` only when `SUPABASE_URL`, one of those server-side keys and the bucket name are present. Therefore the visible Production configuration does not currently demonstrate that signed private Storage uploads can be enabled.
- The Production environment has a sensitive `sarvam_api` variable. Code in `backend/app/sarvam.py` explicitly supports this lowercase compatibility alias as well as `SARVAM_API_KEY`; however, the value was not decrypted, so its validity, quota and provider availability remain unverified.
- `BHARATSIM_ENV=production`, `BHARATSIM_AUTH_REQUIRED=true`, `BHARATSIM_STORAGE_BUCKET=bharatsim-private`, and the fail-closed flags are present as plain environment metadata. Public APK execution, worker isolation attestation and worker egress restriction are all `false`.

### Active connected Supabase project — read-only observations
The active `common 1` project is shared by `bharatsim` and `genomeguard`. Its migration history contains only four BharatSim migrations, while the repository now contains nine. Missing migrations:

1. `20261121190000_bharatsim_custom_persona`
2. `20261121200000_bharatsim_workers_claiming_status`
3. `20261121230000_bharatsim_run_scenario`
4. `20261122000000_bharatsim_large_apk_parts`
5. `20261122010000_bharatsim_personal_workers`

The live `bharatsim.runs` table is missing `persona_json`, `apk_meta_json` and `scenario_json`; the live `bharatsim.workers` table has only `id`, `last_seen`, `status` and `current_run_id`, and is missing personal-worker ownership/key metadata. The shared project's private `bharatsim-private` bucket exists with a 150 MiB object limit and APK/ZIP/octet-stream MIME types, but it contains zero objects; `bharatsim.runs` also contains zero rows. This is not evidence of a successful production upload/run journey.

**No migrations, Storage objects, user rows, Vercel environment variables or secrets were changed.** The shared project must not be migrated without the owner confirming that it is the intended target and providing a backup/restore plan.
