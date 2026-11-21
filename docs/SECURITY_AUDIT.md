# BharatSim — Security Audit

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21  
**Disposition:** Code/CI review only; not an independent penetration test or ASVS certification.

## Controls observed in repository

- Supabase Auth integration and asymmetric JWT verification code exist.
- Server-side owner scoping exists for core routes; migrations enable RLS.
- CI exercises disposable PostgreSQL migration/persistence and worker guard paths.
- Upload and comparison capabilities are gated on required backend dependencies.
- Arbitrary APK execution remains disabled until production storage/database and worker prerequisites exist.
- Dependency scanning has passed on prior candidate snapshots; that does not prove application security.

## Live observation

Production readiness returned HTTP 503 for database/private Storage and reported no configured Android worker. No destructive or intrusive production test was run.

## Release-critical security work

1. Exercise two-user authorization for all endpoints, artifacts, exports and signed URLs.
2. Run each untrusted APK inside a disposable per-job VM/equivalent strong sandbox.
3. Enforce default-deny egress and block metadata/host/internal network access.
4. Enforce CPU, memory, disk, process, wall-clock and network quotas.
5. Test malformed APK, MIME spoofing, ZIP bombs, traversal, package injection and command-injection boundaries.
6. Verify worker token lifecycle, stale/replayed callback rejection, leases, crash recovery and process cleanup.
7. Verify CORS, security headers, TLS, abuse controls, rate limiting, session expiry and safe error handling.
8. Rotate secrets through hosting secret management; never place server credentials in frontend env.

Keep `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED`, isolation attestation and restricted-egress flags false until independently verified.
