# BharatSim Android execution worker

The repository includes an authenticated polling agent (agent.py) and a bounded ADB smoke runner (runner.py). In production, the agent owns one KVM-backed Android Emulator and wipes/reboots its AVD user data at startup and after every claimed APK job. This is an execution prototype—not a production sandbox or a guarantee that arbitrary app flows were tested.

## Safety requirements

- Run the worker on a disposable VM/host dedicated to untrusted APK execution.
- Do not use a personal phone, personal Google account, production secrets, or a host with access to sensitive networks.
- Restrict outbound network access and resource usage at the VM/container boundary. The runner itself is not a security sandbox.
- Use HTTPS for the API. Plain HTTP is allowed only for local development when BHARATSIM_ALLOW_INSECURE_HTTP=true.
- Use a unique, random BHARATSIM_WORKER_TOKEN of at least 32 characters on both API and worker. Rotate it if exposed.
- Configure ANDROID_SERIAL and ANDROID_AVD_NAME explicitly. Production requires BHARATSIM_RECYCLE_EMULATOR=true, BHARATSIM_EMULATOR_ACCEL=on, and readable/writable /dev/kvm; the worker fails closed if the wipe/reboot does not complete.
- Guest wiping is not a substitute for a dedicated VM, egress restrictions, or host-level isolation.
- Do not enable public uploads until host isolation, egress policy, quotas, and retention controls have been reviewed.

## Prerequisites

- Python 3.10+
- Android SDK platform-tools (adb) and build-tools (aapt) on PATH
- Android Emulator/AVD packages installed; when recycling is enabled, the agent starts the configured AVD itself
- Network access from worker to the API

## Start the API

Configure BHARATSIM_WORKER_TOKEN in the API environment. The token must not be committed to the repository. Start FastAPI as described in the root README. When the token is configured, APK uploads with a valid APK-like archive are queued; they are not considered executed until a worker submits a report.

## Dedicated host deployment

For the production Linux VM setup, KVM requirements, per-job emulator wipe, worker environment file, network-isolation requirements and hardened systemd service, see [`docs/WORKER_HOST_SETUP.md`](../docs/WORKER_HOST_SETUP.md), [`docs/WORKER_DEPLOYMENT.md`](../docs/WORKER_DEPLOYMENT.md), and [`deploy/bharatsim-worker.service.example`](../deploy/bharatsim-worker.service.example). The worker agent manages the emulator process; do not run a separate emulator supervisor.

## Start the worker

From the repository root, configure these environment variables:

    export BHARATSIM_ENV=production
    export BHARATSIM_API_URL=https://your-api-host.example
    export BHARATSIM_WORKER_TOKEN='your-long-random-secret'
    export BHARATSIM_WORKER_ID='android-worker-01'
    export ANDROID_SERIAL=emulator-5554
    export ANDROID_AVD_NAME=bharatsim-api35
    export BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true
    export BHARATSIM_RECYCLE_EMULATOR=true
    export BHARATSIM_EMULATOR_ACCEL=on
    python -m worker.agent

For local-only development, set BHARATSIM_ENV=development and BHARATSIM_API_URL=http://127.0.0.1:8000 with BHARATSIM_ALLOW_INSECURE_HTTP=true. Recycling is optional for trusted local APKs; never use the insecure HTTP exception on a public network.

Optional settings: BHARATSIM_POLL_SECONDS (1–60, default 5) and BHARATSIM_SMOKE_DURATION_SECONDS (1–120, default 20).

## Job lifecycle

1. The worker authenticates and claims a queued run.
2. The API leases the run to that worker and returns a short-lived lease token.
3. The worker downloads only the APK attached to that leased run. Returned worker URLs must be relative `/internal/worker/` paths; absolute URLs, external hosts, fragments, and unrelated routes are rejected before credentials are attached.
4. The runner checks bounded APK archive metadata, checks the device, installs and launches the APK, then captures bounded logcat evidence.
5. The worker periodically renews its lease and submits a bounded report.
6. The API accepts results only from the active lease and stores the result with the run.
7. In production, the agent kills the emulator and starts the same AVD with -wipe-data and -no-snapshot before it claims another job.

An expired lease can be retried up to three claims. A stale or duplicate result is rejected. The API accepts at most 250 KB of inline report JSON; the worker includes a bounded logcat tail. Durable object storage, cancellation during an active ADB operation, per-job VM snapshots, and full artifact retention are still production hardening tasks.

## Runner output and limitations

A completed smoke run means install/launch/observation/log collection completed without a detected fatal crash marker; it does not mean the application passed every user journey. A fatal crash marker during the observation window fails the smoke run. Absence of a marker does not prove the app is healthy.

### Persona condition simulation support matrix

- **SUPPORTED (CONTROLLED AND READ-BACK VERIFIED)** (on disposable Android Emulator targets):
  - **Battery saver**: Configured via `cmd battery unplug` and `settings put global low_power 1`, verified via `settings get global low_power` and `dumpsys battery`, reset via `cmd battery reset` and `settings put global low_power 0`.
  - **Storage pressure**: Configured via bounded temporary file allocation (`/data/local/tmp/bharatsim_storage_pressure.tmp`), strict safety reserve check (minimum 100 MB preserved, max allocation capped), verified before and after, with guaranteed deletion and readback verification upon cleanup.

- **CONTROL-PLANE VERIFIED (DATA-PLANE UNVERIFIED)**:
  - **Network latency**: Configured via emulator console `emu network delay <ms>` and verified with status readback; this per-run worker does not prove arbitrary app traffic traversed the shaped path.
  - **Download bandwidth**: Configured via emulator console `emu network speed <up>:<down>` and verified with status readback; active application throughput is not verified per run.
  - **Upload bandwidth**: Upload bandwidth limit is applied and read back on the emulator control plane, but active application data-plane throughput is unverified without a dedicated traffic probe.

- **REPORT-ONLY**:
  - **RAM constraint**: Dynamic RAM throttling is not supported on the Android runtime without VM re-launch. The worker reads `/proc/meminfo` (MemTotal, MemAvailable) and reports actual device memory against persona targets for honest comparison.

- **UNSUPPORTED**:
  - **Packet loss**: The Android emulator console does not support packet loss simulation.
  - **CPU constraint**: Personas do not specify CPU constraints, and arbitrary emulator CPU throttling is not supported.

> **Important**: Emulator control-plane verification does not automatically prove arbitrary application data-plane traffic traversed the shaped network. The CI fixture experiment must pass baseline-versus-shaped comparison before it can be called verified; this is not proof for arbitrary uploaded apps. Persona Android release labels are requested targets: the current worker uses its configured API 35 AVD and does not switch OS images per persona.

The guarded network shaper is documented in NETWORK_SHAPING.md. It must only be used with a dedicated test interface, and applying a qdisc does not prove emulator traffic traversed it.
