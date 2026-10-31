# BharatSim - Android Testing Engine (Person 2)
### HackFront India 2026 | T1.2 – The Cheap Phone Test

Automated Android testing engine that executes APK installation, package and activity resolution, application launch, real-time crash and ANR detection, logcat capture, and structured JSON reporting.

---

## 1. Architecture Overview

```
Bharatsim-person2/
├── android_testing_engine/
│   ├── __init__.py           # Package exports (TestRunner, ADBClient, etc.)
│   ├── adb_client.py         # Subprocess ADB wrapper, device detection, shell commands
│   ├── apk_parser.py         # Multi-tier APK parser (aapt -> pure Python AXML -> heuristics)
│   ├── crash_detector.py     # Logcat parser for FATAL EXCEPTION, native crashes, & ANRs
│   ├── models.py             # Structured schemas (TestReport, CrashDetail, DeviceInfo)
│   ├── runner.py             # Test orchestration & lifecycle execution
│   └── cli.py                # Command-line interface
├── tests/                    # Comprehensive test suite (13 passing tests)
│   ├── test_apk_parser.py
│   ├── test_crash_detector.py
│   ├── test_models.py
│   └── test_runner_mock.py
├── output/                   # Auto-generated artifacts
│   ├── reports/              # Structured JSON reports (<test_id>.json & latest_report.json)
│   └── logs/                 # Device logcat outputs (<test_id>.log)
├── main.py                   # Root executable entrypoint
├── requirements.txt          # Python dependencies
└── README.md                 # Complete documentation
```

---

## 2. Dependencies & Prerequisites

### Python Dependencies
- **Core Engine:** Uses standard Python 3.8+ library modules (`subprocess`, `zipfile`, `struct`, `dataclasses`, `json`, etc.). **Zero mandatory third-party dependencies required!**
- **Testing (Optional):** `pytest` for running unit test suite:
  ```bash
  pip install -r requirements.txt
  ```

### External Tool: Android Debug Bridge (`adb`)
`adb` must be installed on your system.
- If you have **Android Studio** installed, ADB is typically located at:
  `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`
