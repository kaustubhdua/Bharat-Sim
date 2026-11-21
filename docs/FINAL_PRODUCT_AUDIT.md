# BharatSim — current product and judge-readiness audit

**Audit date:** 22 November 2026 (IST)  
**Main SHA reviewed:** `f480592e684983040c7180be3e9010ed29d204c6`  
**Consolidation branch:** `release/judge-readiness-consolidated-2026-11-22`  
**Decision:** controlled-beta prototype with substantial implemented and CI-tested functionality; **not yet fully production-complete**.

This audit supersedes older product-status snapshots in this file. For detailed implementation status, use [Master Feature Inventory](MASTER_FEATURE_INVENTORY.md) and [Production Readiness](PRODUCTION_READINESS.md).

## 1. What judges can reliably evaluate

### Risk planner
- Category-aware API-generated risk ranking.
- Editable critical user journeys and persona selection.
- JSON export.
- It prioritizes tests; it does not execute an APK.

### Logcat analysis
- Deterministic crash/ANR/OOM/network/storage signals.
- Source-line evidence, recommendations, Failure DNA grouping and heuristic BharatScore.
- PDF and JSON export.
- Findings are triage signals, not confirmed root causes. A clean result is not proof of app health.

### Speak-to-Test
- Typed requests and optional microphone capture.
- Schema-validated test specs and server-side allowlisted scenario IDs.
- Controlled BharatPay original/fixed sample APKs.
- Live Sarvam interpretation, translation and audio require a correctly configured server-side key and a real provider response. A fixture/fallback must not be described as live Sarvam output.

### Android worker
Two modes must not be conflated:
- Default legacy smoke mode installs/launches an APK and captures bounded logcat evidence. It has a narrower set of emulator control-plane features.
- Full engine mode (`BHARATSIM_WORKER_ENGINE=engine`) runs baseline/persona passes, collects startup/frame/memory/log telemetry, uses a host proxy for latency/bandwidth/loss stalls/resets on proxy-routed traffic, and tests outage/recovery via airplane mode.

The host proxy affects only traffic using Android's system proxy. A zero-connection report means app-path shaping was not observed. CPU throttling is unsupported. RAM behavior is emulator-provisioning dependent. A completed smoke run is not a complete app acceptance test.

## 2. Latest repository verification evidence

### PR #138 base verification
- CI run [44957776493](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44957776493) passed all seven jobs: backend, PostgreSQL integration, worker guards, frontend, frontend E2E, unified build and container build.
- Android emulator smoke [44957776524](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44957776524) passed on the same code line.
- The PostgreSQL job now creates the minimal Supabase-compatible roles/storage metadata and applies every timestamped BharatSim migration from a clean database.
- The Android preflight verifies route and TCP reachability to the host proxy, not merely that Android reports an active network.

### UI cleanup consolidation
The consolidation branch combines the release-gate fixes above with the requested UI cleanup:
- Removes the capability/worker-contract panel from Overview.
- Removes the JanJeevan pack catalog from Speak-to-Test while retaining scenario lookup and the BharatPay run buttons.
- Removes pairwise test-selection hypothesis cards from the Risk Planner while retaining risk-ranked scenarios and plan export.
- Moves Platform Showcase to the first sidebar navigation position.
- Updates regression tests so the removed catalog is not expected to render, while the actual scenario run actions remain tested.
- Clarifies that full engine-mode proxy shaping and legacy smoke-mode controls differ.

The original standalone UI PR checks exposed real regression/test drift:
- A stale Speak-to-Test assertion still expected the hidden "RUNS NOW" catalog badge.
- The old PostgreSQL CI step omitted newer persona/scenario migrations.
- Playwright assertions on the old main branch referenced stale labels and mobile sidebar geometry.

The consolidation branch includes the PR #138 CI fixes and updates the stale Speak-to-Test assertion. Its own CI and Android checks must pass before merge; the earlier successful PR #138 run is not a substitute for checks on the final head.

## 3. Production infrastructure status

The latest connected read-only infrastructure audit in [Production Readiness](PRODUCTION_READINESS.md) found:

