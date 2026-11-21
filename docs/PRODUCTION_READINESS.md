# BharatSim — Production Readiness

**Audit date:** 2026-11-21 (IST)  
**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
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

## Gate assessment

- **Frontend:** Main UI and public landing route implemented. Candidate build passed on parent snapshot; final E2E on exact candidate SHA is pending.
- **Backend:** Pytest and unified ASGI smoke passed on parent snapshot; live database-backed product journey not ready.
- **Database:** Clean disposable PostgreSQL migrations/restart integration passed on parent snapshot; production persistence unverified.
- **Android:** Fixture-only emulator/worker tests exist; no production worker host and no arbitrary APK verification.
- **Network:** Limited emulator fixture control; arbitrary app traffic not proven; unsupported controls remain disabled.
- **ML:** Heuristic/class-centroid code exists; independent holdout evaluation absent.
- **Sarvam:** Provider credential required; no live output verified.
- **Security:** Dependency audit only; tenant isolation and sandbox egress need independent acceptance.
- **Reporting:** JSON export paths exist; PDF and durable report library/share are incomplete.
- **Performance/accessibility:** No controlled load benchmark or full WCAG audit recorded.

## Manual infrastructure actions required

1. Provision production PostgreSQL and the backend-only Supabase secret; reconcile migrations and verify health.
2. Provision private Storage and test signed upload/download/delete/retention using two actual users.
3. Configure Supabase Auth redirect, email verification and password recovery; execute real signup/login/session refresh/logout.
4. Provision an isolated disposable Android worker host with default-deny egress, resource caps, worker token, watchdog and cleanup; obtain independent attestation before enabling execution.
5. Configure backend-only Sarvam secret if translation/TTS are required.
6. Deploy a coordinated API/frontend release after exact-SHA checks pass; verify deployed SHA and readiness endpoints afterward.

Never toggle public APK execution/isolation/egress flags merely to make the UI look active.
