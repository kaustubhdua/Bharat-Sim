# Security model and release gates

BharatSim accepts APK files, which are untrusted executable code. The current repository contains defensive checks and an authenticated worker protocol, but these are not a complete production security boundary.

## Implemented controls

- Upload size cap, SHA-256 hashing, APK-like ZIP structure check, manifest presence, entry-count and declared uncompressed-size limits, encrypted-entry rejection, and suspicious compression-ratio checks.
- Worker endpoints use a dedicated shared secret with constant-time comparison and require a token of at least 32 characters.
- Jobs are leased to a worker; the lease token is required to download an APK, renew a lease, and submit a result.
- Expired leases are retried up to three claims. Stale/duplicate results are rejected.
- Inline worker result JSON is capped at 250 KB.
- Uploaded APKs are deleted after terminal worker results when filesystem cleanup succeeds; abandoned uploads expire after 24 hours during startup, run creation, or worker claim requests.
- The runner has an explicit opt-in environment guard, explicit Android serial, bounded duration, APK size limit, bounded archive metadata checks, and command timeouts.
- APK-derived Android package names are strictly validated before being passed to an ADB shell command, and the worker agent refuses HTTP redirects and rejects absolute, external, or non-worker route URLs in server-provided job fields before attaching worker credentials.
- Worker result callbacks validate report status and, when supplied, require the reported APK SHA-256 to match the leased artifact.
- The smoke runner attempts to uninstall the test package after execution and fails the run if cleanup fails, warning that a disposable VM reset is still the stronger isolation boundary.
- The network shaper is guarded and only accepts dedicated test interface names. Its apply action parses reported qdisc delay/jitter/loss/rate and compares them with requested values; this is configuration evidence, not proof of end-to-end emulator traffic conditions.

## Not yet implemented / not sufficient for public execution

- The shared API key and worker token are not user authentication, tenant isolation, or per-run user authorization.
- APK archive checks are not malware scanning and do not make an APK safe.
- The worker agent and runner do not create a sandbox by themselves. A compromised APK may act with the privileges of the Android guest and potentially attack reachable infrastructure.
- There is no per-run disposable VM snapshot/revert, hardened container/VM policy, verified network egress isolation, or complete cancellation of active device operations.
- Inline logcat evidence is bounded but not stored in dedicated private object storage with lifecycle/retention controls. The 24-hour upload expiry is request/startup-driven, not a background scheduler.
- There are no quotas, billing controls, per-user limits, or full audit trail for a multi-user service.
- A configured worker token means dispatch is configured; it does not prove a live worker or emulator exists.

## Before public APK execution

1. Add real user identity and per-run ownership; deny cross-user reads and downloads.
2. Place execution on a disposable VM or equivalent isolation boundary with no host secrets, no privileged container, no Docker socket, strict CPU/RAM/disk/time quotas, and restricted outbound network access.
3. Validate emulator and ADB boundaries; do not accept arbitrary shell commands, host paths, or device serials from API callers.
4. Store artifacts in private object storage using generated names, short-lived authorized downloads, encryption where appropriate, and documented deletion/retention.
5. Add upload/job quotas, concurrency limits, abuse monitoring, cancellation, and audit events.
6. Protect API and worker credentials, rotate them, and never put them in frontend environment variables or logs.
7. Test stale leases, replayed callbacks, cross-run access, oversized results, expired artifacts, worker crashes, and malicious APK fixtures.
8. Conduct a security review of the host isolation and egress policy before exposing the service to public users.

## Result integrity policy

- An uploaded or registered APK is not an executed APK.
- A worker result is accepted only for an active lease token.
- A completed smoke run means the runner completed its configured install/launch/observation/log-collection workflow; it is not proof that all app journeys passed.
- Log markers are heuristic evidence, not proof of root cause.
- Network and resource constraints must be labeled verified, unverified, or unsupported. The current runner does not apply them.
