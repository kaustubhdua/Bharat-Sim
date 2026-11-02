# BharatSim 🇮🇳

**Android resilience testing, with evidence you can act on.** Configure constrained-device profiles, submit APKs, inspect execution evidence, and analyze Android logs without confusing a test plan with a completed test.

> **Latest verification (2026-11-02):** PR #113 is merged into `main` as `59a857988ad4d86d0721052b846dff381616ef0a`. It makes production health observable when credentials are absent, prevents production SQLite fallback, verifies the PostgreSQL schema at readiness, and fails closed on protected data routes when persistence/auth or private APK storage is missing. The final PR-head CI run [41351082893](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41351082893) passed backend, frontend build, frontend E2E, PostgreSQL integration, container/Compose smoke and worker guards; dependency audit [41351082859](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41351082859) passed. Android emulator smoke [41351082867](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41351082867) also passed and preserved artifact [13100673423](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41351082867) (SHA-256 `6440e28dfd18b9bdd1f82f139d776cc2e9f7c32fc30c87e456765b63ecc39f98`; expires 2026-11-15). These checks verify the CI fixture and code, not production customer APK execution. The backend Production deployment is still on older commit `c11ed5b0964738929ea62ca5296172032a57e4d1`; its live API alias still returns HTTP 500 `FUNCTION_INVOCATION_FAILED`. Vercel rejected the new deployment attempts with `api-deployments-free-per-day` (more than 100 deployments), so the merged fix is not yet deployed. The exact backend Vercel Production inventory still lacks `BHARATSIM_DATABASE_URL` and a server-only `SUPABASE_SECRET_KEY`/legacy service-role key. Supabase common1 is healthy, but application DB connectivity and Auth/Storage journeys remain unverified. No isolated production Android worker host or default-deny egress proof exists; public APK execution remains disabled. See [the live product audit](docs/LIVE_PRODUCT_AUDIT_2026-11-02.md), [production release gates](docs/PRODUCTION_RELEASE_GATES.md), [isolated worker design](docs/ISOLATED_WORKER_DESIGN.md), and [production completion execution plan](docs/PRODUCTION_COMPLETION_EXECUTION_PLAN.md).

> **Status: controlled-beta MVP; production launch is not approved.** The FastAPI API, responsive dashboard, grouped Failure DNA log analysis, pairwise Interaction Hunter planning panel, APK validation, lease-based worker protocol, and local ADB smoke worker are implemented. The dashboard includes searchable/filterable run history, a live backend capability contract, owner-scoped run deletion, a per-run lifecycle evidence timeline, and integrity-checked report export. The optional Supabase Auth flow and backend JWT/ownership checks are implemented behind `BHARATSIM_AUTH_REQUIRED=true`; live Auth provider settings and a live application database connection have not been verified. The GitHub Actions Android emulator workflow exercises the real local API → queue → worker → ADB → callback → saved-report path using a source-built fixture APK. A historical cellular experiment measured three baseline and three shaped HTTPS requests to `example.com` (88 ms baseline median, 233 ms shaped median, 145 ms increase with 150 ms configured) and verified reset; that historical result is not a substitute for the current release candidate's tests. The current Android network experiment uses a repository-controlled 256,000-byte fixture asset served over raw.githubusercontent.com HTTPS, but each measured request transfers a bounded 64,000-byte range. The CI host resolves the endpoint IPv4 address; the fixture pins that IP while retaining the hostname for TLS SNI and certificate validation. This removes reliance on a public speed-test service while preserving a real external HTTPS data path. The current Appium fixture experiment keeps the emulator's active Android network enabled and routes its HTTPS socket through a host-side allowlisted HTTP CONNECT proxy. The proxy pins raw.githubusercontent.com to the CI-resolved IPv4 address, does not terminate TLS, records each tunnel's bytes and duration, and applies a 384 kbps per-direction cap or a 150 ms initial round-trip setup delay. Each measured request must have a matching proxy event and exact 64,000-byte response. Android Emulator console shaping is still used by the worker's local condition manager, but the CI fixture no longer relies on an unavailable Cellular/Ethernet transport. The latest successful main-branch emulator CI run (GitHub Actions run 41331104452, main code commit ee0beea4495eb41fc27003ea96585f8413ddd77b; subsequent main commits add documentation and frontend-only test setup/auth tests; Android worker runtime code is unchanged) completed three baseline, three bandwidth-only, and three latency-only HTTPS range probes on the active Wi-Fi network. Every sample transferred 64,000 bytes over end-to-end TLS through the allowlisted CONNECT proxy and matched the pinned upstream IP 185.199.111.133. The 384 kbps profile increased median end-to-end transfer time by 1,295 ms; the 150 ms latency profile recorded 150.41–150.43 ms of actual injected delay across both relay directions. End-to-end latency medians remain diagnostic because public upstream RTT varies. The proxy reset was read back at baseline. This verifies only the source-built fixture path, not arbitrary uploaded APKs. Packet loss and CPU throttling remain unsupported; RAM is report-only; public deployment, production sandboxing, live database connectivity, and physical-device fidelity remain unverified. Battery-saver and bounded storage-pressure simulation are implemented for disposable emulator targets with readback/reset evidence.

