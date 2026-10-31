# Reproducible Android emulator smoke test

BharatSim's Android emulator workflow validates two separate things:

1. The real local product path: FastAPI upload → queued run → authenticated worker lease → ADB install/launch/logcat → worker callback → persisted run report.
2. A controlled Appium network experiment from the fixture Android app, using the active Android `Network` socket factory and a real HTTPS transfer.

The workflow uses a source-built fixture APK. It does not execute an arbitrary customer APK.

## What the workflow verifies

### Product execution path

- Starts a disposable Android emulator with Wi-Fi disabled and checks the observed supported transport.
- Starts a local FastAPI instance and a worker with an ephemeral CI-only token.
- Waits for the worker to register before uploading any APK.
- Uploads the fixture APK through the same API used by the dashboard.
- Verifies queue claim, lease, ADB install, launch, logcat collection, APK SHA-256, and the saved worker report.
- Exercises a real Android install-signature conflict and an intentionally invalid APK. Both must fail closed, preserve failure evidence, and attempt cleanup.
- Stores JSON reports, worker/API logs, Appium logs, screenshots, and a SHA-256 evidence manifest in the GitHub Actions artifact.

### Network data-plane experiment

- The fixture downloads exactly 256,000 bytes from the repository-controlled `smoke-android/probe-256k.bin` object over `raw.githubusercontent.com` HTTPS.
- The workflow resolves the host to IPv4 on the CI runner, pins the fixture socket to that address, and still validates TLS using the HTTPS hostname for SNI and certificate verification.
- The Appium journey runs one warm-up and three samples for baseline, bandwidth-only, and latency-only conditions.
- It records HTTP status, exact bytes read, elapsed time, active Android transport, requested and observed emulator profile, and median deltas.
- It requires the configured bandwidth and latency effects to exceed the test thresholds, then resets emulator network controls and verifies the reset.
- The CI workflow also runs an independent Linux `netem` traffic-shaper check. That proves the Linux shaping path; it does not substitute for the Android fixture's own traffic-path evidence.

The harness uses the built-in UMTS emulator profile and checks the profile values against the actual API 35 emulator image's console readback. The control-plane status is recorded separately from the measured fixture transfer. A control-plane readback alone is never treated as a successful bandwidth measurement.

## What a passing result means

A passing run proves that the source-built fixture app completed the tested HTTP transfers through the observed Android emulator transport under the configured conditions, produced repeatable median deltas, and reset the emulator controls.

It does **not** prove:

- arbitrary third-party APK traffic behaves the same way;
- production or public-Internet bandwidth/latency for a real user;
- physical low-cost Android device fidelity;
- packet-loss, CPU-throttling, or unsupported condition simulation;
- production worker isolation or public arbitrary-APK execution.

The earlier Cloudflare speed-test endpoint repeatedly stalled on the first bandwidth-only request after successful baseline requests. The current test uses a controlled static fixture object hosted on GitHub's HTTPS CDN to avoid depending on a public speed-test endpoint's per-client throttling. The data transfer itself still occurs over a real external HTTPS path from Android.

## Run it in CI

Open GitHub Actions → **Android emulator smoke evidence** → **Run workflow**. It also runs on pull requests that change the worker, worker tests, Android fixture, CI scripts, or this workflow.

Download the `bharatsim-android-emulator-smoke` artifact. Inspect:

- `api-run.report.json` — successful product execution report;
- `install-failure.report.json` and `negative-run.report.json` — fail-closed negative fixtures;
- `appium-journey.report.json` — baseline/latency/bandwidth samples and reset evidence;
- `appium-failure-logcat.txt` — device-side diagnostics if the network journey fails;
- `evidence-manifest.json` — SHA-256 and size for each retained evidence file.

Artifacts are retained by GitHub Actions for 14 days. They are CI evidence, not durable customer-run storage.

## Upstream references

- Android Emulator command-line networking: https://developer.android.com/studio/run/emulator-commandline
- Android Emulator console network controls: https://developer.android.com/studio/run/emulator-console
- Appium UiAutomator2: https://appium.github.io/appium-uiautomator2-driver/latest/
- Linux `netem`: https://www.man7.org/linux/man-pages/man8/netem.8.html
