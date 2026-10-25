# Reproducible Android emulator smoke test

BharatSim includes a small, known-good Android fixture app and a GitHub Actions workflow that builds it, boots a disposable Android emulator, starts a local FastAPI instance and authenticated worker with an ephemeral token, uploads the fixture through the API, verifies the queue/lease/ADB/result-callback path and saved report, then runs an Appium UI journey.

## What this proves

When the Android emulator smoke evidence workflow passes, it demonstrates that the checked-in runner can, in that CI environment:
1. Observe an online emulator.
2. Read package metadata from a built APK.
3. Install the APK.
4. Launch its launcher activity.
5. Collect logcat evidence.
6. Emit a report with the APK SHA-256 and expected package name.
7. Attempt uninstall cleanup.

The workflow uploads its report as a short-lived GitHub Actions artifact. It does not submit to the production API and does not prove arbitrary third-party apps work.

## Run it

Open GitHub Actions, select Android emulator smoke evidence, and choose Run workflow. It also runs on pull requests changing the runner, runner tests, smoke app, or this workflow. Inspect the run and download the bharatsim-android-emulator-smoke artifact.

## Explicit limitations

- This is an isolated CI fixture, not physical-device validation.
- The fixture has no external network requests; it does not prove netem shaping reaches emulator traffic.
- The workflow also runs an Appium/UiAutomator2 journey that asserts the fixture title, taps the primary-action button, checks the resulting UI state, and saves a screenshot. This is a fixture-app journey, not a user journey for arbitrary uploaded apps.
- It does not test RAM, storage, or CPU pressure.
- It does not establish production multi-user auth, worker VM isolation, artifact storage, or public deployment readiness.
- The emulator workflow is separate from fast CI to keep normal PR checks quick.

## Upstream projects

- Android Emulator / ADB: https://developer.android.com/studio/run/emulator-commandline
- Appium UiAutomator2: https://appium.github.io/appium-uiautomator2-driver/latest/
- Linux netem: https://www.man7.org/linux/man-pages/man8/netem.8.html
