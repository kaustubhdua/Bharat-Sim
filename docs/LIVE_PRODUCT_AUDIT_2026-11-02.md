# BharatSim live product audit — 2026-11-02

**Decision: not production-ready. Keep the public APK execution guardrails disabled.** This is a point-in-time operational audit, not a certification.

## Repository and automated verification

- Default branch: `main`.
- Audited main SHA: `80634cc4356b12bd4fcfb2a48ae3ef41318a4da9`.
- Dashboard design PR #104 is merged. It combines field-first visual clarity inspired by [Nihdhoom](https://github.com/kaustubhdua/nihdhoom) with a structured engineering-console hierarchy inspired by [Jai-hack](https://github.com/kaustubhdua/jai-hack).
- Post-merge CI [41343948538](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41343948538) passed: backend, worker safety, PostgreSQL integration, frontend build, frontend Playwright E2E, and container/Compose smoke.
- Dependency audit [41343948568](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41343948568) passed. A passing dependency audit is not a security certification.
- CI uses a source-built fixture APK and a disposable emulator. This proves the controlled fixture journey, not arbitrary customer APK safety or production worker isolation.

## Live deployment inventory

The inspected Vercel Production deployments are READY, but they are not a coordinated release:

| Component | Deployment | Commit | Assessment |
|---|---|---|---|
| Backend | `dpl_7omfvTUmRbzpN31b5vHMC9Q37TsG` | `895a2779dfd409ddc483c20745c418a251b81fdb` | Readiness fix deployed; production persistence credentials not present in exact env inventory |
| Frontend | `dpl_Do49P4uhN4bfiSHZ13p1JmnGioxD` | `23f14d95b8fa986fc36fd5f6306e007e6050ff0b` | Older UI; does not include PR #104 design |

The latest backend deployment's aliases include `https://bharat-sim-bay.vercel.app`; the frontend stable alias is `https://bharat-sim-81g2.vercel.app`. Direct page/health retrieval was not independently verifiable through the available web fetch, so READY deployment metadata is not represented as an HTTP smoke test.

### Backend Production environment inventory

The exact backend Vercel project/team Production inventory lists:
- `BHARATSIM_ENV=production`
- `BHARATSIM_AUTH_REQUIRED=true`
- `SUPABASE_URL`
- `BHARATSIM_STORAGE_BUCKET=bharatsim-private`
- `BHARATSIM_CORS_ORIGINS`
- `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`
- `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`
- `BHARATSIM_WORKER_EGRESS_RESTRICTED=false`

It does **not** list `BHARATSIM_DATABASE_URL`, `SUPABASE_SECRET_KEY`, or `SUPABASE_SERVICE_ROLE_KEY`; the returned hidden Production environment count was zero. No values were decrypted. This finding is limited to this project/team scope and must not be generalized to unrelated Vercel projects or credentials stores.

## Live Supabase common1 check

Project `hkyieaovolkethovyenb` is `ACTIVE_HEALTHY`, ap-south-1, PostgreSQL 17.11. A read-only count query returned:

| Resource | Rows |
|---|---:|
| Auth users | 0 |
| `bharatsim.runs` | 0 |
| `bharatsim.artifacts` | 0 |
| `bharatsim.workers` | 0 |
| `bharatsim.audit_events` | 0 |

The prior infrastructure audit found the private `bharatsim-private` bucket and private `bharatsim` schema with RLS enabled and browser roles lacking schema usage. Do not add broad browser grants or policies to clear INFO lints: the application is designed to access these tables server-side after its own JWT/ownership checks.

Latest Supabase advisors returned 30 INFO `rls_enabled_no_policy` notices (7 BharatSim, 23 GenomeGuard) and 28 INFO unused-index notices (13 BharatSim, 15 GenomeGuard). The RLS notices are consistent with the intentionally private schema/grant model; verify grants again before any change. Unused-index notices are not a reason to drop indexes on empty tables. Do not modify GenomeGuard objects as part of this project.

