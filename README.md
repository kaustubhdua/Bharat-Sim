# BharatSim 🇮🇳 — The Cheap Phone Test

**Android resilience testing with evidence you can act on.** BharatSim combines Android log analysis, risk planning, controlled emulator execution, and evidence-backed reports for apps intended to work on low-end devices and unstable Indian networks.

- Product: https://bharat-sim-81g2.vercel.app
- Repository: https://github.com/kaustubhdua/Bharat-Sim
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Current acceptance status: [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md)
- Judge demo: [docs/finale/JUDGE_DEMO_SCRIPT.md](docs/finale/JUDGE_DEMO_SCRIPT.md)

> **Release status:** BharatSim is a controlled-beta engineering prototype, not yet accepted for public customer APK execution. Production database identity, private Storage round-trip, live tenant-isolation tests and a separately isolated worker host remain release gates. Public APK execution must remain disabled until those gates are independently verified.

---

## What is implemented

### Risk planning
- API-backed, deterministic risk ranking for general, e-commerce, fintech, social, education, delivery and media apps.
- Editable critical user journeys, persona selection and JSON export.
- Planning is not execution. A generated plan does not mean the app was installed, tested or failed.

### Logcat analysis and evidence
- Deterministic crash, ANR, OOM, network and storage signal detection.
- Source-line-linked findings, normalized Failure DNA groups, recommendations and a transparent heuristic BharatScore.
- PDF and JSON report export.
- Findings are diagnostic signals, not confirmed root causes. Absence of a marker does not prove app health.

### Android execution workers

The workspace includes **Connect a Laptop**: a signed-in user can create a personal worker key, install the worker on their own Windows/macOS/Linux laptop, and revoke that laptop. Personal keys are stored as hashes server-side and scoped to the owner's jobs; the supervisor keeps the emulator and worker process running. This is a user-owned execution convenience, not a per-job security sandbox or proof of production isolation.

Two distinct worker modes exist:

- **Legacy smoke mode (default):** install/launch, bounded observation, Logcat collection, emulator-console latency/bandwidth control readback, battery-saver and bounded storage-pressure controls where supported.
- **Full engine mode:** set `BHARATSIM_WORKER_ENGINE=engine` to run baseline and persona passes, collect startup/frame/memory/log evidence, and route traffic using the host shaping proxy. The proxy can apply latency, bandwidth, packet-loss stalls, connection resets and offline periods to traffic that actually uses the Android system proxy. Each report records proxy connections/bytes and states when no app traffic traversed the proxy.

The engine's proxy is not a universal VPN. Apps that bypass Android's system proxy are not shaped. CPU throttling is unsupported. RAM behavior depends on emulator provisioning; a profile target is not proof of a live RAM cap. A smoke run is not proof that all app journeys pass.

See [worker/README.md](worker/README.md), [docs/ANDROID_NETWORK_SHAPING.md](docs/ANDROID_NETWORK_SHAPING.md) and [docs/WORKER_HOST_SETUP.md](docs/WORKER_HOST_SETUP.md).

### Speak-to-Test and Sarvam
- Text and optional voice requests can be converted into a validated scenario plan.
- Executable scenario IDs are allowlisted server-side; the included BharatPay APKs are controlled fixtures.
- Real Sarvam interpretation, translation and Bulbul speech require a server-side `SARVAM_API_KEY`. Fallback behavior must be labelled as fallback, not presented as live provider output.
- The BharatPay fixture journey is not a payment gateway integration and does not move real money.

### Persistence, upload and worker protocol
- APK validation includes archive/manifest checks, bounded metadata extraction and SHA-256.
- Signed/resumable private Storage upload code, PostgreSQL persistence, owner-scoped access, worker leases, heartbeats and authenticated result callbacks are implemented and covered by automated tests.
- CI applies the complete isolated BharatSim migration chain to a clean PostgreSQL service and tests persistence across API restarts.
- Production use still requires the correct Supabase/PostgreSQL target and credentials, a real private-bucket round-trip, and live two-user isolation evidence.

---

## ML and score limitations — read before quoting metrics

BharatSim has separate backend and worker classifier paths:

- The backend portable TF-IDF centroid model is generated from 58 curated examples. Its recorded 100% score is training-set/resubstitution accuracy, **not** an independent holdout or field-accuracy result. Softmax-like outputs are ranking scores, not calibrated probabilities.
- The worker classifier is trained on a mixed dataset of LogHub Android logs weakly labelled by rules, templated failure lines and optional locally labelled worker lines. Its recorded 5-fold GroupKFold metrics are 0.7843 accuracy and 0.7707 macro-F1 on that mixed dataset. They are not field accuracy and still need independent label-quality/leakage review.
- The anomaly detector uses explicit thresholds and a fixed-reference z-score heuristic. It is not a validated covariance model or a trained production anomaly detector.
- BharatScore is a heuristic summary, not a certification or probability that an app will work on a specific device.