- The browser `VITE_SUPABASE_URL` reference and the Supabase project available to the connected account did not match.
- The available `common 1` project contains both `bharatsim` and `genomeguard` schemas. It is shared; do not blindly apply BharatSim migrations there.
- Its migration history and live `bharatsim.runs` schema lag the repository's newer persona/scenario/worker migrations.
- Vercel contains masked database/Supabase environment entries, but the actual server-side targets and connectivity were not verified. No secret values were read.
- Production flags remain fail-closed: public APK execution false, worker isolation attestation false and worker egress restriction false.
- The connected Render workspace showed legacy API/web services, not a dedicated isolated Android worker.
- No live production private-Storage upload/download/delete round-trip or two-account tenant-isolation matrix has been accepted.

**Do not change the shared database or enable public execution as a shortcut.** Confirm the authoritative project, backup plan and ownership before applying migrations.

## 4. Feature classification

| Area | Current status | Remaining acceptance |
|---|---|---|
| Auth | Implemented in code | Live signup/confirmation/login/refresh/logout/recovery |
| Tenant isolation | Owner checks and RLS migrations implemented | Two real accounts; cross-user denial for every route and artifact |
| PostgreSQL | Adapter and full migration chain CI-tested on PR #138 base | Confirm production target and verify live read/write across invocations |
| APK intake | Validation, SHA-256 and signed/resumable upload code | Private bucket lifecycle and retention round-trip |
| Worker protocol | Lease, heartbeat, hash-bound download and result callback | Live worker deployment, revocation, concurrency and recovery |
| Legacy smoke worker | Implemented and emulator-CI tested | Dedicated restricted host and real user APK journey |
| Full engine worker | Implemented baseline/persona, telemetry and proxy shaping | Isolated worker deployment and repeated app-specific data-plane verification |
| Risk planner | Implemented and API-backed | Fresh final-branch browser verification |
| Log analysis | Implemented deterministic analysis | Authenticated live journey, adversarial-input review and persistence |
| Failure DNA | Implemented signature grouping | Stability across repeated runs and versions |
| ML classifier | Two inference paths exist | Independent labels, external holdout, calibration and confusion matrix |
| Anomaly detector | Threshold + fixed-reference z-score heuristic | Missing-data policy and repeated-run validation |
| BharatScore | Heuristic summary | Publish weights/thresholds and validate against controlled runs |
| Speak-to-Test | Schema validation and fixture path implemented | Live provider credentials and end-to-end deployed execution |
| FixProof | Comparison workflow implemented | Same scenario, two real completed runs with persisted evidence |
| Sarvam | Provider integration and live evidence artifact | Production endpoint/credential/quota/audio verification |
| Reports/history | Run details and client-side PDF/JSON export | Durable report library, retention, pagination and filters |
| Accessibility | Responsive and reduced-motion support | Manual keyboard, screen-reader, contrast and focus audit |
| Deployment | Unified Vercel build configuration | Exact merged SHA deployed; readiness and authenticated production smoke |

## 5. Must-fix release gates

1. Reconcile Auth/Storage browser project and backend PostgreSQL target; protect GenomeGuard-owned data.
2. Apply reviewed migrations to the confirmed BharatSim production database and prove persistence.
3. Verify private APK upload, hash, worker download, signed retrieval, deletion, expiry and retention.
4. Complete real two-user authorization tests for runs, reports, analysis and artifacts.
5. Deploy and independently attest a per-job isolated Android worker with default-deny egress, resource limits and cleanup.
6. Complete a real authenticated APK → worker → report → reopen/export journey.
7. Verify engine-mode network conditions and repeated Failure DNA/FixProof evidence.
8. Independently validate ML/anomaly/BharatScore claims.
9. Verify Sarvam production behavior if included in judge claims.
10. Complete accessibility review and deploy the exact merged SHA.

## 6. Safe judge-facing language

- “BharatSim provides deterministic Android logcat analysis with source-line evidence.”
- “The risk planner creates explainable test priorities; it does not execute tests.”
- “The legacy worker performs a bounded Android smoke workflow; the full engine performs baseline/persona testing when explicitly configured.”
- “The engine proxy shapes traffic that uses Android's system proxy; arbitrary APK traffic may bypass it.”
- “CPU throttling is unsupported; RAM behavior depends on emulator provisioning.”
- “ML, Failure DNA, anomaly and BharatScore outputs are triage evidence, not certified diagnoses or field-accuracy guarantees.”

**Release decision:** no-go for public arbitrary APK execution until production persistence, tenant isolation, private storage, per-job worker isolation and egress controls pass independent acceptance.
