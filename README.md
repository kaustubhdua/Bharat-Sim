# BharatSim 🇮🇳

**The Cheap Phone Test** — test Android apps under constrained device and unreliable-network conditions, then explain failures with traceable evidence.

> **Status: MVP with an authenticated worker-dispatch prototype.** The API, responsive dashboard, log analysis, risk planner, APK upload validation, lease-based job protocol, and local ADB smoke worker are implemented. The GitHub Actions Android emulator workflow exercises the real local API → queue → worker → ADB → callback → saved-report path using a source-built fixture APK. The fixture's Appium/UiAutomator2 primary-action journey passes in a disposable GitHub Actions emulator. Emulator console delay/bandwidth settings are applied and read back. In the disposable emulator, the fixture made three baseline and three shaped HTTPS requests to `example.com` over CELLULAR: median latency increased from 88 ms to 233 ms (145 ms) with a 150 ms delay configured, and reset readback verified zero delay and default bandwidth. This proves the fixture path in CI only, not arbitrary APK traffic. Packet loss, resource pressure, public deployment, production sandboxing, and physical-device fidelity remain unverified.

## What works in this repository

- Four named Bharat test personas and deterministic risk-ranked scenario planning.
- APK upload size limits, APK-like ZIP structure checks, bounded archive metadata, and SHA-256 fingerprinting.
- FastAPI endpoints with SQLite persistence for run metadata and log analyses. A process-level integration test verifies that run metadata survives an API restart; worker heartbeat history and full report/artifact durability across restarts are not yet proven.
- Worker queue with authenticated job claims, short-lived leases, heartbeats, lease-bound APK downloads, SHA-256 evidence matching, result callbacks, stale-result rejection, and bounded inline report JSON. Protocol tests cover lease renewal, expired-lease reclamation, stale-token rejection, retry exhaustion, and duplicate result rejection.
- Optional polling worker that refuses credential-bearing HTTP redirects, enforces same-origin `/internal/worker/` paths for job URLs, verifies APK hashes, and runs an explicitly enabled ADB smoke test against a configured disposable Android device. APK-derived package names are validated before use in ADB shell commands, and the runner attempts package cleanup after execution.
- Deterministic logcat signal analysis, failure fingerprints, evidence-linked findings, and a transparent heuristic BharatScore.
- React/Vite dashboard with run history, worker heartbeat status, log analysis, and report inspection.
- Docker Compose setup for local API/dashboard deployment, with a loopback-only web binding by default.
- CI for backend tests, frontend production build, worker safety guards, container builds, and scheduled/PR-triggered Python and JavaScript dependency vulnerability audits. The audit workflow passed on the merged revision; passing an audit is not a full security certification.
- Dedicated Android emulator workflow that builds a known-good fixture APK, exercises the real local API → queue → worker → ADB → callback → saved-report path, runs an Appium UI assertion, verifies emulator console latency/bandwidth readback and confirms default network settings are restored. It also runs an isolated Linux network-namespace test that measures real ping traffic through a shaped veth. The CI fixture compares three real external HTTPS requests on cellular before and after applying an emulator latency/bandwidth profile. Latest passing evidence: baseline median 88 ms, shaped median 233 ms, delta 145 ms; the workflow also verifies profile reset to zero latency/default bandwidth. This verifies the source-built fixture's path only, not arbitrary app traffic.

## What is not complete

- No public production URL or deployed commit has been verified.
- A real disposable Android emulator workflow has passed for the source-built BharatSim fixture: upload → queue/lease → ADB install/launch/logcat → authenticated callback → persisted report, followed by an Appium UI action assertion and screenshot. This validates the fixture pipeline only; it does not validate arbitrary third-party APKs or production isolation.
- Appium/UiAutomator2 is integrated for a fixture-app primary-action journey. Product-specific test-flow authoring, broader assertion coverage, and arbitrary-app compatibility remain incomplete.
- Emulator console latency and upload/download bandwidth controls are wired to the worker and read back from the emulator. The CI fixture has verified a baseline-versus-shaped HTTPS latency increase and confirmed reset readback. Packet loss, CPU/RAM/storage pressure, and battery-saver behavior remain unsupported, and arbitrary app traffic is not proven.
- Multi-user identity, per-user run ownership, durable object storage, and production-grade sandbox isolation are not implemented.
- Sarvam translation is not wired into the product.

## Architecture

- backend/: FastAPI API, SQLite persistence, upload handling, log analysis, run/job lifecycle, and worker callbacks.
- frontend/: Vite + React dashboard.
- backend/tests/: backend, upload-security, and worker-protocol tests.
- worker/agent.py: authenticated polling worker using Python's standard library.
- worker/runner.py: bounded ADB install/launch/logcat smoke runner with guarded Android Emulator console latency/bandwidth controls, exact control-plane readback, and reset verification.
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
- Emulator console network latency and bandwidth are reported verified only when control-plane readback matches the request; this does not prove app traffic used the controlled interface.
- Packet loss, resource pressure, and overall persona enforcement remain unsupported/unverified and must not be described as applied.

## Security

Treat every uploaded APK as untrusted code. APK archive checks are not malware scanning or sandboxing. Keep execution on an isolated disposable worker with restricted egress, no production secrets, resource/time limits, and cleanup. The shared API/worker tokens are machine-to-machine credentials, not multi-user authentication. Do not expose public APK execution until identity/ownership, quotas, storage retention, and host isolation have been reviewed. See [docs/SECURITY.md](docs/SECURITY.md), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), and [worker/README.md](worker/README.md).

## License

MIT — see LICENSE.
