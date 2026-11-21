# BharatSim — Testing Strategy

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21

## Principles

- Test actual API/app contracts; mocks and fixtures only in clearly isolated unit tests.
- Use a fresh disposable PostgreSQL database for migration/integration tests.
- Never point APK uploads, destructive actions, fuzzing or load tests at production.
- Separate job submission from Android install, launch, app-verdict and telemetry success.
- Record exact commit SHA, environment, command, result and artifacts for every acceptance claim.
- Treat missing credentials or infrastructure as BLOCKED, not PASS.

## Existing coverage

| Layer | Framework / mechanism | CI job |
|---|---|---|
| Frontend unit/build | Vitest, TypeScript, Vite build | `frontend` |
| Browser E2E | Playwright + Chromium against local FastAPI and Vite | `frontend-e2e` |
| Backend | Pytest | `backend` |
| Database | Disposable PostgreSQL; migration + restart persistence tests | `postgres-integration` |
| Android worker | unittest, py_compile, Appium/UiAutomator2 fixture path | `worker-guards`, Android emulator smoke |
| Deployment/container | Unified ASGI/SPA smoke, Docker, Compose smoke | `unified-vercel-build`, `container-build` |
| Dependencies | Dependency vulnerability workflow | Dependency security audit |

## Playwright inventory

`frontend/e2e/dashboard.spec.ts` contains guest preview, API/personas, evidence-backed log analysis, disabled run registration without APK, wizard navigation, narrow viewport overflow, API docs navigation, live readiness labels, auth gate, deep links, cross-width overlap checks, planner validation/export and public landing cases. The CI workflow now archives Playwright failure evidence on every run.

## Release-critical coverage still needed

1. Complete real Supabase Auth registration, verification, login, refresh, expiration and logout using disposable identities.
2. Execute an authenticated two-user matrix across all API resources and object-storage endpoints.
3. Validate malicious and malformed APKs/archives, decompression bombs, spoofed MIME and path traversal in an isolated environment.
4. Exercise upload interruption/resume/expiry and private object access/retention.
5. Run Android install/launch/capture tests for success, crash, ANR, timeout, ADB loss, worker termination and cleanup.
6. Verify the app's traffic actually traverses the network shaper; test cleanup after success/failure/cancellation.
7. Publish independent held-out classifier precision/recall/F1/confusion matrix and confidence calibration.
8. Run provider contract tests and opt-in live Sarvam translation/TTS in staging.
9. Add accessibility axe/WCAG checks, keyboard-only and screen-reader E2E.
10. Add staging-only k6 load tests with measured p95/throughput thresholds.

## Reproduction commands

```bash
# Frontend unit/type/build
cd frontend && npm ci && npm test && npm run typecheck && npm run build

# Browser E2E (local API + Vite servers configured in playwright.config.ts)
cd frontend && npx playwright install chromium && npm run test:e2e

# Backend
cd backend && pip install -r requirements-dev.txt && pytest -q

# Worker unit/guard suite (repository root)
python -m unittest worker.tests.test_network_shaper worker.tests.test_runner worker.tests.test_agent worker.tests.test_appium_smoke_journey worker.tests.test_https_shaping_proxy worker.tests.test_android_connect_source

# Worker syntax
python -m py_compile worker/agent.py worker/runner.py worker/network_shaper.py
```

PostgreSQL integration and container tests run through `.github/workflows/ci.yml` on disposable services. Do not repoint this suite to production.
