# BharatSim — Test Execution Report

**Audit date:** 2026-11-21 (IST)  
**Earlier candidate:** `c037fb0fb471d13e2f0115b9d3f9d8074b4687e0`

## Evidence reviewed

This report distinguishes test execution from feature availability. GitHub Actions for the candidate head must be fully complete before the PR can be considered merge-ready. CI for its immediate parent snapshot `54ac4377b8a961822ebff80d19d07e6faafbf0c6` had passing backend Pytest, PostgreSQL integration, worker guards, frontend build, unified FastAPI/SPA build and container smoke. Playwright E2E was still running at last inspection. An earlier candidate snapshot had 4 passes and 9 failures in Playwright E2E. Android emulator smoke on a subsequent intermediate snapshot was cancelled. A successful Android smoke from a different commit is not transferred to this candidate.

A follow-up candidate `0e31d2ab117a20c4a29118855fdfa1e4abaaa46f` adds a per-test authentication fixture so guest preview and the sign-in gate begin from a clean browser context. Its CI run is still in progress and must finish before acceptance.

## Live production read-only smoke

| Endpoint | Observed | Interpretation |
|---|---|---|
| `/` | HTTP 200; sign-in screen rendered | Frontend reachable; not an authenticated journey |
| `/api/v1/capabilities` | HTTP 200 | API reachable; the previously deployed payload incorrectly reported TTS/comparison capability despite dependency unavailability |
| `/health/ready` | HTTP 503 | Not ready: database/private storage unavailable; Android worker not configured |

No production accounts, APK uploads, writes or destructive operations were performed.

## Follow-up candidate run\n\nThe first candidate E2E run exposed two test-isolation defects: a suite-wide local auth session was applied even to guest preview/sign-in tests, and the test then expected an unauthenticated screen. Playwright traces and screenshots were captured as CI artifact `14710617269`. The fix now applies the local session only to authenticated dashboard scenarios and leaves guest/sign-in tests unauthenticated. The new candidate CI is pending.\n\n## Test suites

| Suite | Current report |
|---|---|
| Frontend Vitest/typecheck/build | Passed on parent CI snapshot; re-run required on exact candidate SHA |
| Backend Pytest | Passed on parent CI snapshot; re-run required on exact candidate SHA |
| PostgreSQL integration | Passed on parent CI snapshot; re-run required on exact candidate SHA |
| Worker unit/guard suite | Passed on parent CI snapshot; Android production worker not present |
| Container/Compose | Passed on parent CI snapshot |
| Playwright E2E | Earlier snapshot failed; candidate rerun pending at time this report was drafted |
| Android emulator smoke | Candidate attempt cancelled; fixture-only; production arbitrary APK execution unverified |
| Dependency audit | Earlier candidate passed; exact candidate's result must be refreshed |
| Performance/load | Not run |
| Accessibility/WCAG | Not run as a complete audit |
| Live Sarvam | Blocked; no verified live provider output |
| Production DB/storage | Blocked; health readiness HTTP 503 |

## Reproduction

```bash
cd frontend && npm ci && npm test && npm run typecheck && npm run build
cd frontend && npx playwright install chromium && npm run test:e2e
cd backend && pip install -r requirements-dev.txt && pytest -q
```

The CI run attached to the exact candidate SHA is authoritative. Do not mark the feature inventory green from code existence.
