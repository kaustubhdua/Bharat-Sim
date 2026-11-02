# Production completion execution plan

**Status: blocked for public production execution.** This document is an operator checklist and acceptance contract, not evidence that cloud infrastructure has been provisioned or production tests have passed.

## Release policy

- Keep `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`, `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`, and `BHARATSIM_WORKER_EGRESS_RESTRICTED=false` until the worker-host acceptance tests below pass independently.
- Never run customer APKs on the API host, Vercel functions, shared CI runners, or a generic developer sandbox. A Vercel sandbox is not a KVM worker host and does not establish a Firecracker isolation boundary.
- Do not use SQLite or ephemeral `/tmp` as production run state. Production startup must fail closed if PostgreSQL configuration is missing.
- Do not add broad `anon` or `authenticated` policies to private `bharatsim` tables merely to silence the Supabase RLS-without-policy advisor. Confirm schema/table grants and keep privileged operations server-side.
- Never paste credentials into GitHub issues, chat, source code, build logs, screenshots, or frontend variables.

## P0 — Provision a Firecracker worker host

### Infrastructure prerequisites

Provision a dedicated KVM-capable x86_64 Linux host. AWS's Firecracker getting-started guide uses a bare-metal EC2 instance because KVM access is not available on ordinary virtualized instances. Confirm the selected instance type explicitly supports nested/host virtualization and that `/dev/kvm` is available; do not assume a generic cloud VM qualifies.

Minimum host acceptance:
1. Dedicated worker account and patched Ubuntu LTS host/kernel/microcode; no customer workloads or unrelated services on the host.
2. KVM enabled; `/dev/kvm` ownership/mode restricted to the worker service.
3. Pinned, checksum-verified Firecracker VMM and matching jailer from the same patched supported release. Do not use versions affected by CVE-2026-1386 (Firecracker <=1.13.1 and 1.14.0); use a fixed release or newer supported release after reviewing upstream advisories.
4. Root-owned, non-writable executable, chroot base and network namespace paths. Jailer inputs and every parent directory must not be writable by untrusted users.
5. Jailer enabled with default restrictive seccomp; do not use `--no-seccomp` or a weaker custom filter without formal review.
6. Unique unprivileged UID/GID, jail and network namespace per run; cgroup v2 limits for CPU, memory, PIDs, block I/O and file size; bounded disk image and wall-clock deadline.
7. No host Docker socket, cloud instance metadata access, host credentials, host filesystem mounts, SSH agent, or shared writable directories in guests.
8. Default-deny host egress. Allow only the control-plane endpoints and explicitly required guest test endpoints through a policy-enforcing proxy. Deny RFC1918/link-local/loopback/metadata destinations and re-check DNS resolution at connection time to mitigate rebinding.
9. Host watchdog detects hung VMMs, kills them, destroys network namespace and cgroup, wipes per-run disk/memory artifacts, and records cleanup outcome.
10. Host patching, time synchronization, disk encryption, log shipping, metrics, backup and incident-response ownership documented.

### Per-run lifecycle acceptance

`queued -> leased -> booting -> running -> collecting -> terminal -> destroyed`

- Create unique run UID/GID, jail root, netns, cgroup and ephemeral guest disk.
- Inject only a short-lived run-scoped worker credential; never mount API/database/storage master credentials into the guest.
- Fetch APK through the lease-authenticated API path; verify SHA-256 inside the worker before install.
- Start emulator/Appium inside the guest; capture bounded logcat, screenshots and structured report.
- On completion, failure, cancellation, timeout, lease expiry, worker crash or host restart: stop guest, kill child processes, revoke run credentials, destroy netns/cgroup, wipe ephemeral disk and confirm no process or mount remains.
- Reconcile orphaned leases and orphaned host resources on boot and periodically. Reconciliation must be idempotent.
- Record signed/attested host identity, Firecracker version/checksum, policy version, resource limits and cleanup evidence with each run.

