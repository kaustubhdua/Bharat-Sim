# BharatSim — Test Execution Report

**CI-tested application candidates:** `4546d9330f24dacda803cbc887d7bd737dfd2f72` (7/7 CI jobs + dependency audit), `8218bb4d30aa0cbc2d3bd6ea394415b570f9ebcb` (7/7 CI jobs), and Android smoke candidate `d5684752e7f5202c83bb401bf651595290815188` (emulator workflow passed).  
**Branch:** `fix/accurate-capabilities-and-product-evidence`  
**Date:** 2026-11-21 (IST)  
**Candidate branch:** `5b751f88ca8679e5cd32fbdc3eab289451f6aab0`  

## Exact-SHA GitHub Actions evidence

For application SHA `8218bb4d30aa0cbc2d3bd6ea394415b570f9ebcb`, CI run [44913787012](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913787012) completed successfully. All seven jobs passed:
- Backend pytest.
- Frontend install/build.
- Playwright frontend E2E.
- PostgreSQL migration/persistence integration.
- Android worker unit/guard and Python compile checks.
- Docker / Compose build and hardened stack smoke.
- Unified FastAPI + frontend ASGI/deep-link smoke.

Dependency security audit run [44913441381](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913441381) completed successfully on the earlier verified code candidate; run [44913787035](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913787035) also completed successfully for the Android candidate.

Android emulator smoke run [44913283436](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913283436) was still in progress at report time. Its early steps had passed: Linux netem shaping verification, Appium + UiAutomator2 installation, Android SDK setup, emulator image preparation, proxy setup. The known-good APK build and emulator boot/run stages were not yet completed; do not treat this as a passed Android end-to-end test.

The preceding Playwright run on `c037fb0...` found 2 failed tests / 11 passed because a global test session contaminated intentionally guest-only tests. CI captured traces/screenshots as artifact 14710617269. The E2E fixture was corrected to apply a local authenticated session only to authenticated workspace tests. The exact-SHA CI run [44913441396](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913441396) completed successfully with all seven jobs green. The later PR candidate `8218bb4d30aa0cbc2d3bd6ea394415b570f9ebcb` also had all seven CI jobs pass (run [44913787012](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913787012)). The PDF export unit tests are part of that later frontend test suite. The later Android emulator fixture workflow passed on `d5684752e7f5202c83bb401bf651595290815188` (run [44913787016](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/44913787016)). The current branch head `5b751f88ca8679e5cd32fbdc3eab289451f6aab0` consists of follow-on documentation updates; no CI run was found for that exact docs-only SHA.

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
- Analysis PDF: implemented with Vitest checks for PDF signature, report/finding/evidence content and pagination. Those tests still need an exact latest-SHA passing CI result. Run-level PDF/persisted report library/share are incomplete; run JSON export requires authenticated artifact acceptance.
- Accessibility/WCAG: no independent audit completed.
- k6/performance: no controlled staging load test run.

## Reproduction

```bash
cd frontend && npm ci && npm test && npm run typecheck && npm run build
cd frontend && npx playwright install chromium && npm run test:e2e
cd backend && pip install -r requirements-dev.txt && pytest -q
```
