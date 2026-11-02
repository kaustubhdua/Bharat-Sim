# BharatSim Android worker host setup

This guide prepares a dedicated Linux VM to run the existing authenticated Android worker. It is not a substitute for provisioning the VM, verifying KVM, or running a real APK end-to-end.

> **Important isolation boundary:** the current `worker/agent.py` and `worker/runner.py` execute against an ADB device supplied by the host; they do not create a fresh Firecracker microVM per customer job. This systemd setup is therefore only a private, restricted-host pilot recipe. A single shared VM, Docker container, or emulator is **not** sufficient to attest the per-job isolation decision in [ISOLATED_WORKER_DESIGN.md](./ISOLATED_WORKER_DESIGN.md). Keep all three production worker flags false until the Firecracker/jailer supervisor, per-job guest lifecycle, host firewall/default-deny egress, resource limits, cleanup, and real end-to-end acceptance are implemented and independently verified.

## 1. Host requirements

Use a disposable Ubuntu 24.04 x86_64 VM with:

- 4 vCPU and at least 12 GB RAM for one Android Emulator plus the worker/API tooling; more capacity is needed for parallel devices.
- KVM hardware virtualization exposed to the VM (/dev/kvm readable by the worker account).
- At least 30 GB of disposable disk for Android SDK, system images, AVD data, APKs and logs.
- A dedicated unprivileged Linux account named bharatsim.
- No personal files, browser profiles, SSH agent, cloud credentials, production databases or unrelated services on the VM.

Do not run untrusted APKs on the Vercel API host, on a developer laptop, or on a host that can reach private corporate networks.

## 2. Install Android tooling

Install OpenJDK 17, Android command-line tools, platform-tools, emulator and build-tools. Set:

    export ANDROID_HOME=/opt/android-sdk
    export ANDROID_SDK_ROOT=/opt/android-sdk
    export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/build-tools/35.0.0:$PATH"

Install a compatible system image and create a disposable AVD (example API 35):

    sdkmanager "platform-tools" "emulator" "build-tools;35.0.0" "platforms;android-35" "system-images;android-35;google_apis;x86_64"
    avdmanager create avd -n bharatsim-api35 -k "system-images;android-35;google_apis;x86_64" -d pixel_2

Run the emulator as the dedicated account, with a clean data image:

    emulator @bharatsim-api35 -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -memory 2048 -wipe-data

Wait until adb -s emulator-5554 shell getprop sys.boot_completed returns 1. Verify adb devices shows only the disposable emulator. The worker refuses non-emulator serials for destructive condition simulation.

## 3. Configure the worker

Create /etc/bharatsim/worker.env with root-only permissions (mode 0600):

    BHARATSIM_API_URL=https://bharat-sim-bay.vercel.app
    BHARATSIM_WORKER_TOKEN=<same strong random token configured on the API>
    BHARATSIM_WORKER_ID=android-worker-01
    ANDROID_SERIAL=emulator-5554
    BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true
    BHARATSIM_POLL_SECONDS=5
    BHARATSIM_SMOKE_DURATION_SECONDS=20

The API's production alias currently has Vercel SSO protection and production database/Storage credentials are not yet configured. Do not start this service against that alias until those blockers are resolved and the API is reachable from the worker.

Production worker claims are also fail-closed until all three API flags are explicitly enabled: `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=true`, `BHARATSIM_WORKER_ISOLATION_ATTESTED=true`, and `BHARATSIM_WORKER_EGRESS_RESTRICTED=true`. Set them only after independently verifying a disposable VM/microVM boundary and default-deny egress from inside the worker environment. These are operator attestations, not cryptographic remote attestation; a worker token alone is never a sandbox. Keep all three false until that review is complete.

For local development only, use the local API URL and set BHARATSIM_ALLOW_INSECURE_HTTP=true; never enable that exception on a public network.

## 4. systemd service example

Copy both deploy/bharatsim-emulator.service.example and deploy/bharatsim-worker.service.example to /etc/systemd/system/ using the filenames bharatsim-emulator.service and bharatsim-worker.service. Adjust paths, AVD name, account permissions and KVM access, then run:

    sudo systemctl daemon-reload
    sudo systemctl enable --now bharatsim-emulator
    sudo systemctl enable --now bharatsim-worker
    sudo systemctl status bharatsim-emulator bharatsim-worker
    journalctl -u bharatsim-emulator -f
    journalctl -u bharatsim-worker -f

The emulator unit starts a clean AVD and waits for boot completion; the worker unit requires the emulator unit and starts the polling agent only after it is ready. The emulator service uses -wipe-data on process start, not after each job. For stronger per-job isolation, revert a VM snapshot or destroy/recreate the VM after each APK. Configure the Android SDK read-only and AVD/home directories writable only by the dedicated account.

## 5. Network isolation is a release gate

The runner installs and executes untrusted APKs. A worker token is not a sandbox. Before processing public uploads:

- Run each worker in a dedicated disposable VM or microVM; do not rely on a container alone as the security boundary.
- Block access to host management interfaces, cloud metadata endpoints, RFC1918/private ranges, loopback services and internal DNS.
- Permit only the API endpoint and explicitly approved test destinations. If the app must reach arbitrary public internet, route it through an egress proxy that blocks private, link-local and metadata destinations.
- Do not expose ADB, emulator console ports, SSH, Docker socket or host control ports to the public internet.
- Apply CPU, memory, disk, process-count and job-duration limits at the VM boundary.
- Revert a VM snapshot or destroy/recreate the emulator after each job; runner cleanup is best-effort and not equivalent to a clean VM snapshot.
- Rotate the worker token if the VM is compromised.

## 6. Production acceptance test

Do not mark the worker live until all of these pass with a real APK:

1. API returns a queued run only after private APK upload size verification.
2. Worker authenticates, leases the run and downloads only the leased APK.
3. Worker verifies SHA-256 against the run record before ADB install.
4. Emulator install, launch, logcat capture and report submission complete.
5. A deliberate crash fixture is detected; a normal fixture does not produce a crash finding.
6. Battery saver and storage pressure read back correctly and are reset after success, failure, timeout and worker restart.
7. Network latency/bandwidth are read back; packet loss remains explicitly unsupported until a verified data-plane path is integrated.
8. Worker cannot reach host/private metadata endpoints from the APK network.
9. VM/emulator is reset before another customer's APK is processed.

A green Python unit-test suite does not satisfy this acceptance test.