**Do not attest the host until an independent reviewer verifies the host configuration and negative tests.**

## P0 — Production database and storage credentials

For the exact Vercel backend project linked to this repository, verify server-only variables exist in the Production target:
- `BHARATSIM_DATABASE_URL`: Supabase Transaction Pooler connection string, SSL required; use port 6543, a dedicated least-privilege database role and transaction-safe schema selection. Do not place this in any `NEXT_PUBLIC_*` or `VITE_*` variable.
- `SUPABASE_URL`: HTTPS project URL.
- `SUPABASE_SECRET_KEY`: modern server-only secret API key (preferred), or legacy service-role JWT only when unavoidable.
- `BHARATSIM_STORAGE_BUCKET=bharatsim-private`.
- `BHARATSIM_AUTH_REQUIRED=true`.
- `BHARATSIM_ENV=production`.
- Production CORS must list only the canonical frontend origins.

Verify variable target, project ID and last-updated timestamp without decrypting or printing secret values. Restart/redeploy after changes. Do not share values with an operator or put them in logs.

Acceptance:
- `/health/ready` reports database, auth configuration and storage readiness independently; readiness must be false if a required production dependency is unavailable.
- API starts with PostgreSQL only; a test run survives a new function instance/restart and is visible from a second instance.
- Storage signed upload, TUS chunk upload, server-side HEAD size verification, SHA-256 verification, worker-only download and deletion all pass against the actual private bucket.
- A failed database or storage dependency returns a safe fail-closed response and a correlated redacted log entry.

## P0 — Supabase Auth lifecycle and tenant ownership

Run against a dedicated staging Supabase project first, then repeat smoke tests in Production using explicitly approved test accounts:
1. Sign up with email confirmation enabled; verify redirect URL and confirmation completion.
2. Sign in; verify non-anonymous JWT issuer, audience, subject, expiry and signing key.
3. Refresh the session repeatedly, including a transient network failure and retry; verify refresh-token rotation is serialized and tokens are never logged.
4. Sign out; verify client tokens are cleared. For sensitive operations requiring immediate revocation, validate the JWT `session_id` against `auth.sessions`; deleting a user alone does not invalidate an already issued JWT.
5. Expired, malformed, wrong-project, anonymous and revoked tokens are rejected.
6. User A cannot list, read, mutate, export, delete, cancel, upload to, or download User B's runs/artifacts by guessing IDs or paths.
7. A worker can access only the artifact attached to its currently leased run and only with the matching lease token.
8. Test quota boundaries, concurrent run creation, account deletion, audit events and orphaned data cleanup.

Use `auth.uid()` ownership policies only if browser roles are intentionally granted access. Otherwise keep the schema unexposed/server-only and use backend-verified identity plus owner-scoped SQL. Never authorize from user-editable `user_metadata`.

## P0 — Durable artifacts and retention

- Store APKs, logcat, screenshots, Appium evidence and reports as separate private objects with owner, run, type, size, MIME, SHA-256, created time, expiry and deletion state metadata.
- Use server-generated object paths; never trust caller-supplied paths or bucket names.
- Persist artifact metadata and run state transactionally or use an outbox/reconciliation strategy for the object-store/database dual write.
- Implement a scheduled retention worker (not request/startup-triggered cleanup only). It must be idempotent, retry transient failures, quarantine permanent failures, and emit metrics.
- Provide owner-authorized downloads using short-lived signed URLs or an authenticated streaming endpoint; never make the bucket public.
- Verify soft delete, hard delete, expired object cleanup, failed upload cleanup, orphan detection, export integrity, and backup/restore.
- Publish the retention period, maximum upload sizes, deletion SLA and support process.

## P0 — Worker controller, recovery and failure tests

