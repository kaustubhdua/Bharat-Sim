# BharatSim — submission demo runbook

This guide is for recording a truthful, repeatable local demo of the current controlled-beta prototype. It is deliberately separate from the production release checklist.

## What the demo proves

The deployed sign-in screen also offers **Explore public planner preview**. This guest view calls the live persona and risk-planning API; it is not a fake account. APK registration, log submission, report export and private run history remain locked until a visitor signs in. For a full local recording, use the no-auth local development setup below.


The strongest locally reproducible story is:

1. Start the FastAPI API and React dashboard locally.
2. Load the four constrained-device personas and explain their assumptions.
3. Generate an explainable, category-aware risk plan and inspect the pairwise condition hypotheses.
4. Paste real or deliberately prepared Android logcat text into the analyzer.
5. Show grouped Failure DNA findings, source-line evidence, recommendations, the heuristic BharatScore and its limitations.
6. If (and only if) a disposable emulator and local worker are configured, submit a safe fixture APK and show the actual queued → leased → install/launch → logcat → callback → report lifecycle.

A planner result is a proposed test plan, not an executed test. A completed worker run is an install/launch/logcat smoke test, not proof that every user journey passed. The CI Android fixture proves the pipeline for that source-built fixture only.

## Fast local setup

Use a clean checkout of `main`. Requirements: Python 3.12, Node.js 22.12 or newer (the CI build uses Node 22), and npm. Check versions first with `python --version` and `node --version`.

### Terminal 1 — API

**Windows PowerShell**

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks virtual-environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.

**macOS / Linux**

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

The default local development configuration uses local SQLite and local filesystem uploads. With no `VITE_SUPABASE_URL` / publishable key in the frontend environment and no `BHARATSIM_AUTH_REQUIRED=true` in the API environment, the local demo opens directly without sign-in. This is a local-development mode only; it is not the production authentication configuration.

Do not copy production credentials into this demo. Confirm the API is alive at `http://127.0.0.1:8000/health/live`. In local development, `/health/ready` should report the local API database available; execution readiness can still be unavailable because no Android worker is connected.

### Terminal 2 — dashboard

```bash
cd frontend
npm ci
```

Create `.env.local` inside the `frontend` directory (do not commit it) with:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

On Windows PowerShell, you can create it with:

```powershell
"VITE_API_BASE_URL=http://127.0.0.1:8000" | Set-Content -Encoding ascii .env.local
npm run dev
```

On macOS / Linux:

```bash
printf '%s\n' 'VITE_API_BASE_URL=http://127.0.0.1:8000' > .env.local
npm run dev
```

Keep the API terminal open while recording; closing it disconnects the dashboard from its backend.

Open the local Vite URL printed by the command (normally `http://localhost:5173`). Do not set `VITE_SUPABASE_URL` or a publishable key for the local no-auth demo unless you intentionally want to test the sign-in flow. Never place a service-role key, Supabase secret key, database password, or worker token in a `VITE_*` variable.

### Capture real Android logcat for the analysis segment

Do not paste invented or copied example errors into the recording. Use logs from an Android app you own or are authorised to test, preferably on a disposable emulator.

1. Connect the emulator/device and verify it is visible:

   ```bash
   adb devices
   ```

2. Clear old buffered logs, reproduce the actual failure or scenario in your app, then capture the new log stream:

   ```bash
   adb logcat -c
   adb logcat -v threadtime > bharatsim-logcat.txt
   ```

3. After reproducing the issue, stop the capture with `Ctrl+C`, inspect the file, remove any personal identifiers, access tokens, URLs with credentials, or customer data, and paste the relevant real log lines into **Inspect logcat**.

If you cannot reproduce a crash or error in an app you are authorised to test, do not manufacture one for the video. Demonstrate the planner and explain that the analyzer needs actual log evidence. The GitHub [Android emulator smoke run](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41331104452) has a downloadable CI artifact for the repository's source-built fixture APK; label that evidence as CI fixture output, not a customer APK or your local device run.

### Optional — persistent local PostgreSQL

For a more realistic local persistence demonstration, use the repository's Docker Compose PostgreSQL workflow in [LOCAL_POSTGRES_DEVELOPMENT.md](LOCAL_POSTGRES_DEVELOPMENT.md). It is local-only and does not emulate Supabase Auth or Supabase Storage.

## Optional Android APK smoke run

Only do this with an APK you own or are authorised to test, on a disposable Android Emulator/VM. Do not install unknown APKs on a personal phone or a machine containing personal accounts, files, SSH keys or production credentials. The worker is not itself a sandbox.