- Or download standalone **Android SDK Platform-Tools for Windows**:
  1. Download: [https://developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools)
  2. Extract `platform-tools` (e.g. to `C:\Android\platform-tools`).
  3. Add that directory to your Windows System `PATH` environment variable.

---

## 3. Quick Start & Execution Commands

### A. Verify ADB & Environment
Check that ADB is accessible from Python:
```bash
python main.py check-adb
```

### B. Offline Self-Test (No Device or APK Required)
Run a complete simulated self-test that exercises the report pipeline, crash detection, and artifacts generation:
```bash
# Normal simulated test run (PASSED)
python main.py self-test

# Crash scenario simulation (CRASHED)
python main.py self-test --simulate-crash
```

### C. List Connected Devices / Emulators
```bash
python main.py devices
```

### C. Inspect APK Metadata (No Device Required)
Extract package name, launcher activity, and version information without a device:
```bash
python main.py parse-apk path/to/app.apk
```

### D. Run Automated Test on an APK
Run complete automated test (install -> launch -> 10s logcat monitor -> crash detect -> report):
```bash
python main.py run path/to/app.apk
```

#### Advanced CLI Options:
```bash
# Custom monitoring duration (e.g., 20 seconds)
python main.py run path/to/app.apk --duration 20.0

# Target specific device (when multiple devices/emulators connected)
python main.py run path/to/app.apk --device emulator-5554

# Explicit package name and launch activity overrides
python main.py run path/to/app.apk --package com.example.app --activity .MainActivity

# Auto-uninstall app after test completes
python main.py run path/to/app.apk --uninstall

# Custom output folder for reports and logs
python main.py run path/to/app.apk --output custom_output

# Specify custom ADB path
python main.py run path/to/app.apk --adb-path "C:\Android\platform-tools\adb.exe"
```

### E. Run Test Suite
```bash
python -m pytest tests/ -v
```

---

## 4. Integration Guide for Person 5 (Backend / API Developer)

The Person 5 backend developer can consume this module either **in-process (Python API)** or **via Subprocess (CLI)**.

### Option 1: Direct Python Integration (Recommended)
```python
from android_testing_engine import TestRunner

# Initialize runner
runner = TestRunner(output_dir="output", default_test_duration=10.0)

# Run test lifecycle
report = runner.run_test(
    apk_path="uploads/candidate_app.apk",
    test_duration=15.0,        # Test execution window in seconds
    uninstall_after_test=True  # Clean up after test
)

# Access fields directly
print(f"Overall Status: {report.overall_status}")       # PASSED | FAILED | CRASHED | ERROR
print(f"Package:        {report.package_name}")
print(f"Crash Detected: {report.crash_detected}")
print(f"Report JSON:    {report.to_json()}")

# Or obtain as Python dictionary
report_dict = report.to_dict()
```

### Option 2: JSON Output File Integration
Every test run automatically writes two persistent artifacts:
1. `output/reports/<test_id>.json` — Unique per-test structured report.
2. `output/reports/latest_report.json` — Guaranteed symlink/copy pointing to the most recent run.
3. `output/logs/<test_id>.log` — Full device logcat captured during the execution.

---

## 5. Structured Test Report Schema (JSON Specification)

```json
{
  "test_id": "test_20261031_130000_a1b2c3",
  "apk_name": "candidate_app.apk",
  "package_name": "com.example.candidate",
  "device_name": "Xiaomi Redmi 9A",
  "android_version": "10",
  "installation_status": "SUCCESS",
  "launch_status": "SUCCESS",
  "test_duration": 10.45,
  "crash_detected": true,
  "crash_details": [
    {
      "crash_type": "FATAL_EXCEPTION",
      "reason": "java.lang.NullPointerException: Attempt to invoke virtual method on a null object",
      "timestamp": "10-31 13:00:05.123",
      "pid": "1420",
      "process_name": "com.example.candidate",
      "stack_trace": [
        "10-31 13:00:05.123  1420  1420 E AndroidRuntime: FATAL EXCEPTION: main",
        "10-31 13:00:05.123  1420  1420 E AndroidRuntime: Process: com.example.candidate, PID: 1420",
        "10-31 13:00:05.123  1420  1420 E AndroidRuntime: java.lang.NullPointerException: ...",
        "10-31 13:00:05.123  1420  1420 E AndroidRuntime: \tat com.example.candidate.MainActivity.onCreate(MainActivity.java:30)"
      ]
    }
  ],
  "error_logs": [
    "10-31 13:00:05.123  1420  1420 E AndroidRuntime: FATAL EXCEPTION: main",
    "10-31 13:00:05.124  1000  1200 I ActivityManager: Process com.example.candidate (pid 1420) has died"
  ],
  "log_file_path": "F:\\Bharatsim-person2\\output\\logs\\test_20261031_130000_a1b2c3.log",
  "overall_status": "CRASHED",
  "timestamp": "2026-10-31T07:30:00.000000+00:00",
  "device_id": "9a8b7c6d5e",
  "activity_name": "com.example.candidate/.MainActivity",
  "installation_error": null,
  "launch_error": null
}
```

### Status Enum Values
| Field | Possible Values | Meaning |
|---|---|---|
| `installation_status` | `SUCCESS`, `FAILED`, `SKIPPED` | Result of `adb install -r -g` |
| `launch_status` | `SUCCESS`, `FAILED`, `SKIPPED`, `NOT_ATTEMPTED` | Result of `am start` or `monkey` |
| `overall_status` | `PASSED`, `FAILED`, `CRASHED`, `ERROR` | High-level summary of test |
| `crash_detected` | `true`, `false` | Whether fatal crash/ANR occurred |

---

## 6. How to Connect an Android Device / Emulator

### Connecting a Physical Phone (e.g. Budget Phone for HackFront):
1. **Enable Developer Options on phone:**
   - Go to `Settings` -> `About phone`.
   - Tap `Build number` 7 times until it says *"You are now a developer!"*.
2. **Enable USB Debugging:**
   - Go to `Settings` -> `System` (or `Additional settings`) -> `Developer options`.
   - Turn on **USB debugging**.
   - (For Xiaomi/Redmi devices, also turn on **Install via USB** and **USB debugging (Security settings)** if prompted).
3. **Connect phone to PC with USB cable:**
   - On the phone screen, a prompt will appear: *"Allow USB debugging?"*.
   - Check **"Always allow from this computer"** and tap **Allow**.
4. **Verify in terminal:**
   ```bash
   python main.py devices
   ```

### Connecting an Android Emulator:
1. In Android Studio, launch **Device Manager** and start any AVD (e.g., Pixel 4 with Android 10 or 11).
2. Or launch via command line:
   ```bash
   emulator -avd <avd_name>
   ```
3. Run `python main.py devices` to confirm it appears as `emulator-5554`.

---

## 7. Key Considerations & Limitations for Backend Developer (Person 5)

1. **Serial Execution per Device:**
   - ADB locks the installation and logcat streaming to the connected device. If running multiple tests in parallel, either assign distinct devices using `--device <serial_id>` or use a job queue (e.g. Celery / RQ / asyncio queue) to run tests sequentially on a single device.
2. **Low-End / "Cheap Phone" Timing (T1.2):**
   - Budget phones (1GB-2GB RAM, Android Go, quad-core) can take up to 8-15 seconds just to launch an application. We recommend configuring `test_duration` between `15.0` and `25.0` seconds when benchmarking cheap devices.
3. **Logcat Retention:**
   - Logcat buffers are limited on cheap devices (often 256KB). Our engine streams logcat in real time to disk during test execution so no crash lines are lost even if the buffer rolls over.
4. **Missing Activity Fallback:**
   - Some APKs do not declare an exported launch activity or obfuscate it. Our engine automatically falls back to Android's `monkey` launcher tool to trigger the default entry intent.
