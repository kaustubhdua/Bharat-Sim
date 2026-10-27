# BharatSim 🇮🇳

**The Cheap Phone Test** — test Android apps under constrained device and unreliable-network conditions, then explain failures with traceable evidence.

> **Status: MVP with an authenticated worker-dispatch prototype.** The API, responsive dashboard, log analysis, risk planner, APK upload validation, lease-based job protocol, and local ADB smoke worker are implemented. The GitHub Actions Android emulator workflow exercises the real local API → queue → worker → ADB → callback → saved-report path using a source-built fixture APK. A historical cellular experiment measured three baseline and three shaped HTTPS requests to `example.com` (88 ms baseline median, 233 ms shaped median, 145 ms increase with 150 ms configured) and verified reset; that historical result is not a substitute for the current release candidate's tests. The current routed-probe candidate is being revalidated because its host-routable endpoint failed with `ConnectException` and public DNS remained unreliable from the emulator. The workflow now resolves the public HTTPS endpoint on the CI host, pins the resulting IP for the fixture socket, and retains the URL hostname for TLS SNI and certificate validation. This avoids emulator DNS without substituting a local response. The current candidate must pass repeated latency/bandwidth assertions before those controls are described as verified. No such candidate pass is claimed yet. Packet loss and CPU throttling remain unsupported; RAM is report-only; public deployment, production sandboxing, and physical-device fidelity remain unverified. Battery-saver and bounded storage-pressure simulation are implemented for disposable emulator targets with readback/reset evidence.

## What works in this repository

- Four named Bharat test personas and deterministic risk-ranked scenario planning.
- APK upload size limits, APK-like ZIP structure checks, bounded archive metadata, and SHA-256 fingerprinting.
- FastAPI endpoints with SQLite persistence by default for local development. An opt-in PostgreSQL adapter and isolated Supabase migration now exist, but the migration must be applied and the server-only database URL configured before PostgreSQL is active. A process-level integration test verifies SQLite run metadata survives an API restart; worker heartbeat history and full report/artifact durability across restarts are not yet proven.
- Worker queue with authenticated job claims, short-lived leases, heartbeats, lease-bound APK downloads, SHA-256 evidence matching (completed results must include the matching APK hash), result callbacks, stale-result rejection, and bounded inline report JSON. Protocol tests cover lease renewal, expired-lease reclamation, stale-token rejection, retry exhaustion, and duplicate result rejection.
- Optional polling worker that refuses credential-bearing HTTP redirects, enforces same-origin `/internal/worker/` paths for job URLs, verifies APK hashes, and runs an explicitly enabled ADB smoke test against a configured disposable Android device. APK-derived package names are validated before use in ADB shell commands, the runner attempts package cleanup after execution, and common secret patterns are redacted from report text before persistence (best effort, not exhaustive).
- Deterministic logcat signal analysis, failure fingerprints, evidence-linked findings, and a transparent heuristic BharatScore. Worker reports also include bounded, line-addressable crash, ANR, OOM, network, and storage marker excerpts from actual collected logcat; markers remain diagnostic signals, not confirmed root causes.
- React/Vite dashboard with run history, worker heartbeat status, log analysis, and report inspection.
- Docker Compose setup for local API/dashboard deployment, with a loopback-only web binding by default.
- CI for backend tests, frontend production build, real-browser Playwright E2E against a live local FastAPI instance (API/profile loading, source-line log analysis, and disabled run registration until an APK is selected), worker safety guards, container builds, and scheduled/PR-triggered Python and JavaScript dependency vulnerability audits. The audit workflow passed on the merged revision; passing an audit is not a full security certification. The dashboard labels worker `completed` states as `smoke completed`, not as a product-health pass.
- Dedicated Android emulator workflow that builds a known-good fixture APK, exercises the real local API → queue → worker → ADB → callback → saved-report path, runs an Appium UI assertion, verifies emulator console latency/bandwidth readback and confirms default network settings are restored. It also runs an isolated Linux network-namespace test that measures real ping traffic through a shaped veth. The fixture network experiment uses a bounded 2,000,000-byte public HTTPS transfer, pins the CI-resolved endpoint IP while preserving TLS hostname validation, and explicitly enables the simulated cellular data route and requires the fixture to confirm that Android reports cellular transport. The prior host-routable endpoint failed with `ConnectException`, and prior host-alias experiments did not show a repeatable latency effect (observed median deltas of -49 ms and +14 ms despite console readback); those results are not accepted as proof of shaping. The current candidate must pass measured latency and bandwidth assertions plus reset verification before it is marked verified. Any pass applies only to the source-built fixture and CI emulator, not arbitrary uploaded apps. All current traffic-path claims apply to the source-built fixture only, not arbitrary app traffic.

