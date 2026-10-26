# API reference

FastAPI's interactive schema is available at /docs when the backend is running.

## Public application endpoints

- GET /health/live — process liveness.
- GET /health/ready — database readiness; does not assert that an Android worker is online.
- GET /api/v1/capabilities — current implementation flags and limitations.
- GET /api/v1/personas — supported test personas.
- POST /api/v1/plan — deterministic risk-ranked scenario plan.
- POST /api/v1/runs — multipart form with persona_id and optional APK file.
- GET /api/v1/runs — recent run metadata.
- GET /api/v1/runs/{run_id} — run state and worker-submitted report, if present.
- GET /api/v1/workers — workers whose heartbeat was observed in the last 90 seconds.
- POST /api/v1/analyze/logs — deterministic analysis of supplied log text.
- GET /api/v1/analyses — recent saved log analyses.

When BHARATSIM_REQUIRE_API_KEY=true, /api/v1 routes require X-BharatSim-API-Key. This is a single shared-key gate for private deployments, not multi-user authentication.

## Worker protocol

The worker protocol is enabled when BHARATSIM_WORKER_TOKEN is configured to a secret of at least 32 characters. Each internal worker request must include X-BharatSim-Worker-Token. Never expose this token in frontend code.

- POST /internal/worker/claim — JSON body: {"worker_id":"android-worker-01"}. Returns {"job":null} when no job is available or a leased job with run ID, APK SHA-256, lease token, and relative callback URLs.
- GET /internal/worker/runs/{run_id}/apk — download the APK attached to the current lease using the X-BharatSim-Lease-Token header.
- POST /internal/worker/runs/{run_id}/heartbeat — JSON body: {"lease_token":"..."}; extends the five-minute lease.
- POST /internal/worker/runs/{run_id}/result — JSON body contains lease_token, status (completed or failed), result object, and optional error. Result JSON is capped at 250 KB. A completed status requires result.status=completed.

Lease tokens are per-run capabilities and must be kept secret. Stale/expired lease callbacks are rejected. Leases expire after five minutes and can be re-claimed up to three attempts; expired runs beyond that attempt cap are marked failed.

## Run states

- awaiting_worker — no authenticated worker dispatch token was configured when the run was created, or no APK was attached.
- queued — an APK was saved and worker dispatch is configured.
- leased — a worker claimed the job.
- completed — the runner reports that its configured smoke workflow finished and the report was accepted. This does not mean every app journey passed.
- failed — the runner reported an execution failure or the lease expired after the retry cap.

## Security and limits

- APK uploads are size-limited and validated as APK-like ZIP archives with bounded metadata. This is not malware scanning.
- Uploaded APKs are deleted after terminal worker results when filesystem cleanup succeeds. Abandoned uploads expire after 24 hours during startup, run creation, or worker claim requests; this is not a background scheduler.
- Worker reports are limited to 250 KB inline; production deployments should use private artifact storage for larger evidence.
- The worker can apply Android Emulator console latency and bandwidth settings and verifies control-plane readback/reset. CI has measured increased latency for the source-built fixture on the emulator network path; this is not arbitrary-app proof. Packet loss, outage/recovery, CPU/RAM/storage pressure, and app-specific UI journeys remain unsupported.
- Do not expose public APK execution until user identity/ownership, isolated worker execution, quotas, egress restrictions, and artifact retention controls are implemented and reviewed.
