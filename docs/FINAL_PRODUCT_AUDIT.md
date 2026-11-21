# BharatSim — Final Product Audit

**Production URL:** https://bharat-sim-81g2.vercel.app  
**Repository:** https://github.com/kaustubhdua/Bharat-Sim  
**Audited main SHA:** `2c754dcb428fdbacc67da18d41fad3c1d0745c83`  
**Working branch:** `fix/accurate-capabilities-and-product-evidence`  
**Audit date:** 2026-11-21 (IST)

## 1. Executive assessment

BharatSim now has a substantially broader SaaS interface than the original dashboard: a product landing page, dashboard overview, test-configuration wizard, run comparison, run details, log analysis, evaluator fixtures, and settings. PR #131 was merged before the latest UI integration commit.

The product is **not production-ready for customer APK execution**. The live homepage has returned HTTP 200, but the production readiness endpoint returned HTTP 503. The latest main commit `2c754dc` also has a failed Vercel build. The last successful production deployment is an earlier commit; it does not prove the current main commit is deployable.

This audit distinguishes implemented code from verified runtime behavior. Fixtures, static profile definitions, training-set results, provider fallbacks and CI-only emulator evidence are not represented as live customer execution.

## 2. Live production and deployment evidence

| Check | Observed result | Classification |
|---|---|---|
| Production homepage | HTTP 200 on the last successful production deployment | Responding |
| `/api/v1/personas` | HTTP 200 | Available |
| `/api/v1/capabilities` | HTTP 200 | Available, but the audited main payload over-reported some capabilities |
| `/health/ready` | HTTP 503 | Not ready |
| Production database persistence | `false` in the live capability response | Unavailable |
| Private APK storage / upload | `false` | Unavailable |
| Android execution / worker dispatch | `false` | Disabled |
| Network shaping | `false` | Not enabled for production runs |
| Sarvam translation | `false` | Provider key not configured |
| Vercel deployment for main `2c754dc` | Build failed in `python build_frontend.py` | Failed |
| Main CI run `44908756056` | Backend, PostgreSQL integration and worker guards passed; frontend, unified build and container build failed; E2E had a failing analysis journey | Mixed / blocked |
| Dependency audit | Completed successfully; 0 vulnerabilities reported by the Vercel build's npm audit | Passed |

The Vercel build log identifies TypeScript errors in `frontend/src/App.tsx`: unused `Moon`, `Sun` imports and an unused destructured theme state. This branch removes the obsolete App-local theme state and consolidates theme handling in a shared provider.

The last main-branch Android emulator smoke run failed on an Appium/UiAutomator2 stale-element reference during the primary-action journey. This branch adds locator re-resolution and retry coverage.

## 3. Feature classification

| Area | Classification | Evidence and limitation |
|---|---|---|
| Supabase email/password auth | Implemented; live user journey not independently verified | Sign-in, sign-up, session refresh and sign-out code exist. Real-user/two-tenant production verification remains outstanding. |
| Password reset / verification UX | Partial | Auth API support exists, but a complete, polished recovery and resend flow is not delivered. |
| Tenant isolation / RLS | Implemented in migrations; production verification blocked | Owner-scoped API queries and RLS policies exist. Live PostgreSQL is unavailable, so do not claim production RLS verification. |
| APK validation | Implemented in code | Client/server validation and metadata extraction exist; production upload is disabled by unavailable database/storage. |
| Private APK storage | Awaiting external infrastructure | Signed upload flow exists; production storage capability is false. |
| Persona catalogue | Working | API returns configured profiles. A profile describes requested settings; it is not proof that every constraint was applied. |
| Test registration | Partial / production disabled | Registration code exists, but production database and worker prerequisites are unavailable. |
| Android install / launch | Implemented in runner; production execution disabled | ADB install and launch logic exists. No production worker is registered. |
| Monkey exploration | Implemented in runner | Bounded UI exploration exists; it is not an isolated per-job sandbox. |
| Gfxinfo / meminfo telemetry | Implemented in runner | Jank and PSS collection code exists. These values only exist for runs where the worker actually captured them. |
| Network latency / bandwidth | Partial | Emulator controls include set/readback and CI exercises a bounded fixture proxy. Production device traffic fidelity is not verified. |
| Packet loss / outage / CPU shaping | Unsupported / not verified | Do not advertise these as applied constraints. |
| Run comparison | Implemented in code; gated by this branch | PR #131 fixed the `result_json` query, owner scoping, completed-run checks and measured-metric-only comparison. This branch disables the feature when persistent database capability is false and filters selectors to completed runs. |
| Logcat analysis | Working as a stateless API feature | Analysis endpoint and evidence-linked findings exist. The Playwright analysis-screen journey remains a failing test and is being instrumented with response/body and browser-error diagnostics. |
| ML failure classifier | Partial | Portable TF-IDF class-centroid classifier trained on a small curated set (58 examples). Reported 100% accuracy is resubstitution on the training set, not independent holdout accuracy. |
| Anomaly detection | Partial | Explicit metric thresholds and a pure-Python z-score heuristic; not IsolationForest or a validated multivariate ML model. |
| Evaluator quick tour | Working as a fixture experience | Curated scenarios are sample logcat/metrics, not APK executions or authentic device evidence. |
| Sarvam explanation | Partial | Remediation explanations use deterministic rule-based templates; they are not generative Sarvam root-cause analysis. |
| Sarvam translation / Bulbul TTS | Awaiting provider credentials | Server endpoints exist. Real provider output requires server-side `SARVAM_API_KEY`; silent fixture WAVs must never be represented as speech. |
| Landing page | Implemented; copy corrected on this branch | Public route and product preview exist. Preview data is labelled as illustrative; unsupported performance and network claims are removed. |
| Dashboard | Partial | Uses API run/worker/persona data. This branch removes the fabricated default readiness score and labels fallback persona definitions. |
| Test configuration wizard | Partial | APK selection/validation and upload capability gating exist. Worker settings not accepted by the run API are now read-only and explicitly identified as fixed defaults. |
| Run detail / history | Partial | Existing run detail and history flows exist; complete server-side pagination, date/persona filters and full compare/report workflows remain incomplete. |
| Findings / Reports | Partial | Findings are available through analysis/run evidence. Dedicated resource pages and full PDF export are not delivered. |
| Settings | Partial | Theme and language preferences are local. Account, quota, RLS, storage, worker and TTS status are now displayed from actual capability data or explicitly marked unverified. |
| Theme | Implemented on this branch | Shared ThemeProvider, persistent light/dark selection, pre-paint bootstrap and browser theme-color synchronization. |
| Accessibility / motion | Partial | Reduced-motion and focus treatments exist; full WCAG audit and screen-reader journey are outstanding. |

