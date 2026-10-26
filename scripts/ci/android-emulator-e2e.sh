#!/usr/bin/env bash
set -euo pipefail

adb wait-for-device
deadline=$((SECONDS + 60))
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)" = "1" ]; do
  if (( SECONDS >= deadline )); then
    echo "Android emulator did not finish booting" >&2
    exit 1
  fi
  sleep 2
done

export ANDROID_SERIAL=emulator-5554
# Preserve the emulator's available network so the fixture can make a real HTTP
# request. If the active transport is Wi-Fi, the report must keep traffic-path
# verification false unless a supported transport is actually observed.
export BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true
export BHARATSIM_API_URL=http://127.0.0.1:8000
export BHARATSIM_ALLOW_INSECURE_HTTP=true
export BHARATSIM_WORKER_ID=ci-emulator-worker
export BHARATSIM_POLL_SECONDS=1
export BHARATSIM_SMOKE_DURATION_SECONDS=20
export BHARATSIM_WORKER_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export BHARATSIM_DATA_DIR="$RUNNER_TEMP/bharatsim-api-data"

mkdir -p artifacts

# The Android fixture uses a real public HTTPS payload endpoint. DNS is configured
# by the emulator workflow; a remote endpoint is required to verify the emulator's
# actual routed traffic shaping rather than only local host-alias traffic.
(cd backend && exec uvicorn app.main:app --host 0.0.0.0 --port 8000) > artifacts/api.log 2>&1 &
API_PID=$!
WORKER_PID=
APPIUM_PID=
cleanup() {
  # Always restore network controls, even when Appium assertions fail.
  adb -s emulator-5554 emu network delay none >/dev/null 2>&1 || true
  adb -s emulator-5554 emu network speed full >/dev/null 2>&1 || true
  adb -s emulator-5554 shell svc wifi enable >/dev/null 2>&1 || true
  adb -s emulator-5554 shell svc data enable >/dev/null 2>&1 || true
  [ -z "$APPIUM_PID" ] || kill "$APPIUM_PID" 2>/dev/null || true
  [ -z "$WORKER_PID" ] || kill "$WORKER_PID" 2>/dev/null || true
  [ -z "$API_PID" ] || kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

python - <<'PY'
import time
import urllib.request
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=2).read()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("BharatSim API did not become ready")
PY

python worker/agent.py > artifacts/worker.log 2>&1 &
WORKER_PID=$!

curl --fail --silent --show-error \
  -F persona_id=baseline \
  -F "apk=@smoke-android/app/build/outputs/apk/debug/app-debug.apk;type=application/vnd.android.package-archive" \
  http://127.0.0.1:8000/api/v1/runs > artifacts/upload-response.json

python - <<'PY'
import json
import time
import urllib.request
from pathlib import Path

uploaded = json.loads(Path("artifacts/upload-response.json").read_text())
run_id = uploaded["id"]
if uploaded["status"] != "queued":
    raise SystemExit(f"APK was not queued: {uploaded}")

deadline = time.monotonic() + 180
final = None
while time.monotonic() < deadline:
    with urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/runs/{run_id}", timeout=5) as response:
        final = json.load(response)
    if final["status"] in ("completed", "failed"):
        break
    time.sleep(2)
if not final or final["status"] != "completed":
    raise SystemExit(f"End-to-end worker run did not complete: {final}")

result = final.get("result") or {}
assert result.get("apk_sha256") == uploaded["apk"]["sha256"], "APK evidence hash mismatch"
assert result.get("runner_return_code") == 0, result
assert result.get("package_name") == "org.bharatsim.smokeapp", result.get("package_name")
assert result.get("execution_scope") == "install_launch_logcat_smoke", result
assert result.get("constraints_applied") is False, result
network_profile = result.get("network_profile") or {}
assert network_profile.get("control_plane", {}).get("status") == "verified", network_profile
assert network_profile.get("network_constraints_applied") is True, network_profile
# The worker report may claim traffic-path verification only if its own
# logcat probe observed the required transport and latency. Otherwise it must
# remain explicitly partial; the separate Appium journey below verifies a
# real request while a fresh profile is active.
if network_profile.get("traffic_path_verified") is True:
    assert str(result.get("constraint_verification", "")).startswith("fixture_network_path_verified"), result
else:
    assert network_profile.get("traffic_path_verified") is False, network_profile
    assert str(result.get("constraint_verification", "")).startswith("partial_network_control_verified"), result
