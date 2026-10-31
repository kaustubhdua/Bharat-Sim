# Security model and release gates

BharatSim accepts APK files, which are untrusted executable code. The current repository contains defensive checks and an authenticated worker protocol, but these are not a complete production security boundary.

## Implemented controls

- Upload size cap, SHA-256 hashing, APK-like ZIP structure check, manifest presence, entry-count and declared uncompressed-size limits, encrypted-entry rejection, and suspicious compression-ratio checks.
- Worker endpoints use a dedicated shared secret with constant-time comparison and require a token of at least 32 characters.
- Jobs are leased to a worker; the lease token is required to download an APK, renew a lease, and submit a result.
- Expired leases are retried up to three claims. Stale/duplicate results are rejected.
- Inline worker result JSON is capped at 250 KB.
- Authenticated users can delete their own non-active runs. The API first atomically transitions queued/awaiting runs to `cancelled`, blocks deletion of leased/running jobs, removes the associated APK and run-linked analyses, and retains a cancelled row if storage cleanup fails so deletion can be retried.
- Run detail pages can export the stored report as a private, non-cacheable JSON download. The export contains the run metadata, the original report, a stable SHA-256 over canonical report JSON, and a separate SHA-256/ETag for the downloaded file.
- The authenticated worker status endpoint no longer returns `current_run_id`; it exposes only an online/busy summary so another tenant's run identifier is not disclosed.
- Before submitting worker evidence, common bearer credentials, key/token/password/secret key-value fields, secret query parameters, and JWT-shaped strings are redacted recursively from report text.
- When server-side Supabase Storage credentials are configured, APKs are streamed into the private `bharatsim-private` bucket using generated `runs/<uuid>/input.apk` object paths; worker downloads are proxied through the authenticated lease endpoint, and terminal results trigger object deletion. Local development without Storage credentials retains the local-filesystem path. Abandoned local/private uploads expire after 24 hours when cleanup is invoked during startup, run creation, or worker claim requests.
- The runner has an explicit opt-in environment guard, explicit Android serial, bounded duration, APK size limit, bounded archive metadata checks, and command timeouts.
- APK-derived Android package names are strictly validated before being passed to an ADB shell command, and the worker agent refuses HTTP redirects and rejects absolute, external, or non-worker route URLs in server-provided job fields before attaching worker credentials.
- Completed worker callbacks require a valid 64-character APK SHA-256 matching the leased artifact; failure callbacks may omit the hash when failure happens before download or runner execution.
- The smoke runner attempts to uninstall the test package after execution and fails the run if cleanup fails, warning that a disposable VM reset is still the stronger isolation boundary.
- The guarded network shaper is limited to dedicated test interfaces. Its apply action parses reported qdisc delay/jitter/loss/rate and compares them with requested values; this is configuration evidence, not proof of end-to-end emulator traffic.

## Not yet implemented / not sufficient for public execution

- The local API container runs as a non-root user with a read-only root filesystem, dropped Linux capabilities, no-new-privileges, and configured PID/memory limits. These reduce container privileges but are not an APK sandbox.
- The API now has an opt-in Supabase Auth JWT verification gate for customer-data endpoints. It verifies asymmetric ES256/RS256 tokens against the project's JWKS, validates issuer/audience/expiry/subject, rejects anonymous tokens, and scopes run/analysis reads and writes by the verified `sub` UUID. The local SQLite adapter adds nullable `owner_id` columns; the existing Supabase core schema already contains the matching owner columns.\n- The frontend now includes an optional Supabase email/password sign-in and account-creation flow when `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are configured. It stores the short-lived session in `sessionStorage`, refreshes access tokens before expiry, attaches the access token to API calls, and offers sign-out. End-to-end verification against the live project's enabled providers, email-confirmation settings, redirect configuration, and deployed environment variables is still required. Do not treat code integration alone as a production launch.\n- The optional shared API key and worker token are not user authentication, tenant isolation, or per-run user authorization.
- APK archive checks are not malware scanning and do not make an APK safe.
- The worker agent and runner do not create a sandbox by themselves. A compromised APK may act with the privileges of the Android guest and potentially attack reachable infrastructure.
- There is no per-run disposable VM snapshot/revert, hardened container/VM policy, verified network egress isolation, or complete cancellation of active device operations.
- Inline logcat evidence and worker reports remain bounded JSON in the database; they are not yet separate object artifacts. Report export is generated on demand from the stored JSON rather than persisted as a separate object. APK upload expiry is 24 hours but cleanup is request/startup-driven, not a background scheduler. Storage lifecycle rules and a background retention scheduler are not yet configured. Run-level deletion is available, but independent artifact-level deletion is not.
- There are no enforced per-user quotas, billing controls, concurrency limits, or complete audit trail for a multi-user service.
- A configured worker token means dispatch is configured; it does not prove a live worker or emulator exists.

