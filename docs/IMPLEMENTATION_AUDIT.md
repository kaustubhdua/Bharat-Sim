> Historical implementation snapshot (21 Nov 2026). Several statuses in this matrix are obsolete (including ML, TTS, exploration and production persistence). Do not use it as the current feature inventory. See [docs/MASTER_FEATURE_INVENTORY.md](MASTER_FEATURE_INVENTORY.md) and [docs/FINAL_PRODUCT_AUDIT.md](FINAL_PRODUCT_AUDIT.md) for current audited status.

# BharatSim — Full Implementation Audit & Feature Status Matrix

**Date:** 21 November 2026  
**Auditor:** BharatSim Core Engineering Team  
**Repository:** [kaustubhdua/Bharat-Sim](https://github.com/kaustubhdua/Bharat-Sim)  
**Target Deployment:** [https://bharat-sim-81g2.vercel.app](https://bharat-sim-81g2.vercel.app)

---

## 1. Executive Summary

This comprehensive audit catalogs the state of the BharatSim platform at the start of the final push. BharatSim has a strong core with 142+ passing backend tests, clean TypeScript interfaces, and deterministic heuristics for constraint planning. However, key production connections (live Supabase credentials in Vercel), ML-based classification (currently regex rules), Sarvam text-to-speech audio streaming, and seamless evaluator walkthroughs require completion.

---

## 2. Feature-by-Feature Status Matrix

| ID | Feature | Current Status | Existing Code Location | Gap / Required Action |
|:---|:---|:---:|:---|:---|
| **F01** | **User Authentication & Signup** | 🟡 Partially Implemented | `frontend/src/auth.ts`, `backend/app/main.py` (JWKS) | Supabase Auth JWT verification exists behind `BHARATSIM_AUTH_REQUIRED=true`; need complete UI signup/login/profile flow with graceful local fallback. |
| **F02** | **Tenant Isolation & RLS** | 🟢 Implemented (Verified) | `supabase/migrations/*.sql`, `backend/app/main.py` | Schema isolation (`bharatsim` schema), RLS enabled, per-user ownership and quota checks (10 daily / 2 active) verified in tests. |
| **F03** | **APK Upload & Validation** | 🟢 Implemented (Verified) | `backend/app/main.py`, `frontend/src/storageUpload.ts` | ZIP validation, compression ratio check, SHA-256 fingerprinting, direct-to-storage signed TUS capabilities chunked in 6 MiB. |
| **F04** | **APK Metadata & Manifest Parser** | 🟢 Implemented (Verified) | `worker/android_testing_engine/apk_parser.py` | Pure-Python AXML parser fallback extracting package name, main activity, version, and min/target SDK. |
| **F05** | **Device Personas (4 Bharat Profiles)** | 🟡 Partially Implemented | `backend/app/main.py`, `worker/condition_planner.py` | 4 personas defined (Budget Android, Edge Village, Storage Pressure, Baseline). Need to expand to official set: **Budget Android**, **Edge Village**, **Crowded Station (3G)**, and **Congested Urban 4G**. |
| **F06** | **Android Worker Dispatch & Queue** | 🟢 Implemented (Verified) | `backend/app/main.py`, `worker/agent.py` | Authenticated claim, 5-minute lease tokens, heartbeat renewals, single active-job lock per worker slot, stale result rejection. |
| **F07** | **ADB Runner & Exploration** | 🟡 Partially Implemented | `worker/runner.py`, `worker/condition_applicator.py` | Smoke runner installs and launches APK; need to add bounded `adb shell monkey` automated UI exploration with strict app-locking. |
| **F08** | **Network Shaping & Simulation** | 🟢 Implemented (Verified in CI) | `scripts/ci/https_shaping_proxy.py`, `worker/runner.py` | Host-side allowlisted HTTP CONNECT proxy (384 kbps cap, 150 ms latency), emulator console shaping, and standalone Linux `tc/netem` prototype. |
| **F09** | **Performance & Telemetry Capture** | 🟡 Partially Implemented | `worker/runner.py`, `worker/android_testing_engine` | Captures start time and exit codes; need structured `dumpsys gfxinfo` (jank/slow frames), `cat /proc/meminfo`, and mobile data usage recording. |
| **F10** | **Logcat Failure Detection** | 🟢 Implemented (Verified) | `worker/android_testing_engine/crash_detector.py` | Regex state machine for Java FATAL EXCEPTION, native crashes (SIGSEGV/SIGABRT), ANRs, and Low Memory Killer (`lmkd`). |
| **F11** | **ML Failure Classification** | 🔴 Missing (Currently Regex) | `backend/app/main.py` | Currently uses deterministic regex rules. Must train and embed a genuine `scikit-learn` TF-IDF + Logistic Regression/SGD classifier pipeline (`scripts/train_classifier.py`). |
| **F12** | **ML Anomaly Detection** | 🔴 Missing | `backend/app/evidence_fusion.py` | Need `IsolationForest` and Z-score regression detection comparing baseline vs. constrained execution across cold start, frame drops, and memory. |
| **F13** | **Bharat Readiness Score** | 🟡 Partially Implemented | `backend/app/main.py` | Heuristic score exists; needs integration with ML classification probabilities and telemetry deltas. |
| **F14** | **Sarvam AI Explanations & Fixes** | 🔴 Missing (Only Translation) | `backend/app/sarvam.py` | Currently only translates text; need Sarvam LLM diagnostic synthesis to generate plain-language developer fixes. |
| **F15** | **Sarvam AI Translation** | 🟢 Implemented | `backend/app/sarvam.py`, `frontend/src/components/SarvamTranslation.tsx` | Hindi (`hi-IN`), Tamil (`ta-IN`), Marathi (`mr-IN`) translation working for text $\le 2000$ chars. |
| **F16** | **Sarvam AI Text-to-Speech (TTS)** | 🔴 Missing | None | Need `POST /api/v1/translate/audio` via Sarvam Bulbul TTS and an in-dashboard streaming audio player. |
| **F17** | **Evaluator Quick Tour** | 🔴 Missing | None | Need prominent "⚡ Load Live Evaluator Scenario" with Scenario A (Fintech UPI Timeout) and Scenario B (Quick-Commerce OOM). |
| **F18** | **Reporting & Exports (PDF & JSON)** | 🟡 Partially Implemented | `backend/app/main.py`, `frontend/src/components/RunDetailView.tsx` | JSON export exists with SHA-256 integrity hash; need printable/downloadable PDF report export. |
| **F19** | **UI/UX Polish (Linear/Sentry Design)** | 🟡 Partially Implemented | `frontend/src/App.tsx`, `frontend/src/styles.css` | Dark mode and cards exist; need cohesive navigation, tabs, telemetry cards, and audio playback widgets. |
| **F20** | **Live Production Persistence** | 🔴 Blocked by Config | `backend/app/main.py` | `/health/ready` returns 503 because `BHARATSIM_DATABASE_URL` is missing in Vercel production settings. |

---

## 3. High-Priority Remediation Plan

1. **P0: ML Pipeline (`scikit-learn`)**:
   - Create `scripts/train_classifier.py` using LogHub Android logs + labeled failure markers.
   - Train and export `failure_classifier.joblib` and TF-IDF vectorizer.
   - Integrate classifier into `backend/app/ml_classifier.py` and call during log analysis.
   - Implement `IsolationForest` anomaly detector in `backend/app/anomaly_detector.py`.

2. **P0: Device Personas Expansion**:
   - Update `PERSONAS` dictionary in `backend/app/main.py` and `worker/condition_planner.py` to match the 4 required profiles:
     1. *Budget Android* (2 GB RAM, 720p, battery saver).
     2. *Edge Village* (Rural network, 450 ms latency, 8% packet loss).
     3. *Crowded Station* (Congested 3G, variable latency, packet loss).
     4. *Congested Urban 4G* (High jitter, bandwidth contention).

3. **P0: Sarvam AI Deepening (LLM + Bulbul TTS)**:
   - Enhance `backend/app/sarvam.py` with:
     - Plain-language developer explanation & remediation prompt.
     - `POST /api/v1/translate/audio` using `bulbul:v1`.
   - Update frontend with embedded audio player.

4. **P1: Evaluator Quick Tour**:
   - Add pre-packaged, authenticated demonstration scenarios for instant evaluator inspection:
     - Scenario A: Fintech UPI Checkout Timeout under Edge Village network.
     - Scenario B: Quick-Commerce Low-Memory Killer Crash on Budget Android.

5. **P1: Automated Exploration with `adb monkey`**:
   - Add bounded exploration command in `worker/runner.py`:
     `adb shell monkey -p <package> --throttle 250 --pct-touch 70 --pct-motion 20 --pct-syskeys 0 --pct-appswitch 0 100`.

6. **P1: Export Capabilities**:
   - Implement structured client-side PDF export / print styling for reports.

7. **P2: Documentation & Security Packaging**:
   - Update `README.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `docs/SECURITY.md`, and `docs/ARGOSX_REMEDIATION.md`.

