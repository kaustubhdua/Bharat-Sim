# BharatSim — Test Execution Report

**Candidate SHA:** `58af61db5aac2f29e8128d512a7cf999eb71dc92`  
**Branch:** `fix/accurate-capabilities-and-product-evidence`  
**Date:** 2026-11-21 (IST)

## Exact-SHA GitHub Actions evidence

For the candidate SHA above, CI run [44913283418](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913283418) completed successfully. All seven jobs passed:
- Backend pytest.
- Frontend install/build.
- Playwright frontend E2E.
- PostgreSQL migration/persistence integration.
- Android worker unit/guard and Python compile checks.
- Docker / Compose build and hardened stack smoke.
- Unified FastAPI + frontend ASGI/deep-link smoke.

Dependency security audit run [44913283488](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913283488) completed successfully.

Android emulator smoke run [44913283436](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913283436) was still in progress at report time. Its early steps had passed: Linux netem shaping verification, Appium + UiAutomator2 installation, Android SDK setup, emulator image preparation, proxy setup. The known-good APK build and emulator boot/run stages were not yet completed; do not treat this as a passed Android end-to-end test.

The preceding Playwright run on `c037fb0...` found 2 failed tests / 11 passed because a global test session contaminated intentionally guest-only tests. CI captured traces/screenshots as artifact 14710617269. The E2E fixture was corrected to apply a local authenticated session only to authenticated workspace tests. The subsequent exact-SHA CI run above passed the entire E2E job.

## Production read-only smoke

| Endpoint | Observed | Interpretation |
|---|---|---|
| `/` | HTTP 200; sign-in experience rendered | Frontend reachable, not proof of authenticated workflows |
| `/api/v1/capabilities` | HTTP 200 | API reachable; the captured response was edge-cached and reflected an older capability payload |
| `/health/ready` | HTTP 503 | Not ready: PostgreSQL/private Storage unavailable and Android worker not configured |

No production account, APK upload, write, test execution or destructive operation was performed.

## Remaining test categories

- Actual production Android worker and APK install/launch/telemetry: blocked by absent production worker.
- Live two-tenant Supabase RLS test: not run against production.
- Sarvam live Hindi/Tamil/Marathi translation and Bulbul speech: blocked until provider credential and successful live calls.
- PDF/JSON generated report structure: PDF path not implemented; JSON paths exist but need full authenticated artifact acceptance.
- Accessibility/WCAG: no independent audit completed.
- k6/performance: no controlled staging load test run.

## Reproduction

```bash
cd frontend && npm ci && npm test && npm run typecheck && npm run build
cd frontend && npx playwright install chromium && npm run test:e2e
cd backend && pip install -r requirements-dev.txt && pytest -q
```
