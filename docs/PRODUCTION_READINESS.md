# BharatSim — Production Readiness

**Audit date:** 2026-11-21 (IST)  
**Candidate branch:** `d4f3605711aa51929b8148a4fee296768085776f`  
**Application code tested by green CI:** `8218bb4d30aa0cbc2d3bd6ea394415b570f9ebcb` (7/7 jobs); emulator smoke evidence on `d5684752e7f5202c83bb401bf651595290815188`  
**Production URL:** https://bharat-sim-81g2.vercel.app  
**Decision: NO-GO for public APK testing. Controlled preview only.**

## Read-only production smoke

| Check | Observation |
|---|---|
| Homepage | HTTP 200; auth/sign-in experience renders |
| `/api/v1/capabilities` | HTTP 200; prior production payload over-reported TTS/comparison vs missing dependencies |
| `/health/ready` | HTTP 503 |
| Database | Reported unavailable |
| Private Storage | Reported unavailable |
| Android worker | Not configured / offline |
| Android execution | Disabled |
| Sarvam translation | Reported unavailable |
| Sarvam TTS | Previously reported enabled on a stale deployed capability payload; this branch gates by server-side key |

## CI and deployment status

- The application-code candidate `4546d9330f24dacda803cbc887d7bd737dfd2f72` passed all seven CI jobs and the dependency audit. Subsequent changes were limited to test-report/readme documentation.
- Vercel status on the latest documentation SHA is a failed `build-rate-limit` check. This is a platform quota issue; do not claim a production deployment of the candidate.
- A production HTTP capture returned 503 from readiness and was edge-cached at 2026-11-21 14:01 UTC. It is valid evidence for that captured state, not proof that a later deployment is live.

## Gate assessment

- **Frontend:** Frontend build, TypeScript and Playwright E2E passed on application-code SHA `4546d9330f24dacda803cbc887d7bd737dfd2f72`; later commits only adjusted documentation/README.
- **Backend:** Backend pytest, unified ASGI/SPA smoke and Docker/Compose acceptance passed on application-code SHA `4546d9330f24dacda803cbc887d7bd737dfd2f72`; deployed database-backed workflow not ready.
- **Database:** Clean disposable PostgreSQL migrations/restart integration passed on parent snapshot; production persistence unverified.
- **Android:** Fixture-only emulator/worker tests exist; no production worker host and no arbitrary APK verification.
- **Network:** Limited emulator fixture control; arbitrary app traffic not proven; unsupported controls remain disabled.
- **ML:** Heuristic/class-centroid code exists; independent holdout evaluation absent.
- **Sarvam:** Provider credential required; no live output verified.
- **Security:** Dependency audit only; tenant isolation and sandbox egress need independent acceptance.
- **Reporting:** Analysis-level JSON and PDF export implementations exist. PDF artifact-content and pagination tests are included in the passing frontend CI at `8218bb4d30aa0cbc2d3bd6ea394415b570f9ebcb`; persistent report library, run-level PDF and sharing remain incomplete.
- **Performance/accessibility:** No controlled load benchmark or full WCAG audit recorded.

## Manual infrastructure actions required

1. Provision production PostgreSQL and the backend-only Supabase secret; reconcile migrations and verify health.
2. Provision private Storage and test signed upload/download/delete/retention using two actual users.
3. Configure Supabase Auth redirect, email verification and password recovery; execute real signup/login/session refresh/logout.
4. Provision an isolated disposable Android worker host with default-deny egress, resource caps, worker token, watchdog and cleanup; obtain independent attestation before enabling execution.
5. Configure backend-only Sarvam secret if translation/TTS are required.
6. Deploy a coordinated API/frontend release after exact-SHA checks pass; verify deployed SHA and readiness endpoints afterward.

Never toggle public APK execution/isolation/egress flags merely to make the UI look active.
