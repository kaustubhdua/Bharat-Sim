# BharatSim Android execution worker

The repository includes an authenticated polling agent (agent.py) and a bounded ADB smoke runner (runner.py). The agent connects queued API jobs to a disposable Android emulator/device. This is an execution prototype—not a production sandbox or a guarantee that arbitrary app flows were tested.

## Safety requirements

- Run the worker on a disposable VM/host dedicated to untrusted APK execution.
- Do not use a personal phone, personal Google account, production secrets, or a host with access to sensitive networks.
- Restrict outbound network access and resource usage at the VM/container boundary. The runner itself is not a security sandbox.
- Use HTTPS for the API. Plain HTTP is allowed only for local development when BHARATSIM_ALLOW_INSECURE_HTTP=true.
- Use a unique, random BHARATSIM_WORKER_TOKEN of at least 32 characters on both API and worker. Rotate it if exposed.
- Configure ANDROID_SERIAL explicitly to the disposable test device. Never point it at a personal or production device.
- Do not enable public uploads until host isolation, egress policy, quotas, and retention controls have been reviewed.

## Prerequisites

- Python 3.10+
- Android SDK platform-tools (adb) and build-tools (aapt) on PATH
- A booted disposable emulator or test device visible to ADB
- Network access from worker to the API

## Start the API

Configure BHARATSIM_WORKER_TOKEN in the API environment. The token must not be committed to the repository. Start FastAPI as described in the root README. When the token is configured, APK uploads with a valid APK-like archive are queued; they are not considered executed until a worker submits a report.

## Start the worker

From the repository root, configure these environment variables:

    export BHARATSIM_API_URL=https://your-api-host.example
    export BHARATSIM_WORKER_TOKEN='your-long-random-secret'
    export BHARATSIM_WORKER_ID='android-worker-01'
    export ANDROID_SERIAL=emulator-5554
    export BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true
    python worker/agent.py

For local-only development, set BHARATSIM_API_URL=http://127.0.0.1:8000 and BHARATSIM_ALLOW_INSECURE_HTTP=true in the worker environment. Never use this exception on a public network.

Optional settings: BHARATSIM_POLL_SECONDS (1–60, default 5) and BHARATSIM_SMOKE_DURATION_SECONDS (1–120, default 20).

## Job lifecycle

1. The worker authenticates and claims a queued run.
2. The API leases the run to that worker and returns a short-lived lease token.
3. The worker downloads only the APK attached to that leased run. Returned worker URLs must be relative `/internal/worker/` paths; absolute URLs, external hosts, fragments, and unrelated routes are rejected before credentials are attached.
4. The runner checks bounded APK archive metadata, checks the device, installs and launches the APK, then captures bounded logcat evidence.
5. The worker periodically renews its lease and submits a bounded report.
6. The API accepts results only from the active lease and stores the result with the run.

An expired lease can be retried up to three claims. A stale or duplicate result is rejected. The API accepts at most 250 KB of inline report JSON; the worker includes a bounded logcat tail. Durable object storage, cancellation during an active ADB operation, per-job VM snapshots, and full artifact retention are still production hardening tasks.

## Runner output and limitations

A completed smoke run means install/launch/observation/log collection completed without a detected fatal crash marker; it does not mean the application passed every user journey. A fatal crash marker during the observation window fails the smoke run. Absence of a marker does not prove the app is healthy. The current runner does not automate app-specific UI journeys, apply network shaping, or impose RAM/storage pressure. Those capabilities must remain labeled unsupported until separately implemented and verified.

The guarded network shaper is documented in NETWORK_SHAPING.md. It must only be used with a dedicated test interface, and applying a qdisc does not prove emulator traffic traversed it.