See [docs/ML_PIPELINE.md](docs/ML_PIPELINE.md) and [docs/READINESS_SCORE_VALIDATION.md](docs/READINESS_SCORE_VALIDATION.md).

---

## Network and device support truth

| Condition | Legacy smoke worker | Full engine worker | Evidence boundary |
|---|---|---|---|
| Latency / bandwidth | Emulator control-plane readback | Host proxy for proxy-routed app traffic | Readback or proxy counters must be inspected per run |
| Packet-loss stalls / resets | Unsupported | Proxy-supported | Only connections through Android system proxy are affected |
| Network outage / recovery | Not a general verified control | Airplane-mode drop/recovery journey | Per-run device/process evidence required |
| Battery saver / storage pressure | Supported on disposable emulators with readback/cleanup | Supported where emulator controls succeed | Report only what was applied and reset |
| RAM | Report-only / provisioning dependent | AVD provisioning dependent | Do not claim a dynamic per-app RAM cap |
| CPU throttling | Unsupported | Unsupported | Never claim it was applied |
| Arbitrary APK traffic path | Not verified | Not guaranteed | Apps may bypass the system proxy |

The CI HTTPS proxy experiment validates a source-built fixture's route and measured transfer behavior. It does not prove arbitrary uploaded APK traffic, production isolation or physical-device fidelity.

---

## Run locally

### Requirements
- Python 3.11+ (CI currently tests Python 3.12)
- Node.js 22+
- Docker Engine + Docker Compose plugin for the full PostgreSQL stack
- Android SDK / ADB / disposable emulator only if running an Android worker

### Full local stack (recommended)
From the repository root, set a unique local PostgreSQL password and start the stack:

```bash
# macOS/Linux
export BHARATSIM_LOCAL_POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build
```

Windows PowerShell:

```powershell
$env:BHARATSIM_LOCAL_POSTGRES_PASSWORD = python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up --build
```

Open:
- Dashboard: http://127.0.0.1:8080
- API docs: http://127.0.0.1:8080/docs
- Liveness: http://127.0.0.1:8080/health/live
- Readiness: http://127.0.0.1:8080/health/ready

This is a local development stack, not a multi-tenant production sandbox. It does not provision a disposable Android emulator.

### Backend only
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend only
```bash
cd frontend
npm ci
npm run dev
```

By default, Vite proxies API requests to the local backend. See [frontend/.env.example](frontend/.env.example) before overriding the API base URL.

### Optional Android worker
Use only a disposable emulator on a dedicated, restricted development host. Configure a unique `BHARATSIM_WORKER_TOKEN`, `ANDROID_SERIAL`, `BHARATSIM_API_URL`, and `BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true`. For full engine mode also set `BHARATSIM_WORKER_ENGINE=engine`. Do not run untrusted APKs on a personal phone or a host containing sensitive credentials. See [worker/README.md](worker/README.md).

---

## Validation commands

```bash
# Backend tests
cd backend
pip install -r requirements-dev.txt
pytest -q
cd ..

# Worker tests and syntax
python -m unittest discover -s worker/tests
python -m py_compile worker/agent.py worker/runner.py worker/engine.py worker/shaper.py

# Frontend unit tests and production build
cd frontend
npm ci
npm test
npm run build

# Browser E2E
npx playwright install chromium
npm run test:e2e
cd ..

# Compose and container checks
docker compose config --quiet
docker build -f backend/Dockerfile -t bharatsim-api:local .
docker build -f frontend/Dockerfile -t bharatsim-web:local .
```

GitHub Actions also runs a clean PostgreSQL migration/persistence job, worker guards, unified Vercel build, container smoke and a separate Android emulator fixture workflow. A green CI run proves the checked-in test scope, not production acceptance.

## Production release gates

Before calling BharatSim fully complete, the following must be evidenced against the intended production environment:

1. Reconcile browser Auth/Storage project and server-side PostgreSQL project IDs; protect shared GenomeGuard data.
2. Apply reviewed migrations to the confirmed BharatSim database and prove persistence across independent API invocations.
3. Verify private APK upload, size/hash validation, worker download, signed retrieval, deletion and retention.
4. Run a real two-user matrix for every private API route, report, run and artifact.
5. Provision and attest a dedicated per-job isolated Android worker with default-deny egress, resource limits and teardown.
6. Complete a real authenticated APK → report → reopen/export journey.
7. Independently validate engine network conditions and Failure DNA/FixProof across repeated runs.
8. Verify live Sarvam provider paths if those are part of the judge claims.
9. Complete manual accessibility, screen-reader, keyboard and responsive checks.
10. Verify the exact merged SHA is deployed and healthy on the canonical origin.

See [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) and [docs/PRODUCTION_RELEASE_GATES.md](docs/PRODUCTION_RELEASE_GATES.md). Public arbitrary APK execution must remain disabled until the isolation, ownership and egress gates pass.
