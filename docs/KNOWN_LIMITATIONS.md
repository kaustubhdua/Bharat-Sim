# BharatSim — Known Limitations

**Date:** 2026-11-21  
**Candidate branch:** `5b751f88ca8679e5cd32fbdc3eab289451f6aab0`

- Production readiness is HTTP 503: DB and private Storage unavailable, Android worker not configured.
- Arbitrary APK execution is intentionally disabled.
- Android smoke evidence is fixture-only and does not certify customer APKs or physical low-cost devices.
- Network controls are limited to selected latency/bandwidth fixture paths; packet loss/outage and generic app traffic verification unsupported.
- RAM is report-only; CPU pressure unsupported; persona profiles are requested settings rather than proof of applied conditions.
- Classifier uses small curated data; no independent held-out model metrics.
- Anomaly detection is deterministic heuristic/threshold logic, not a trained IsolationForest.
- Sarvam requires a backend-only secret; live provider outputs are unverified.
- JSON exports and analysis-level client-side PDF export exist. A persisted report library, run-level PDF export and sharing lifecycle are not implemented.
- Password recovery/verification resend UX, dedicated findings/reports resources, server-side history pagination and persistent account preferences are incomplete.
- Complete tenant isolation test matrix, independent security review, full accessibility audit and staging performance/load benchmark remain outstanding.
- The exact candidate CI and Vercel deployment status must pass before merge/release.