## 4. Recent UI integration review

The latest main integration added:
- Public landing page and product preview.
- Dashboard overview and dedicated test wizard.
- Run comparison view and settings view.
- Sidebar/topbar navigation and theme context.

The review found misleading or inert UI that this branch corrects:
- Removed the hardcoded readiness score of 85 when no report exists.
- Replaced fabricated landing-preview jank, memory and confidence values with “available after a real worker run”.
- Removed unsupported claims about 8% packet loss, CPU throttling and 100% holdout classifier accuracy.
- Made the public landing route accessible before sign-in and made its planner CTA enter the explicit UI-only preview.
- Replaced fake account UUID, quota, “RLS enforced”, “TTS online” and storage claims with capability-backed or explicitly unverified states.
- Made unsupported per-run worker overrides read-only and explained that the current API does not accept them.
- Restricted comparison selectors to completed runs and disabled comparison when persistent database support is unavailable.
- Consolidated theme state into one shared provider so the topbar and settings view cannot drift.

## 5. Current branch remediation

This branch includes:
- Capability flags: TTS/translation require a configured server-side Sarvam key; run comparison requires persistent database availability.
- Voice controls check the actual capability endpoint and remain disabled when TTS is not configured.
- Telemetry percentage parsing accepts unit-suffixed values such as `90 MB`.
- Appium smoke actions re-resolve stale UiAutomator2 elements and retry; unit tests cover click and text-read recovery.
- Playwright analysis tests assert the actual POST response shape and capture browser errors/body text if the result route fails.
- Public landing access and preview activation work without creating an API identity.
- Accurate product copy and status surfaces replace synthetic metrics and unsupported claims.

## 6. Release blockers

These are not code-only tasks and cannot be truthfully marked complete from this chat:

1. Provision and verify production PostgreSQL and private Supabase Storage.
2. Verify Auth, RLS and owner isolation with separate real passenger/tenant identities.
3. Provision an isolated Android worker with per-job VM/container isolation, restricted egress, worker credentials, heartbeat and cleanup.
4. Verify real APK upload, installation, launch, telemetry and artifact persistence end-to-end.
5. Configure `SARVAM_API_KEY` in the server environment and verify real translation/TTS output.
6. Fix the remaining Playwright analysis-screen failure and obtain a successful Android emulator smoke run.
7. Verify the exact merged SHA builds and deploys successfully on Vercel.
8. Complete PDF export, password recovery UX, dedicated findings/reports pages, server-side history filters/pagination and persistent user settings.
9. Validate classifier performance on a held-out, independently labelled dataset and publish a model version/validation record.
10. Perform an independent security and accessibility review.

**Safety gate:** Public arbitrary APK execution must remain disabled until isolated workers, storage boundaries, tenant authorization and default-deny egress are independently verified.
