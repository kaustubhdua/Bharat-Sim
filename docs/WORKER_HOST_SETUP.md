# BharatSim Android worker host setup

This guide is the operational summary for the production worker. The full security and SDK runbook is in [WORKER_DEPLOYMENT.md](WORKER_DEPLOYMENT.md).

## Production host

Use a dedicated Ubuntu 24.04 x86_64 VM with at least 4 vCPU, 12 GB RAM, 40 GB free disk, hardware virtualization, and readable/writable /dev/kvm. The worker executes untrusted APKs. Do not share the host with the API, database, browser profiles, cloud credentials, personal files, or unrelated workloads.

Do not expose ADB/emulator console ports or host management interfaces. Block cloud metadata and private/control-plane network ranges from the worker. Restrict egress to the BharatSim API, common1 Supabase Storage/Auth endpoints, and public test destinations required by the app under test. A worker token is authentication, not a sandbox.

## Android SDK and AVD

Install OpenJDK 17, Android command-line tools, platform-tools, emulator, build-tools 35.0.0, and the Android 35 Google APIs x86_64 system image. Configure:

~~~~bash
export ANDROID_SDK_ROOT=/opt/android-sdk
export ANDROID_HOME=/opt/android-sdk
export ANDROID_USER_HOME=/var/lib/bharatsim/android
export ANDROID_AVD_HOME=/var/lib/bharatsim/avd
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/build-tools/35.0.0:$PATH"

yes | sdkmanager --licenses
sdkmanager "platform-tools" "emulator" "build-tools;35.0.0" "platforms;android-35" "system-images;android-35;google_apis;x86_64"
avdmanager create avd --force --name bharatsim-api35 --package "system-images;android-35;google_apis;x86_64" --device pixel_2
~~~~

The worker agent now manages the emulator process itself. Do not enable the old standalone bharatsim-emulator.service alongside recycling; it can race the agent for emulator-5554.

## Worker environment

Create /etc/bharatsim/worker.env with mode 0600 and root ownership:

~~~~dotenv
BHARATSIM_ENV=production
BHARATSIM_API_URL=https://bharat-sim-bay.vercel.app
BHARATSIM_WORKER_TOKEN=<same strong random token configured on the API>
BHARATSIM_WORKER_ID=android-worker-01
BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true
BHARATSIM_RECYCLE_EMULATOR=true
BHARATSIM_EMULATOR_ACCEL=on
BHARATSIM_EMULATOR_BOOT_TIMEOUT_SECONDS=240
BHARATSIM_EMULATOR_LOG=/var/log/bharatsim/emulator.log
ANDROID_SERIAL=emulator-5554
ANDROID_AVD_NAME=bharatsim-api35
ANDROID_SDK_ROOT=/opt/android-sdk
ANDROID_HOME=/opt/android-sdk
ANDROID_USER_HOME=/var/lib/bharatsim/android
ANDROID_AVD_HOME=/var/lib/bharatsim/avd
BHARATSIM_POLL_SECONDS=5
BHARATSIM_SMOKE_DURATION_SECONDS=20
~~~~

The worker token must match the server-side BHARATSIM_WORKER_TOKEN in Vercel and contain at least 32 random characters. Do not copy the database URL, service-role key, or Sarvam key to the worker.

## systemd

Use only the worker service. It must run as a dedicated unprivileged account with supplementary group kvm and read/write access only to the AVD home, Android user home, worker temp/artifact paths, and emulator log path. The service should use KillMode=control-group so stopping the agent also stops its child emulator process.

~~~~bash
sudo systemctl daemon-reload
sudo systemctl enable --now bharatsim-worker
sudo systemctl status bharatsim-worker
journalctl -u bharatsim-worker -f
~~~~

Do not start public APK execution until the API database/Storage credentials are configured, Vercel SSO no longer blocks server-to-server worker calls, and the full production acceptance test in WORKER_DEPLOYMENT.md passes. Supabase Auth and worker-token authentication must remain enabled when SSO is removed.
