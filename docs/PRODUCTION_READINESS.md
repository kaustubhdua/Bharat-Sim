# BharatSim production readiness — 2 November 2026

## Public entry point

- Customer-facing website: https://bharat-sim-81g2.vercel.app
- The backend is an internal API service, not a second customer-facing website.
- The frontend Vercel project rewrites `/api/*`, `/health/*`, and API documentation paths to the backend.
- Production deployments for both projects were built from GitHub `main` commit `36eac4303a8f468ace7b0ec7f836b36fd5cc8c7d` and reached Vercel `READY` on 2 November 2026.

## Verified live behavior

The following endpoints were checked through the frontend origin after deployment:

- `GET /` — frontend sign-in shell returns HTTP 200.
- `GET /health/live` — API returns HTTP 200.
- `GET /api/v1/personas` — four authored personas return HTTP 200.
- `GET /api/v1/capabilities` — live capability contract returns HTTP 200.
- `GET /docs` and `GET /openapi.json` — API documentation is reachable.
- Vercel runtime error lookup returned no errors in the first hour after the deployment.

## Live feature contract

| Capability | Production state | Evidence / limitation |
|---|---|---|
| Persona catalogue | Available | Four authored profiles returned by API |
| Risk planner | Available | Stateless scenario selection; scenarios are hypotheses, not executed tests |
| Pasted-log analysis | Available after sign-in | Stateless analysis works without PostgreSQL; response explicitly says it is not saved |
| Failure fingerprinting | Available for pasted logs | Based on supplied log evidence |
| Heuristic BharatScore | Available for pasted logs | Heuristic score, not a population-level user-impact measurement |
| Saved reports and run history | Unavailable | Persistent PostgreSQL is not configured |
| APK upload | Unavailable | Private Storage server credential is not configured |
| Worker dispatch / production Android execution | Unavailable | No production worker heartbeat or verified isolated host |
| Sarvam translation | Unavailable | `SARVAM_API_KEY` is not configured |

The production readiness endpoint intentionally returns HTTP 503 until database and private-storage dependencies are available. This is a fail-closed state, not a frontend outage.

## Android evidence

The GitHub Actions workflow [Android emulator smoke evidence](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41393320329) passed on the same main commit. It builds a known-good fixture APK, boots a disposable Android Emulator, exercises an allowlisted HTTPS proxy path, records injected latency and bandwidth telemetry, and verifies that the profile is reset.

This proves the CI fixture's traffic path and emulator-control behavior. It does not prove arbitrary customer APKs are executed in production, and it is not a substitute for the per-job Firecracker/jailer worker isolation described in [ISOLATED_WORKER_DESIGN.md](./ISOLATED_WORKER_DESIGN.md).

## Remaining production gates

1. Configure `BHARATSIM_DATABASE_URL` using the exact Supabase shared transaction-pooler connection string from the project's Connect dialog. Do not guess the pooler cluster host.
2. Configure a server-only Supabase secret/service-role key for private Storage operations. Never put it in a `VITE_*` or `NEXT_PUBLIC_*` variable.
3. Provision a dedicated disposable worker host with per-job microVM isolation, default-deny egress, resource limits, cleanup verification and a unique `BHARATSIM_WORKER_TOKEN`.
4. Run the real-APK acceptance checklist in [WORKER_HOST_SETUP.md](./WORKER_HOST_SETUP.md). Only then set the three production worker safety attestations to true.
5. Configure `SARVAM_API_KEY` only if regional report translation is required.

Do not mark production ready, enable APK uploads, or enable public worker dispatch until the corresponding live checks pass. Packet loss and CPU throttling remain unsupported; RAM constraints are report-only. Emulator latency and bandwidth controls alone do not prove arbitrary-app data-plane shaping.

## CI verification on main

- Backend: 132 passed, 2 skipped.
- Frontend unit tests: 33 passed.
- Playwright: 8 passed.
- Android emulator smoke evidence: passed.
- Dependency security audit: passed.
- Vercel production builds: frontend and backend both `READY`.