## What is not complete

- No public production URL or deployed commit has been verified.
- A real disposable Android emulator workflow has passed for the source-built BharatSim fixture: upload → queue/lease → ADB install/launch/logcat → authenticated callback → persisted report, followed by an Appium UI action assertion and screenshot. This validates the fixture pipeline only; it does not validate arbitrary third-party APKs or production isolation.
- Appium/UiAutomator2 is integrated for a fixture-app primary-action journey. Product-specific test-flow authoring, broader assertion coverage, and arbitrary-app compatibility remain incomplete.
- Emulator console latency and upload/download bandwidth controls are wired to the worker and read back from the emulator. Battery-saver and bounded storage-pressure simulation are wired for disposable emulator targets with cleanup/readback evidence. Packet loss and CPU throttling remain unsupported, RAM is report-only, and arbitrary app traffic is not proven.
- Multi-user identity, per-user run ownership, durable object storage, and production-grade sandbox isolation are not implemented. The Supabase migration is committed but has not yet been applied to common 1 or verified against a configured PostgreSQL backend.
- Sarvam translation is not wired into the product.

## Architecture

- backend/: FastAPI API, SQLite local persistence plus opt-in PostgreSQL adapter, upload handling, log analysis, run/job lifecycle, and worker callbacks.
- supabase/: isolated BharatSim schema migration and local CLI configuration; this schema is not exposed to browser clients.
- frontend/: Vite + React dashboard.
- backend/tests/: backend, upload-security, and worker-protocol tests.
- worker/agent.py: authenticated polling worker using Python's standard library.
- worker/runner.py: bounded ADB install/launch/logcat smoke runner with guarded Android Emulator console latency/bandwidth controls, exact control-plane readback, and reset verification.
- worker/condition_planner.py: persona-to-condition planning with explicit supported, control-plane-verifiable, report-only, and unsupported classifications.
- worker/condition_applicator.py: reversible battery-saver/storage-pressure application, RAM readback, structured condition evidence, and cleanup/reset handling.
- worker/network_shaper.py: guarded Linux tc/netem prototype; not integrated into Android job execution. `scripts/ci/network-shaper-e2e.sh` measures traffic across an isolated shaped veth in CI.
- docs/: architecture, API, security, open-source references, and roadmap.

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

See docs/DEPLOYMENT.md. The local stack runs with `docker compose up --build -d` and serves the dashboard at `http://127.0.0.1:8080`. It does not provision an Android emulator and is not safe for public multi-user APK execution.

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
- Emulator condition simulation: network latency, download bandwidth, battery saver, and bounded storage pressure are supported on disposable Android emulators with control-plane readback verification and guaranteed cleanup.
- Upload bandwidth is control-plane verified, but data-plane throughput remains unverified without an active probe.
- Emulator control-plane verification does not automatically prove arbitrary application data-plane traffic traversed the shaped network.
- Packet loss, dynamic RAM restriction, and CPU throttling remain unsupported/report-only and are never faked.

## Production release gates

See [`docs/PRODUCTION_RELEASE_GATES.md`](docs/PRODUCTION_RELEASE_GATES.md) for the evidence-based checklist covering tenant isolation, Android execution, constraint verification, and deployment. Public APK execution remains blocked until the critical safety and operational gates are satisfied.

### Private single-tenant API gate

The local Compose stack can optionally require `BHARATSIM_REQUIRE_API_KEY=true` and a random `BHARATSIM_API_KEY` of at least 32 characters. Nginx injects this key server-side for same-origin API calls; it is not shipped in the frontend bundle. This protects a private single-operator instance only—it is not multi-user authentication or a substitute for tenant isolation. Setup instructions are in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Security

Treat every uploaded APK as untrusted code. APK archive checks are not malware scanning or sandboxing. Keep execution on an isolated disposable worker with restricted egress, no production secrets, resource/time limits, and cleanup. The shared API/worker tokens are machine-to-machine credentials, not multi-user authentication. Do not expose public APK execution until identity/ownership, quotas, storage retention, and host isolation have been reviewed. See [docs/SECURITY.md](docs/SECURITY.md), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), and [worker/README.md](worker/README.md).

## License

MIT — see LICENSE.
