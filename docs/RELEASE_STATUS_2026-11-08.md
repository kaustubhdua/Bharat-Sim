# BharatSim — release status snapshot

**Snapshot:** 2026-11-08  
**Decision:** controlled-beta MVP; no-go for public arbitrary APK execution.

## Latest verified repository checks

The current worker-protocol changes are on `main` at `0328d9a9960a33c6e831bf4478bb020564869df7`.

- Main CI passed: backend, frontend, frontend E2E, PostgreSQL integration, worker guards, container build and unified Vercel build.
- Android emulator smoke passed on the tested fixture workflow.
- The worker protocol now reserves a worker slot before claim and refuses a second claim while the same worker holds a live lease. The regression test confirms the first lease and second queued job remain intact.

These checks establish repository/CI behavior. They do not establish that a production worker host exists or that an arbitrary APK can be safely executed.

## Production gates still open

### Server-side persistence and identity

Configure in the backend hosting environment only:

- `BHARATSIM_DATABASE_URL`: production PostgreSQL connection string, preferably the supported pooler endpoint.
- `SUPABASE_SECRET_KEY` or the explicitly supported legacy `SUPABASE_SERVICE_ROLE_KEY`: server-side Storage access.
- Confirm the Supabase project URL, Auth issuer/JWKS, allowed redirect URLs and production CORS origins.
- Verify Auth sign-in, token expiry/refresh, owner scoping, private bucket upload/download, run creation, report persistence and deletion against the live deployment.
- Prove persistence across API restart and backup/restore.

Never place database credentials or Supabase secret/service-role keys in `VITE_*`, browser code, source control or issue logs.

### Isolated Android worker

The production trust boundary remains a disposable KVM-backed Firecracker microVM per job. Before provisioning, verify the current supported Firecracker release, its official checksums/signatures and security advisories; use the matching VMM and jailer.

Required evidence:

- Dedicated KVM host; no execution inside Vercel, a shared container or a personal device.
- Root-owned jailer paths, default seccomp, separate cgroups and hard CPU/memory/disk/process/time limits.
- Host-controlled default-deny egress, including denial of metadata, loopback, private IPv4/IPv6 and host/other-tenant networks.
- Per-run short-lived capabilities; no general cloud credentials, database secrets or broad Storage keys in the guest.
- Host-side watchdog, forced termination and verified VM/disk/credential cleanup on success, timeout, crash and controller restart.
- Repeated create → fixture execute → evidence upload → destroy cycles, including malicious-egress and forced-crash tests.

Keep all execution safety flags false until independent verification:

- `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`
- `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`
- `BHARATSIM_WORKER_EGRESS_RESTRICTED=false`

### Release acceptance

Only after the above infrastructure is configured:

1. Deploy the exact tested `main` SHA without bypassing provider build quotas.
2. Verify the deployed SHA and public routes.
3. Run authenticated upload-to-report and delete flows.
4. Verify readiness accurately reports database, private Storage and worker status.
5. Run cross-tenant denial, stale/duplicate lease, worker crash, cancellation and cleanup tests.
6. Record artifacts, hashes, owner and go/no-go decision in [PRODUCTION_RELEASE_GATES.md](PRODUCTION_RELEASE_GATES.md).

Until then, keep the public planner/demo available only within its documented scope, keep APK execution disabled, and do not describe BharatSim as a production device-testing service.
