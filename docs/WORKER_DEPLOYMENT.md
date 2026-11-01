# Production Android worker deployment

The worker executes untrusted APKs. Do not run it on a developer laptop, a shared application host, or a VM that contains production database/API secrets. Use a dedicated x86_64 Linux VM with KVM and a restricted network policy.

## Security boundary

- One worker process owns one Android Emulator serial. Do not share an emulator between workers.
- The worker agent requires a fresh guest after every claimed run when BHARATSIM_ENV=production. It kills the current AVD and starts it again with -wipe-data -no-snapshot; it repeats this on startup.
- If the emulator cannot be wiped and booted successfully, the worker exits fail-closed and stops claiming jobs.
- Guest wiping is not a substitute for host isolation. The VM must be dedicated, contain no cloud credentials or database passwords, and have no inbound ADB exposure. For stronger isolation, recreate/revert the VM from a trusted image after suspicious APKs or at a defined interval.
- Restrict egress from the VM. Block cloud metadata endpoints and private/control-plane networks; allow only the BharatSim API, common1 Supabase Storage/Auth endpoints, and the public internet needed by the app under test. Bind host admin services to loopback and firewall the emulator's 10.0.2.2 host-gateway path.
- Never expose TCP 5554/5555 (or any ADB port) to the public internet.

## Host requirements

- Ubuntu 24.04 x86_64 (or a compatible Linux distribution).
- At least 4 vCPU, 8 GB RAM, and 40 GB free disk for the Android SDK, system image, emulator data, and APK artifacts.
- Hardware virtualization enabled and /dev/kvm readable/writable by the worker service account.
- Android SDK command-line tools, platform-tools, emulator, build-tools, and the Android 35 Google APIs x86_64 system image.
- Python dependencies from backend/requirements.txt / the worker's documented environment.

A container deployment must pass /dev/kvm through explicitly and add the service account to the host kvm group. Do not use --privileged; grant only the device and capabilities required by the network-shaping configuration. Confirm the selected provider supports KVM before provisioning.

## Create the AVD

Set the SDK paths and install the packages:

~~~~bash
export ANDROID_SDK_ROOT=/opt/android-sdk
export ANDROID_HOME=/opt/android-sdk
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"

yes | sdkmanager --licenses
sdkmanager "platform-tools" "emulator" "platforms;android-35" "build-tools;35.0.0" "system-images;android-35;google_apis;x86_64"
avdmanager create avd --force --name bharatsim-api35 --package "system-images;android-35;google_apis;x86_64" --device pixel_2
~~~~

Do not start a separate emulator supervisor when BHARATSIM_RECYCLE_EMULATOR=true; the agent manages the emulator process itself.

## Worker environment

Configure these variables only on the dedicated worker host:

| Variable | Value |
|---|---|
| BHARATSIM_ENV | production |
| BHARATSIM_API_URL | Public HTTPS API origin after the Vercel API deployment is live and SSO protection has been deliberately removed from the API origin |
| BHARATSIM_WORKER_TOKEN | The same strong random 32+ character secret configured server-side as BHARATSIM_WORKER_TOKEN in the API project |
| BHARATSIM_ENABLE_LOCAL_APK_EXECUTION | true |
| BHARATSIM_RECYCLE_EMULATOR | true (mandatory in production) |
| ANDROID_SERIAL | emulator-5554 |
| ANDROID_AVD_NAME | bharatsim-api35 |
| ANDROID_SDK_ROOT / ANDROID_HOME | The installed SDK root |
| BHARATSIM_EMULATOR_ACCEL | on (mandatory in production; requires /dev/kvm) |
| BHARATSIM_POLL_SECONDS | 5 (optional, 1–60) |
| BHARATSIM_EMULATOR_BOOT_TIMEOUT_SECONDS | 240 (optional, 60–600) |
| BHARATSIM_EMULATOR_LOG | A writable log path, e.g. /var/log/bharatsim/emulator.log |

Run from the repository root:

~~~~bash
python -m worker.agent
~~~~

The worker token is not the Supabase service-role key. Do not copy the database URL, service-role key, or Sarvam API key onto the worker host.

## Vercel and common1 prerequisites

Before starting the worker:

1. Configure BHARATSIM_DATABASE_URL with common1's Transaction Pooler URI and SUPABASE_SERVICE_ROLE_KEY on the Vercel API project.
2. Configure the same BHARATSIM_WORKER_TOKEN value on the API project and worker host.
3. Keep BHARATSIM_AUTH_REQUIRED=true; user routes use verified Supabase JWTs and owner-scoped database queries.
4. Keep the bharatsim-private Storage bucket private. The worker receives APK bytes only through lease-authorized API downloads.
5. Deploy the latest API code and verify /health/ready, database persistence, signed APK upload, worker claim/heartbeat/result, and object cleanup.
6. Vercel SSO currently protects the .vercel.app API origin. A server-to-server worker cannot complete the Vercel SSO flow. Only after Supabase Auth and worker-token protection are verified, disable Vercel SSO on the API origin (or use a suitable unprotected custom API domain). Do not disable application authentication.

## Known limitations

The current worker runs a real install/launch/logcat smoke test; it does not automate arbitrary user journeys through every screen. Android release labels in personas are requested targets; the worker currently uses the configured API 35 AVD and does not switch Android OS images per persona. RAM is report-only, CPU throttling and packet loss are unsupported unless a separately verified traffic-shaping path is configured. See docs/PRODUCTION_RELEASE_GATES.md before enabling public execution.