The controller must have explicit state transitions, lease fencing, idempotent callbacks, bounded retries with backoff, and a dead-letter/reconciliation path. Test at minimum:
- VMM fails before guest boot.
- Emulator boot hangs or fails.
- APK install fails or package signature/manifest is invalid.
- App crashes; ANR occurs; device goes offline.
- Appium server/ADB child process hangs or exits unexpectedly.
- Job wall-clock deadline expires.
- User cancels queued, leased and running jobs.
- Lease expires while a worker is still running; stale worker callback is rejected.
- Duplicate completion/failure callback is idempotent.
- Worker process dies after report upload but before callback.
- API restarts during each lifecycle transition.
- Host reboots with active guests and orphaned cgroups/netns/jails.
- Storage delete fails and is later retried.
- Every terminal path verifies no guest, child process, mount, cgroup, netns or temporary credential remains.

For each case assert database state, event timeline, artifact integrity, cleanup evidence, retry count and alert emission. A test that merely marks a row failed without checking host resource teardown is insufficient.

## P0 — Coordinated deployment

1. Merge a reviewed release candidate; capture exact SHA and dependency lockfile hashes.
2. Pass backend, frontend, PostgreSQL integration, container build, worker guards, dependency audit and Android emulator smoke on that SHA.
3. Verify production DB/Auth/Storage variables in the exact backend project without revealing values.
4. Deploy backend first, verify readiness and migration compatibility, then deploy frontend built against the same API contract.
5. Promote only READY deployments from the intended SHA. A branch preview is not Production.
6. Verify custom domains, SSO/access protection, CORS, TLS, health/readiness, login, session refresh, cross-user denial, APK upload, worker run, report download and deletion.
7. Run a rollback rehearsal and retain the previous known-good deployment.
8. Keep public APK execution disabled until worker host attestation and end-to-end security acceptance are signed off.

## P1 — Frontend QA

- Run Playwright on Chromium, Firefox and WebKit at mobile (320/360/390 px), tablet and desktop viewports.
- Test keyboard-only operation, visible focus, semantic headings/landmarks, form labels, validation announcements, contrast, reduced motion, screen-reader names and touch targets.
- Add automated axe checks to key routes and fix all critical/serious violations; manually verify flows automated tools cannot assess.
- Test empty/loading/error/offline/expired-session/permission-denied/large-history states.
- Verify no horizontal overflow, clipped text, inaccessible dialogs, broken charts, or accidental secret/token display.
- Capture screenshots and trace artifacts for regressions; run on a real low-memory Android browser.

## P1 — Monitoring, alerts, backup and recovery

Instrument request IDs and structured redacted logs. Dashboards/alerts should cover API 5xx/latency, DB pool exhaustion/connection failures, auth failures, queue age/depth, lease expiry/retries, worker heartbeats, emulator boot time, VMM crashes, cleanup failures, storage errors/bytes, retention backlog, quota rejection and deployment health.

- Define SLOs, alert thresholds, escalation owner and on-call runbook.
- Enable Supabase database backups/PITR appropriate to the chosen plan and verify restore into an isolated project.
- Back up configuration and non-secret infrastructure definitions; secrets must be stored in the cloud secret manager with rotation and audit.
- Define RPO/RTO, incident severity, evidence preservation, breach response and customer notification process.
- Run a restore and worker-host rebuild drill before production sign-off.

## P1 — Network conditions and physical device

Supported network profiles must be backed by measured data-plane evidence, not profile labels or control-plane readback. Current CI proves a source-built fixture's HTTPS range request through an allowlisted CONNECT proxy at baseline, 384 kbps and 150 ms injected setup delay. It does not prove arbitrary APK traffic is routed through the proxy.

Keep packet loss, jitter, outage/reconnect, CPU throttling and RAM-pressure claims explicitly unsupported until independently measured. Add controlled loss/jitter/reconnect tests with a verified path, collect actual throughput/RTT/loss and reset all shaping state after each test.

Physical device acceptance must record exact model, chipset/RAM/storage, Android build/API, battery state, network, app build, test script, measured results, screenshots/logs and cleanup. Include a low-cost 2–3 GB RAM device representative of target users, test install/launch/upgrade/low-storage/background/permission/network-loss/payment/login journeys, and compare results against emulator baselines. A cloud virtual device is not a substitute for the requested physical device.