assert network_profile.get("reset", {}).get("status") == "verified", network_profile
for step_name in ("install_apk", "launch_app", "collect_logcat"):
    step = next((s for s in result.get("steps", []) if s.get("name") == step_name), None)
    assert step and step.get("return_code") == 0, f"{step_name} failed: {step}"

report = {
    "status": final["status"],
    "run_id": run_id,
    "apk_sha256": uploaded["apk"]["sha256"],
    "result_status": result.get("status"),
    "execution_scope": result.get("execution_scope"),
    "requested_persona_id": result.get("requested_persona_id"),
    "constraints_applied": result.get("constraints_applied"),
    "result_interpretation": result.get("result_interpretation"),
    "steps": [s.get("name") for s in result.get("steps", [])],
    "fatal_exception_marker": result.get("fatal_exception_marker"),
    "api_saved_report": True,
}
Path("artifacts/api-run.report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
PY

# Exercise the real worker failure callback with an APK-shaped archive whose
# manifest is deliberately invalid. It must end in a failed report and must
# never be represented as a successful execution.
python - <<'PYNEG'
import zipfile
from pathlib import Path
with zipfile.ZipFile("artifacts/invalid-manifest.apk", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("AndroidManifest.xml", b"not a compiled Android manifest")
    archive.writestr("classes.dex", b"not dex bytecode")
PYNEG
curl --fail --silent --show-error \
  -F persona_id=baseline \
  -F "apk=@artifacts/invalid-manifest.apk;type=application/vnd.android.package-archive" \
  http://127.0.0.1:8000/api/v1/runs > artifacts/negative-upload-response.json

python - <<'PYNEG'
import json
import time
import urllib.request
from pathlib import Path

uploaded = json.loads(Path("artifacts/negative-upload-response.json").read_text())
run_id = uploaded["id"]
if uploaded["status"] != "queued":
    raise SystemExit(f"Negative fixture was not queued: {uploaded}")
deadline = time.monotonic() + 90
final = None
while time.monotonic() < deadline:
    with urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/runs/{run_id}", timeout=5) as response:
        final = json.load(response)
    if final["status"] in ("completed", "failed"):
        break
    time.sleep(1)
if not final or final["status"] != "failed":
    raise SystemExit(f"Invalid APK fixture did not fail closed: {final}")
result = final.get("result") or {}
if result.get("status") != "failed":
    raise SystemExit(f"Failure callback did not preserve runner failure: {result}")
if result.get("runner_return_code", 0) == 0:
    raise SystemExit(f"Invalid APK unexpectedly returned runner success: {result}")
if not result.get("error"):
    raise SystemExit(f"Failure report did not explain why execution failed: {result}")
Path("artifacts/negative-run.report.json").write_text(json.dumps({
    "status": final["status"],
    "run_id": run_id,
    "fixture_kind": "intentionally_invalid_apk_manifest",
    "runner_return_code": result.get("runner_return_code"),
    "error": result.get("error"),
    "result_interpretation": result.get("result_interpretation"),
    "constraints_applied": result.get("constraints_applied"),
}, indent=2))
print(json.dumps({"status": final["status"], "fixture_kind": "intentionally_invalid_apk_manifest",
                  "runner_return_code": result.get("runner_return_code"), "error": result.get("error")}, indent=2))
PYNEG

# The Appium journey runs a warm-up plus three baseline, three latency-only,
# and three bandwidth-only HTTP transfers of a controlled payload through the
# emulator network stack, then verifies the emulator controls reset to defaults.
# This deterministically validates emulator shaping; it does not claim public-Internet performance.
adb install smoke-android/app/build/outputs/apk/debug/app-debug.apk

# A hosted Pixel emulator can occasionally leave a system "launcher isn't
# responding" dialog in front of the app after cold boot. The launcher is not
# the target under test, so dismiss that stale host-UI state and verify that
# the fixture activity itself can be foregrounded before Appium attaches.
adb -s emulator-5554 shell am force-stop com.google.android.apps.nexuslauncher >/dev/null 2>&1 || true
adb -s emulator-5554 shell input keyevent 4 >/dev/null 2>&1 || true
adb -s emulator-5554 shell am start -W -n org.bharatsim.smokeapp/.MainActivity > artifacts/fixture-activity-preflight.log
grep -q "Status: ok" artifacts/fixture-activity-preflight.log

appium --address 127.0.0.1 --port 4723 > artifacts/appium-server.log 2>&1 &
APPIUM_PID=$!
python worker/tests/appium_smoke_journey.py --artifacts artifacts
