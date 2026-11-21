# BharatSim — Master Feature Inventory

**Audit date:** 2026-11-21 (IST)  
**Main baseline:** `2c754dcb428fdbacc67da18d41fad3c1d0745c83`  
**Candidate branch:** `8218bb4d30aa0cbc2d3bd6ea394415b570f9ebcb`  
**Production:** https://bharat-sim-81g2.vercel.app

## Status definitions

- **IMPLEMENTED AND VERIFIED** — passed a reproducible test on the specified SHA/environment.
- **IMPLEMENTED BUT NOT VERIFIED** — code exists; target runtime behavior has not been proven.
- **PARTIALLY IMPLEMENTED** — some behavior exists, but key lifecycle/requirements remain absent.
- **BLOCKED BY EXTERNAL DEPENDENCY** — infrastructure/provider/credentials unavailable.
- **NOT IMPLEMENTED** — no complete implementation found.
- **FAILED** — an observed test or live check failed.

## Feature matrix

This inventory records major end-user flows and backend subsystems. It is not an AST-generated enumeration of every individual JSX control. The route/control matrix is maintained in `FEATURE_INTERACTION_INVENTORY.md`.

| ID | Feature | Frontend / route | Backend / dependency | Status | Evidence and remaining work |
|---|---|---|---|---|---|
| AUTH-001 | Email/password sign-in | `AuthGate.tsx` | Supabase Auth | IMPLEMENTED BUT NOT VERIFIED | Sign-in code exists; real deployed journey not run |
| AUTH-002 | Registration / email verification | `AuthGate.tsx` | Supabase Auth / SMTP | PARTIALLY IMPLEMENTED | Sign-up exists; full verification/resend journey incomplete |
| AUTH-003 | Session persistence / refresh | `auth.ts` | Supabase token endpoint | IMPLEMENTED BUT NOT VERIFIED | Session storage/refresh code exists; expired-session acceptance outstanding |
| AUTH-004 | Logout | Sidebar/AuthGate | Supabase logout | IMPLEMENTED BUT NOT VERIFIED | Local clear fallback exists; deployed session lifecycle not tested |
| APK-001 | APK file selection / drag-drop | `UploadPanel.tsx`, `NewTestWizard.tsx` | Browser File API | IMPLEMENTED BUT NOT VERIFIED | UI implementation exists; production upload blocked |
| APK-002 | APK validation / metadata | Backend APK validation | FastAPI parser | IMPLEMENTED BUT NOT VERIFIED | Code exists; adversarial archive test coverage incomplete |
| APK-003 | APK SHA-256 / duplicate controls | App upload handler | SHA-256 / DB | PARTIALLY IMPLEMENTED | Hashing implemented; production DB unavailable |
| APK-004 | Signed/resumable private upload | `storageUpload.ts` | Supabase private Storage | BLOCKED BY EXTERNAL DEPENDENCY | Production storage capability unavailable; no live round trip |
| PERSONA-001 | Persona catalogue | Persona panel / wizard | `GET /api/v1/personas` | IMPLEMENTED AND VERIFIED | API/CI smoke returns personas; config is not evidence of applied constraints |
| TEST-001 | Test registration | New-test wizard | `POST /api/v1/runs`, DB/storage | BLOCKED BY EXTERNAL DEPENDENCY | Production DB/storage unavailable |
| TEST-002 | Baseline + constrained paired run | Run configuration | Isolated Android worker | BLOCKED BY EXTERNAL DEPENDENCY | No production worker; no production pair execution |
| TEST-003 | Run lifecycle/status polling | Run detail | Runs API/events | IMPLEMENTED BUT NOT VERIFIED | Polling code exists; no active production run |
| WORKER-001 | Worker auth / heartbeat | Worker status surfaces | Worker token + DB | BLOCKED BY EXTERNAL DEPENDENCY | Production worker not configured |
| WORKER-002 | Job claim / lease / recovery | Worker agent | Database leases | IMPLEMENTED BUT NOT VERIFIED | Worker guard tests exist; production crash/recovery unverified |
| ANDROID-001 | APK install / launch | Worker runner | ADB/emulator | IMPLEMENTED BUT NOT VERIFIED | Controlled fixture execution exists; customer APKs unverified |
| ANDROID-002 | Logcat / gfxinfo / meminfo telemetry | Run detail | ADB and Android services | IMPLEMENTED BUT NOT VERIFIED | Collection code exists; real production telemetry unverified |
| NET-001 | Latency / bandwidth constraints | Persona/worker | Emulator controls / fixture proxy | PARTIALLY IMPLEMENTED | CI fixture readback exists; arbitrary APK traffic path not verified |
| NET-002 | Packet loss / outage / CPU stress | Persona/worker | tc/netem or equivalent | NOT IMPLEMENTED | Explicitly unsupported/not enabled |
| ML-001 | Logcat failure classifier | Findings / analysis | TF-IDF centroid | IMPLEMENTED BUT NOT VERIFIED | Small curated dataset; no independent holdout evaluation |
| ML-002 | Anomaly / regression analysis | Compare | Deterministic statistical heuristics | PARTIALLY IMPLEMENTED | Not a validated multivariate ML model |
| SCORE-001 | BharatScore | Analysis / run detail | Deterministic scoring | IMPLEMENTED BUT NOT VERIFIED | Evidence-driven code; comprehensive boundaries/reproducibility not independently reviewed |
| REPORT-001 | JSON analysis export | Analysis route | Browser Blob | IMPLEMENTED BUT NOT VERIFIED | Download code exists; full generated artifact validation still needed |
| REPORT-002 | JSON run report | Run detail | Owner-scoped API report | IMPLEMENTED BUT NOT VERIFIED | API code exists; production persisted object retention not verified |
| REPORT-003 | Analysis PDF export | Analysis route | Client-side PDF generator (`pdfExport.ts`) | IMPLEMENTED BUT NOT VERIFIED | PDF generator and Vitest artifact-content/pagination tests exist; exact latest-SHA test result not separately isolated from CI yet. This is analysis PDF, not persisted run-report PDF. |
| REPORT-004 | Report library / sharing | Reports | DB/storage/share tokens | NOT IMPLEMENTED | No complete persisted report catalogue/share lifecycle |
| SARVAM-001 | Translation | Analysis route | Sarvam API key | BLOCKED BY EXTERNAL DEPENDENCY | Server credential needed; live provider call not verified |
| SARVAM-002 | Hindi/Tamil/Marathi TTS | Audio player | Sarvam Bulbul | BLOCKED BY EXTERNAL DEPENDENCY | Live speech not verified; never substitute fixture WAV |
| HISTORY-001 | Test history / filters | `/runs` | Runs API | PARTIALLY IMPLEMENTED | Client filtering exists; server-side pagination/date filters incomplete |
| COMPARE-001 | Owner-scoped completed-run comparison | `/compare` | Persistent measured reports | BLOCKED BY EXTERNAL DEPENDENCY | Code gated by DB; production persistence unavailable |
| SETTINGS-001 | Light/dark theme | Settings/sidebar | ThemeProvider/localStorage | IMPLEMENTED BUT NOT VERIFIED | Shared provider exists; exact candidate browser E2E pending |
| SETTINGS-002 | Account/language/notification persistence | Settings | User preference API | PARTIALLY IMPLEMENTED | Some browser-local preferences only |
| SECURITY-001 | Tenant authorization / RLS | Backend routes / migrations | Supabase Auth/Postgres RLS | IMPLEMENTED BUT NOT VERIFIED | Owner checks and migrations exist; live two-user verification outstanding |
| SECURITY-002 | APK isolation / egress | Worker runtime | Firecracker/KVM or equivalent | BLOCKED BY EXTERNAL DEPENDENCY | Dedicated host missing; public execution must stay disabled |
| DOCS-001 | API docs navigation | Topbar | FastAPI OpenAPI | IMPLEMENTED BUT NOT VERIFIED | Same-origin link exists in candidate; deployed URL needs confirmation |

## Production evidence

Read-only checks on the live deployment returned homepage HTTP 200, `/api/v1/capabilities` HTTP 200 and `/health/ready` HTTP 503. The readiness response reported database and private storage unavailable and no production worker configured. Therefore the primary upload → Android execution → telemetry → report journey is not currently production-verifiable.

## Coverage limitations

This matrix does not claim every JSX control has its own unique row; use `FEATURE_INTERACTION_INVENTORY.md` for navigation/control coverage. A row must not be marked verified based only on code existence or a successful build.