## Evidence register

Attach one dated record per acceptance item:
- commit SHA and CI run links;
- cloud resource IDs and host configuration attestation (never secrets);
- database migration list and read-only health queries;
- auth test account IDs (non-sensitive synthetic accounts only) and outcomes;
- object IDs, byte sizes and SHA-256 values (not signed URLs/tokens);
- worker lifecycle logs and cleanup verification;
- deployment IDs, production target and smoke test report;
- accessibility reports, browser versions, viewport screenshots;
- monitoring screenshots, backup/restore drill result;
- physical device model/build and test report.

**Completion is achieved only when every P0 and P1 item has evidence, the security review signs off, and the release owner explicitly approves production launch.**


## Live infrastructure verification — 2026-11-02

This section records a read-only inspection of the connected Supabase project and the unified Vercel project. It is evidence of configuration state at the inspection time, not a production acceptance sign-off.

### Supabase project

- Project ref: `hkyieaovolkethovyenb`; region: `ap-south-1`; database engine: PostgreSQL 17; project status: `ACTIVE_HEALTHY`.
- The live `bharatsim` schema contains the seven expected tables: `runs`, `analyses`, `workers`, `run_events`, `artifacts`, `quotas`, and `audit_events`. All seven have RLS enabled.
- Live migration history includes the four BharatSim migrations: `20261027054905`, `20261027061609`, `20261030181640`, and `20261101042942`.
- Direct privilege checks confirmed `anon` and `authenticated` have neither schema USAGE nor SELECT on BharatSim tables; `service_role` has SELECT. Keep this schema private and do not add client policies simply to silence the advisor.
- Private bucket `bharatsim-private` exists with a 157,286,400-byte maximum object size and APK/ZIP/octet-stream MIME allowlist.
- At inspection: zero Supabase Auth users, zero BharatSim runs, analyses, artifacts, and quotas. No real user-auth lifecycle or persisted customer workload has yet been proven.
- The Supabase project is shared with GenomeGuard. Do not run an isolated BharatSim-wide migration push, reset the project, or alter GenomeGuard objects. Use a coordinated migration owner or a separate project for future isolation.

### Unified Vercel environment

The linked unified project has the expected public Supabase URL/publishable key and BharatSim mode/auth/storage settings, but the following server-only settings were absent in the inspected environment inventory: `BHARATSIM_DATABASE_URL`, `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`), and `BHARATSIM_WORKER_TOKEN`. Do not infer a usable PostgreSQL connection from the Supabase MCP connection: the application needs a separately configured, SSL-protected connection string and server-only secret. Secret values were not read or printed.

The worker feature flags were false at inspection:

- `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`
- `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`
- `BHARATSIM_WORKER_EGRESS_RESTRICTED=false`

This is the correct fail-closed state until a dedicated per-job Firecracker host and its cleanup/network negative tests are independently accepted. No BharatSim worker service was present in the connected Render workspace at inspection; do not substitute a generic web service or shared VM and call it isolated execution.

### Remaining external acceptance gates

1. Configure the missing Vercel Production secrets from Supabase/Vercel secure dashboards; verify names and targets without exposing values.
2. Run real email signup/confirmation/login/refresh/logout and two-account isolation tests in the deployed app.
3. Provision and independently attest a dedicated KVM/Firecracker worker host; then set worker flags only after its negative egress and teardown tests pass.
4. Complete artifact object lifecycle integration and scheduled retention/reconciliation, then verify object metadata, signed download, expiry, deletion, and orphan cleanup against the private bucket.
5. Complete cancellation/recovery, full Appium journey, physical-device/network, accessibility, monitoring, backup/restore, and load-test acceptance as described above.

Do not treat INFO-only advisor notices or unused indexes on currently empty tables as release blockers by themselves. Revisit them after representative traffic. Do not change GenomeGuard-owned findings from this project-level audit.