## Before public APK execution

1. Integrate Supabase Auth sign-in/session refresh into the frontend, send access tokens only in Authorization headers, and test account lifecycle. Backend JWT verification and owner-scoped run/analysis access are now implemented behind `BHARATSIM_AUTH_REQUIRED=true`.
2. Place execution on a disposable VM or equivalent isolation boundary with no host secrets, no privileged container, no Docker socket, strict CPU/RAM/disk/time quotas, and restricted outbound network access.
3. Validate emulator and ADB boundaries; do not accept arbitrary shell commands, host paths, or device serials from API callers.
4. APK input artifacts now use the private `bharatsim-private` bucket and authenticated worker proxy; extend this to reports/logcat/screenshots, add short-lived user-authorized downloads, lifecycle rules, and documented deletion/retention.
5. Add upload/job quotas, concurrency limits, abuse monitoring, cancellation, and audit events.
6. Protect API and worker credentials, rotate them, and never put them in frontend environment variables or logs.
7. Test stale leases, replayed callbacks, cross-run access, oversized results, expired artifacts, worker crashes, and malicious APK fixtures.
8. Conduct a security review of the host isolation and egress policy before exposing the service to public users.

## Assessment scope and upstream references

BharatSim's install/launch/logcat smoke runner is an operational resilience test, not a mobile application security assessment and not an APK malware scanner. Do not advertise MASVS compliance or security certification based on a smoke run.

Use established open-source standards and tools when designing separate security-analysis features:

- [OWASP MASVS](https://github.com/OWASP/masvs) defines mobile application security verification controls.
- [OWASP MASTG](https://mas.owasp.org/MASTG/) provides test procedures and evidence guidance for Android/iOS app security assessment.
- [OWASP Mobile Application Security Testing guidance](https://owasp.github.io/DevSecOpsGuideline/2-Process/2-4-Test/2-4-3-Mobile-Application-Security-Test/) describes how static and dynamic tools fit into mobile security testing.
- [Android app security best practices](https://source.android.com/docs/security/best-practices/app) documents Android sandbox and process-isolation principles.
- [Appium UiAutomator2](https://appium.github.io/appium-uiautomator2-driver/) is the upstream UI automation driver used for the fixture journey.

These references are guidance, not a certification of BharatSim. Any future APK security-analysis feature needs its own threat model, safe execution environment, validated tooling, and evidence-backed acceptance tests.

## Result integrity policy

- An uploaded or registered APK is not an executed APK.
- A worker result is accepted only for an active lease token.
- A completed smoke run means the runner completed its configured install/launch/observation/log-collection workflow; it is not proof that all app journeys passed.
- Log markers are heuristic evidence, not proof of root cause.
- Worker report redaction is a best-effort defense-in-depth control, not a guarantee that all application-specific secrets or personal data are removed.
- Network latency and download/upload bandwidth controls can be applied and read back on a disposable Android Emulator; fixture CI additionally checks measured traffic behavior and reset for the source-built fixture only. The worker documents battery-saver and bounded storage-pressure operations with readback and cleanup, but these do not create a complete low-end-device persona or prove arbitrary APK behavior. Packet loss, CPU throttling and RAM restriction remain unsupported. Emulator control-plane readback alone is not proof that arbitrary application traffic traversed the shaped path.
