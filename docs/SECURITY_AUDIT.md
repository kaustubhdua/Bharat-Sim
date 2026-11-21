# BharatSim — internal security control review

**Review type:** repository-level control review, not an independent penetration test or OWASP ASVS Level 2 certification.  
**Scope:** authentication, authorization, file ingestion, tenant boundaries, worker protocol and HTTP headers.  
**Automated coverage:** see `backend/tests/test_security.py`, `backend/tests/test_signed_uploads.py`, `backend/tests/test_worker_protocol.py` and the dependency-audit workflow.

## 1. Implemented controls

### Authentication and ownership
- Supabase access tokens are verified against the configured project's JWKS.
- The API derives `owner_id` from the verified token subject, not from a browser-supplied owner field.
- Run and analysis queries use owner-scoped predicates; cross-user object lookups are designed to return 404.
- JWT/owner-isolation unit tests cover representative API paths.

**Not yet accepted:** live two-user production testing across every private endpoint, signed URL, Storage object and report. Source-level checks and unit tests are not proof of production RLS behavior.

### APK intake
- Validates APK-like ZIP structure and Android manifest presence.
- Bounds archive entry counts, uncompressed size and compression ratio.
- Rejects path traversal entries and validates metadata before queueing.
- Uses SHA-256 to bind uploaded APK bytes to worker reports.
- Signed upload capabilities are generated for server-owned private object paths.

**Limit:** these checks are not malware scanning, code signing verification or sandboxing.

### Worker protocol
- Worker authentication uses a server-side token.
- Claims use short-lived leases; heartbeats renew the lease.
- APK download is lease-bound and SHA-256 checked.
- Stale/expired leases and duplicate result callbacks are rejected.
- Worker URLs are constrained to same-origin internal routes; credential-bearing redirects are refused.
- Common secret patterns are redacted from report text on a best-effort basis.

**Limit:** a worker token and a shared emulator do not create a per-job security boundary. The worker runner is not itself a sandbox.

### HTTP and browser controls
- CORS is restricted to configured origins.
- Security response headers include content-type and frame protections.
- Frontend secrets must never be placed in `VITE_*` variables.

## 2. Production security gates

- Confirm the authoritative Supabase Auth/Storage project and PostgreSQL database before applying migrations.
- Verify RLS and two-user read/write/delete denial on production.
- Verify private APK upload, signed download, deletion, expiry and orphan cleanup.
- Provision a dedicated per-job VM/microVM worker with default-deny egress, resource limits, patched images and process-tree teardown.
- Keep public APK execution disabled until independent worker isolation and egress evidence exists.
- Add malware/reputation scanning only if a suitable offline or isolated workflow is designed; do not confuse ZIP validation with malware detection.
- Complete an independent security review and incident/backup/restore exercise.

## 3. Security reporting language

The dependency audit and automated security tests are useful controls, not a zero-vulnerability guarantee. Do not call BharatSim ASVS Level 2 certified, penetration-tested or safe for arbitrary public APK execution until an independent assessment supports those claims.
