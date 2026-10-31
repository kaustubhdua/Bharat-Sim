# BharatSim architecture

## Current implementation

The repository provides a FastAPI service, a React/Vite dashboard, deterministic persona profiles and risk-ranked scenario planning, SQLite local persistence plus an opt-in PostgreSQL adapter, bounded APK upload validation, evidence-linked log analysis, and an authenticated worker-dispatch protocol. Optional Supabase Auth JWT verification and owner-scoped run/analysis operations are implemented behind a production configuration gate.

## Data flow

1. The browser fetches personas and submits an APK with a selected persona.
2. The API validates the extension and APK-like ZIP metadata, enforces a size limit, stores the file under a generated run identifier, and calculates SHA-256.
3. If BHARATSIM_WORKER_TOKEN is configured, the run enters queued; otherwise it remains awaiting_worker.
4. The worker agent claims a queued run and receives a short-lived lease token. The token is required to download the run's APK, renew the lease, and submit a result.
5. The worker runs the bounded ADB smoke runner against its explicitly configured disposable Android device. It submits the structured report and bounded logcat evidence; the API rejects stale leases and stores the accepted result.
6. After a terminal result is saved, the API attempts to delete the uploaded APK. The report remains attached to the run record.
7. Developers can paste logcat text. The analyzer detects known markers, retains line references, fingerprints signals, and returns cautious next steps.
8. The score is a disclosed heuristic over detected signals only; it is not a population estimate.

## Worker and trust boundaries

The worker agent and runner are separate from the API process, but they do not themselves create a sandbox. They must be deployed on a disposable, restricted host/VM with no production secrets, strict resource limits, restricted outbound networking, and clean-up policies. Do not expose public APK execution until the host-level isolation and multi-user authorization design have been reviewed.

Current worker protocol controls include:
- authenticated claim requests and per-run lease tokens;
- five-minute lease with heartbeat renewal and up to three claims after abandoned leases;
- APK download authorization tied to the active lease;
- stale/duplicate result rejection and a 250 KB inline result limit;
- worker heartbeat display in the dashboard;
- APK deletion after a terminal result, when filesystem deletion succeeds.

Production gaps remain: live Auth/database/Storage runtime configuration is not verified; the API still defaults to SQLite locally; reports/logs/screenshots are inline JSON rather than durable object artifacts; there is no per-job disposable VM snapshot/revert, active-job cancellation with child-process teardown, enforced quotas, background retention scheduler, or complete audit trail.

## Network shaping

Linux tc/netem can emulate latency, jitter, loss, and rate limits on a controlled host network, but does not automatically shape traffic inside every Android Emulator topology. The guarded network shaper is still a standalone prototype and is not invoked by the worker agent. Validate the path with a known test endpoint and record measured/applied conditions. Do not display a profile as applied merely because the UI selected it.

## Security

APK files and logs are untrusted inputs. The API checks archive shape and size but does not perform malware analysis and is not a secure execution sandbox. Before public deployment, verify live Supabase Auth/session settings and per-run authorization against the deployed environment, then add enforced quotas, retention/cleanup scheduling, private report/log/screenshot storage, restricted egress, and VM-grade isolated worker execution. Owner-scoped run deletion and integrity-checked report export exist, but do not replace durable artifact storage or active-job cancellation. Never send logs to a hosted AI service without explicit consent.