1. Start a disposable Android Emulator and confirm `adb devices` shows its serial.
2. Start the API with the same random local-only worker token configured in the worker environment:

   ```bash
   export BHARATSIM_WORKER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   ```

   Keep this value in the API and worker terminals only; do not save it in the frontend environment or commit it.
3. Restart the API after setting the token.
4. In a third terminal, from the repository root, set:

   ```bash
   export BHARATSIM_API_URL=http://127.0.0.1:8000
   export BHARATSIM_ALLOW_INSECURE_HTTP=true
   export BHARATSIM_WORKER_TOKEN='<same local-only token>'
   export BHARATSIM_WORKER_ID=demo-emulator-worker
   export ANDROID_SERIAL='<your disposable emulator serial>'
   export BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true
   python worker/agent.py
   ```

5. Upload a known-good fixture APK through the dashboard. Watch the run lifecycle and report. Then use a deliberately crashing fixture only if one is already available and safe to run.
6. Do not claim the smoke run passed the app's complete business flows. Report the exact APK hash, emulator image/API, worker revision and smoke steps shown by the report.

The worker protocol and limitations are documented in [worker/README.md](../worker/README.md). The dedicated-host requirements are in [WORKER_HOST_SETUP.md](WORKER_HOST_SETUP.md).

## Five-minute recording sequence

Keep the recording focused. Use the actual locally running build, not edited screenshots.

| Time | Screen / action | What to explain |
|---|---|---|
| 0:00–0:30 | Dashboard overview | The problem: apps are often built on laptops and tested on flagship phones, but used on constrained devices and networks |
| 0:30–1:15 | Personas | Show low storage, limited memory and network assumptions; state that personas are profiles, not measured population statistics |
| 1:15–2:00 | Risk planner | Select an app category, edit critical journeys, generate scenarios; explain deterministic prioritisation and pairwise hypotheses |
| 2:00–3:30 | Log analysis | Paste representative logcat, run analysis, open Failure DNA groups, show source lines, severity, recommendations and score |
| 3:30–4:15 | Evidence and caveats | Show evidence provenance, confidence/validation steps, requested vs verified conditions, unsupported controls |
| 4:15–5:00 | Optional worker run | Show a real fixture APK lifecycle only if it actually completes locally; otherwise show the CI fixture evidence and label it as CI |

Do not show credentials, personal email, private keys, browser password managers, unrelated desktop notifications, or real customer APKs/logs.

## Safe claims to use

- “BharatSim provides explainable constrained-device personas and a deterministic risk planner.”
- “The log analyzer groups repeated crash, ANR, OOM, network and storage signals and links findings to source log lines.”
- “BharatScore is a transparent heuristic indicator, not a statistically calibrated probability.”
- “The Android CI fixture validates a source-built APK through the local API, queue, worker, ADB, callback and saved-report path.”
- “The current network experiment verifies a controlled HTTPS fixture path for latency and download-bandwidth shaping.”
- “The dashboard explicitly labels control-plane-only, report-only and unsupported conditions.”

## Claims not to make

- Do not say arbitrary uploaded APKs are safely executed in production.
- Do not say Firecracker per-job isolation or default-deny egress is live; the production worker host is not provisioned.
- Do not claim physical ₹8,000-device fidelity from emulator-only evidence.
- Do not claim packet-loss, CPU-throttling or dynamic RAM throttling support.
- Do not claim upload-bandwidth data-plane verification or arbitrary-app traffic shaping.
- Do not describe the deterministic planner or log analyzer as a generative AI model.
- Do not claim production run history/private APK uploads work until the live database and server-only Storage round trip have passed.

## Submission evidence checklist

- [ ] Public repository link opens without authentication.
- [ ] The recording uses a clean local build and shows actual interactions.
- [ ] At least one analysis report includes source-line evidence and limitations.
- [ ] Any worker result is labelled as a smoke test and tied to its APK SHA-256.
- [ ] CI emulator fixture run and its artifact are linked from the submission notes.
- [ ] README links to this guide and the production limitations.
- [ ] AI tools, open-source components and third-party services are disclosed in the submission form.
- [ ] No credentials, private data, or copyrighted third-party APKs/logs are included.

## Production remains a separate gate

A local demo can be recorded without waiting for Vercel. The public deployment still requires a successful unified Vercel deployment, live database and private-storage credentials, deployed Auth/persistence/upload acceptance, and a separately verified isolated worker host. See [SINGLE_PROJECT_DEPLOYMENT.md](SINGLE_PROJECT_DEPLOYMENT.md), [PRODUCTION_RELEASE_GATES.md](PRODUCTION_RELEASE_GATES.md) and [ISOLATED_WORKER_DESIGN.md](ISOLATED_WORKER_DESIGN.md).