## What works in this repository

- Four named Bharat test personas, a category-aware deterministic risk planner with editable critical user journeys (e-commerce, fintech, social, education, delivery, media and general), and pairwise condition-interaction hypotheses surfaced in the dashboard. The planner prioritizes tests; it does not execute them. See [docs/PLANNER.md](docs/PLANNER.md) for scoring and limitations.
- APK upload size limits, APK-like ZIP structure checks, bounded archive metadata, and SHA-256 fingerprinting.
- FastAPI endpoints with SQLite persistence for direct local Python development; the Docker Compose workflow now starts a private PostgreSQL 17 service by default and automatically initializes the reviewed BharatSim schema. An opt-in PostgreSQL adapter and isolated Supabase migration exist. Vercel serverless connections use the Supabase Transaction pooler with psycopg prepared statements disabled and transaction-local `SET LOCAL search_path` (no session-level state). When private Storage is configured, the dashboard uploads APK bytes directly using short-lived signed TUS capabilities in retryable 6 MiB chunks (bypassing Vercel's 4.5 MB function body limit and recovering from unstable networks); the API verifies object size before queueing and the worker independently checks SHA-256. On Vercel/AWS serverless deployments, APK uploads are disabled until both persistent PostgreSQL and private Storage are configured; the API never falls back to an ephemeral function filesystem. Local development without Storage credentials retains filesystem uploads. The `common 1` Supabase project now has a verified private `bharatsim-private` Storage bucket; when the server-only `SUPABASE_SECRET_KEY` (preferred) or legacy `SUPABASE_SERVICE_ROLE_KEY` is configured, APK uploads are streamed into generated object paths, workers retrieve them only through lease-authenticated proxy downloads, and terminal results delete the input object. Local development without Storage credentials retains filesystem uploads. Worker reports/logcat remain bounded inline JSON; durable report artifact storage and background retention scheduling are still outstanding. The `common 1` project has the `bharatsim` schema and private grants; the core migration filename matches its remote `20261027054905_bharatsim_core` history. A clean PostgreSQL 17 CI job applies the core, foreign-key-index, and signed-upload metadata migrations from zero and verifies restart persistence, per-user quota enforcement, and signed-upload metadata. The additive foreign-key-index migration is applied to `common 1` at remote version `20261027061609_bharatsim_fk_indexes`, and the repository migration filename now matches that history. The application has not yet been verified using its live server-side database URL. Worker heartbeat history and full report/artifact durability across restarts are not yet proven.
- Worker queue with authenticated job claims, short-lived leases, heartbeats, lease-bound APK downloads, SHA-256 evidence matching (completed results must include the matching APK hash), result callbacks, stale-result rejection, and bounded inline report JSON. Protocol tests cover lease renewal, expired-lease reclamation, stale-token rejection, retry exhaustion, and duplicate result rejection.
- Optional polling worker that refuses credential-bearing HTTP redirects, enforces same-origin `/internal/worker/` paths for job URLs, verifies APK hashes, and runs an explicitly enabled ADB smoke test against a configured disposable Android device. APK-derived package names are validated before use in ADB shell commands, the runner attempts package cleanup after execution, and common secret patterns are redacted from report text before persistence (best effort, not exhaustive).
- Deterministic logcat signal analysis, failure fingerprints, evidence-linked findings, and a transparent heuristic BharatScore. Worker reports also include bounded, line-addressable crash, ANR, OOM, network, and storage marker excerpts from actual collected logcat; markers remain diagnostic signals, not confirmed root causes.
- Cross-source evidence synthesis on each run detail and report export correlates logcat markers with condition-manager verification, network control/data-plane evidence, and ADB step outcomes. It emits only low/medium unconfirmed hypotheses, distinguishes pre-existing from applied conditions, and hashes derived diagnostics separately from the original worker report. See [docs/EVIDENCE_SYNTHESIS.md](docs/EVIDENCE_SYNTHESIS.md); the fail-closed review pattern was informed by `jai-hack` without importing its cybersecurity classifiers.
- React/Vite dashboard with searchable/filterable run history, live capability status, worker heartbeat status, log analysis, report inspection, owner-scoped run deletion, and on-demand JSON report export with SHA-256 integrity metadata. Report JSON remains in the database; this export is not separate durable object storage.
- Docker Compose setup for local API/dashboard deployment, with a loopback-only web binding by default and a private PostgreSQL 17 service. Set a unique `BHARATSIM_LOCAL_POSTGRES_PASSWORD` before startup; see [the local PostgreSQL quickstart](docs/LOCAL_POSTGRES_DEVELOPMENT.md).
- CI for backend tests, frontend production build, real-browser Playwright E2E against a live local FastAPI instance (API/profile loading, source-line log analysis, and disabled run registration until an APK is selected), worker safety guards, container builds, and scheduled/PR-triggered Python and JavaScript dependency vulnerability audits. The audit workflow passed on the merged revision; passing an audit is not a full security certification. The dashboard labels worker `completed` states as `smoke completed`, not as a product-health pass.
- Dedicated Android emulator workflow that builds a known-good fixture APK, exercises the real local API → queue → worker → ADB → callback → saved-report path, and runs an Appium UI assertion. The Appium fixture binds its HTTPS socket to the active Android Network and routes it through a host-side allowlisted CONNECT proxy pinned to the CI-resolved raw.githubusercontent.com IPv4 address. The proxy preserves end-to-end TLS, records tunnel bytes/timings, applies a 384 kbps per-direction cap or a 150 ms initial round-trip setup delay, and verifies control readback and reset. Each measurement downloads a bounded 64,000-byte range from a 256,000-byte repository fixture. A separate Linux network-namespace test measures real ping traffic through a shaped veth. Verified in CI run 41331104452 on the active Wi-Fi transport: three repeated baseline, bandwidth-only and latency-only HTTPS range samples, pinned upstream IP 185.199.111.133, 64,000 response bytes per sample, 384 kbps median slowdown of 1,295 ms, 150.41–150.43 ms injected latency telemetry, and verified reset. This pass proves only the source-built fixture's path, not arbitrary uploaded APK traffic.

## What is not complete

- The latest inspected frontend Production deployment is READY on commit `23f14d95b8fa986fc36fd5f6306e007e6050ff0b`; it predates the merged dashboard redesign. The backend Production deployment is READY on `895a2779dfd409ddc483c20745c418a251b81fdb`, but its exact Vercel Production environment inventory does not list `BHARATSIM_DATABASE_URL` or a server-only Supabase secret key. The API therefore cannot be accepted as a live persistent customer service. No same-release frontend/backend deployment or deployed end-to-end customer journey has been verified. The Vercel deployment quota previously returned HTTP 402 `api-deployments-free-per-day`; no quota bypass was attempted.
- The current candidate uses a repository fixture asset over raw.githubusercontent.com HTTPS, transferring 64 KB per measurement through an allowlisted CONNECT proxy with a 384 kbps per-direction rate cap or 150 ms initial round-trip setup delay. CI run 41331104452 passed repeated real HTTPS baseline, latency-only and bandwidth-only fixture measurements, including 64,000-byte responses, pinned upstream IP 185.199.111.133, measured 150.41–150.43 ms injected delay, bandwidth slowdown, and reset verification. This validates only the source-built fixture path; it does not validate arbitrary third-party APKs or production isolation.
- Appium/UiAutomator2 is integrated for a fixture-app primary-action journey. Product-specific test-flow authoring, broader assertion coverage, and arbitrary-app compatibility remain incomplete.
- Emulator console latency and upload/download bandwidth controls are wired to the worker and read back from the emulator. Battery-saver and bounded storage-pressure simulation are wired for disposable emulator targets with cleanup/readback evidence. Packet loss and CPU throttling remain unsupported, RAM is report-only, and arbitrary app traffic is not proven.
- Supabase Auth JWT verification, per-user run/analysis ownership, and per-user run quotas (10 per UTC day, 2 active by default) are implemented behind `BHARATSIM_AUTH_REQUIRED=true`; the frontend includes optional email/password sign-in. Owner-scoped run deletion and report export are also implemented and covered by cross-user regression tests. However, live Supabase Auth provider/redirect settings, server-side `BHARATSIM_DATABASE_URL`, Storage service credentials, and an actual application read/write test against `common 1` remain unverified. The isolated `bharatsim` schema and private APK bucket exist in `common 1`, but the application has not been shown to use them at runtime. Per-user daily/active run quotas are implemented (10 per UTC day, 2 active by default); per-user upload-frequency/byte limits, production-grade disposable-VM sandbox isolation, egress restrictions, and durable report/log/screenshot object storage are not implemented.
- Optional Sarvam AI translation for condensed finding summaries in Hindi, Tamil, and Marathi. It is opt-in, sends no raw logcat, uses a server-only `SARVAM_API_KEY`, and remains disabled until that credential is configured. See [`docs/SARVAM_TRANSLATION.md`](docs/SARVAM_TRANSLATION.md).

## Architecture

- backend/: FastAPI API, SQLite local persistence plus opt-in PostgreSQL adapter, upload handling, log analysis, cross-source evidence fusion, run/job lifecycle, and worker callbacks.
- supabase/: isolated BharatSim schema migration and local CLI configuration; this schema is not exposed to browser clients.
- frontend/: Vite + React dashboard.
- backend/tests/: backend, upload-security, and worker-protocol tests.
- worker/agent.py: authenticated polling worker using Python's standard library.
- worker/runner.py: bounded ADB install/launch/logcat smoke runner with guarded Android Emulator console latency/bandwidth controls, exact control-plane readback, and reset verification.
- worker/condition_planner.py: persona-to-condition planning with explicit supported, control-plane-verifiable, report-only, and unsupported classifications.
- worker/condition_applicator.py: reversible battery-saver/storage-pressure application, RAM readback, structured condition evidence, and cleanup/reset handling.
- worker/network_shaper.py: guarded Linux tc/netem prototype; not integrated into Android job execution. `scripts/ci/network-shaper-e2e.sh` measures traffic across an isolated shaped veth in CI.
- docs/: architecture, API, security, evidence-synthesis method, open-source references, and roadmap.

## Run locally

### Backend

    cd backend
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Open http://localhost:8000/docs and http://localhost:8000/health/ready.

### Frontend

    cd frontend
    npm install
    npm run dev

The frontend uses same-origin API requests by default. Set VITE_API_BASE_URL=http://localhost:8000 in frontend/.env.local only if needed. Never put private keys in VITE_* variables.

### Docker Compose

See docs/DEPLOYMENT.md and docs/WORKER_HOST_SETUP.md for local deployment and isolated Android worker host setup. The local stack runs with `docker compose up --build -d` and serves the dashboard at `http://127.0.0.1:8080`. It does not provision an Android emulator and is not safe for public multi-user APK execution.

### Worker

See worker/README.md. Configure BHARATSIM_WORKER_TOKEN on the API and worker, provide an HTTPS BHARATSIM_API_URL, configure an explicit disposable ANDROID_SERIAL, and opt in with BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true. Do not run unknown APKs on a personal device or an unisolated host.

### Tests

    cd backend
    pip install -r requirements-dev.txt
    pytest -q
    cd ..
    python -m unittest worker.tests.test_network_shaper
    python -m py_compile worker/agent.py worker/runner.py
    cd frontend
    npm install
    npm run build
    npx playwright install chromium
    npm run test:e2e
    cd ..
    docker compose config --quiet
    docker build -f backend/Dockerfile -t bharatsim-api:local .
    docker build -f frontend/Dockerfile -t bharatsim-web:local .

## API and execution truth

- /health/live reports process liveness; /health/ready checks database availability.
- /api/v1/capabilities reports implemented features and limitations.
- /api/v1/workers reports worker heartbeats seen in the last 90 seconds.
- Runs remain queued/awaiting a worker until the worker claims them. A run becomes completed or failed only after an authenticated worker result is accepted.
- A completed smoke run means the runner finished install/launch/observation/log collection; it is not proof of broad app correctness.
- Emulator condition simulation: network latency and download/upload bandwidth controls have emulator control-plane readback; battery saver and bounded storage pressure have readback/cleanup evidence on disposable emulators. The CI fixture now has a verified HTTPS download data path through the host CONNECT proxy; this is fixture-only and does not establish arbitrary uploaded-app traffic.
- Upload bandwidth remains control-plane verified only; the current 64 KB fixture experiment verifies download shaping, not a large upload throughput path.
- Emulator control-plane verification does not automatically prove arbitrary application data-plane traffic traversed the shaped network.
- Packet loss, dynamic RAM restriction, and CPU throttling remain unsupported/report-only and are never faked.

## Production release gates

See [`docs/PRODUCTION_RELEASE_GATES.md`](docs/PRODUCTION_RELEASE_GATES.md) for the evidence-based checklist covering tenant isolation, Android execution, constraint verification, and deployment. The current Vercel/common1 environment contract and remaining credentials are documented in [`docs/VERCEL_DEPLOYMENT.md`](docs/VERCEL_DEPLOYMENT.md). Public APK execution remains blocked until the critical safety and operational gates are satisfied.

### Private single-tenant API gate

The local Compose stack can optionally require `BHARATSIM_REQUIRE_API_KEY=true` and a random `BHARATSIM_API_KEY` of at least 32 characters. Nginx injects this key server-side for same-origin API calls; it is not shipped in the frontend bundle. This protects a private single-operator instance only—it is not multi-user authentication or a substitute for tenant isolation. Setup instructions are in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Security

Treat every uploaded APK as untrusted code. APK archive checks are not malware scanning or sandboxing. Keep execution on an isolated disposable worker with restricted egress, no production secrets, resource/time limits, and cleanup. The shared API/worker tokens are machine-to-machine credentials, not multi-user authentication. Do not expose public APK execution until identity/ownership, quotas, storage retention, and host isolation have been reviewed. See [docs/SECURITY.md](docs/SECURITY.md), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), and [worker/README.md](worker/README.md).

## License

MIT — see LICENSE.