## UI/product quality findings

- The dashboard visual refresh is merged but not yet in the inspected frontend Production deployment.
- The overview now needs to present live API/worker/capability state rather than decorative device mock metrics.
- Built-in sample log content has been removed in the follow-up UI branch; log analysis should run only on user-submitted content. Predefined persona profiles are configuration templates, not measured physical-device data, and must remain labeled as profiles/targets.
- A run planner is not an executed test. A worker smoke run is not proof of app quality. A heuristic log signal is not a confirmed root cause. The UI and report must preserve these distinctions.
- The product should use precise labels for supported, read-back verified, traffic-path verified, report-only and unsupported controls. No packet-loss, CPU-pressure or physical-device support claims without corresponding evidence.

## Security and infrastructure release blockers

1. Add the common1 Transaction Pooler database URL to the backend Production project, with TLS required and the correct Vercel/serverless pooler settings.
2. Add a modern Supabase server-only secret key (preferred) or legacy service-role key to the backend Production secret store. Never expose it in browser variables, GitHub, source code, chat or logs. Supabase documents that secret keys bypass RLS and must stay in trusted server-side components: https://supabase.com/docs/guides/getting-started/api-keys
3. Verify live Auth Site URL and redirect allowlist, then exercise signup/email confirmation/signin/refresh/expiry/signout with real users and tokens.
4. Prove PostgreSQL create/read/update/delete across separate API invocations and restarts; prove private Storage upload/verify/download/delete using a non-production test object and clean it up.
5. Provision a dedicated KVM-capable worker host. Use a currently supported pinned Firecracker release (v1.17.0 was latest at audit time), verify official checksum/signature and advisories at install time, and use the matching jailer binary. Follow upstream production guidance for default seccomp, jailer, trusted paths, per-run UID/GID, cgroups, resource limits, host patching, no shared host mounts/secrets and an external watchdog:
   - https://github.com/firecracker-microvm/firecracker/releases
   - https://github.com/firecracker-microvm/firecracker/blob/main/docs/prod-host-setup.md
   - https://github.com/firecracker-microvm/firecracker/blob/main/docs/jailer.md
6. Prove default-deny worker egress from inside the guest, including private/link-local/metadata destination denial and DNS-rebinding controls. A CONNECT proxy allowlist must not permit arbitrary destinations.
7. Prove full lifecycle: lease, boot, execute, collect, callback, terminal state, VM destruction, disk/memory cleanup, cancellation and crash recovery. No shared CI runner or API host can substitute for a production isolation boundary.
8. Complete cross-tenant denial tests for every customer-data endpoint, upload quotas, artifact retention/deletion, signed URL expiry, replay protection and incident response.
9. Deploy frontend and backend from the same reviewed release SHA, then run a real browser journey against those deployed services and record the exact deployed SHA and test artifact.
10. Run a physical low-cost Android device validation before claiming physical-device fidelity. Keep packet loss, outage/recovery and CPU throttling unsupported until implemented and measured.

## Release guardrails

Keep all three backend Production values false until independently attested:
- `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`
- `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`
- `BHARATSIM_WORKER_EGRESS_RESTRICTED=false`

Do not provision paid infrastructure or change unrelated Render/GenomeGuard services without explicit authorization and a verified budget. A successful local CI run, READY deployment metadata, a green health endpoint, or an attractive UI alone does not meet production acceptance.

## Research references

- Firecracker v1.17.0 release: https://github.com/firecracker-microvm/firecracker/releases
- Firecracker production host setup: https://github.com/firecracker-microvm/firecracker/blob/main/docs/prod-host-setup.md
- Firecracker getting started and binary provenance: https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md
- Supabase API key security: https://supabase.com/docs/guides/getting-started/api-keys
- Supabase Storage access control: https://supabase.com/docs/guides/storage/security/access-control
- Android Virtualization Framework overview (ARM64 Android-device capability, not a substitute for a cloud KVM host): https://source.android.com/docs/core/virtualization
