# Local deployment with Docker Compose

This stack builds the FastAPI API and the React dashboard, persists API data in a named volume, and proxies API paths through nginx so the frontend uses same-origin requests. It binds the web port to loopback by default and is intended for local evaluation—not public multi-user APK execution.

## Start locally

Install Docker Engine and the Compose plugin. From the repository root:

    docker compose up --build -d
    docker compose ps
    curl http://127.0.0.1:8080/health/ready

Open http://127.0.0.1:8080. API docs are available at http://127.0.0.1:8080/docs. To use another local port, set BHARATSIM_PORT before running Compose.

To stop while preserving the named data volume:

    docker compose down

To delete all local persisted data too:

    docker compose down -v

## Runtime mode and production guard

The default Compose configuration is for loopback-only local development (`BHARATSIM_ENV=development`). If `BHARATSIM_ENV=production`, the API refuses to start unless `BHARATSIM_REQUIRE_API_KEY=true`, `BHARATSIM_API_KEY` is at least 32 characters, `BHARATSIM_AUTH_REQUIRED=true`, and `SUPABASE_URL` is an HTTPS project URL. Production mode also requires `BHARATSIM_DATABASE_URL` and an explicit TLS mode for remote PostgreSQL, plus a server-only `SUPABASE_SERVICE_ROLE_KEY` for the private `bharatsim-private` Storage bucket. The auth gate verifies Supabase asymmetric JWTs against the project's JWKS and scopes run/analysis access by user UUID. The dashboard includes email/password sign-in and account creation when built with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (publishable/legacy anon key only). Configure the matching server-side `SUPABASE_URL`, `BHARATSIM_AUTH_REQUIRED=true`, `SUPABASE_SERVICE_ROLE_KEY`, and `BHARATSIM_STORAGE_BUCKET=bharatsim-private`. APKs are streamed into this private bucket and served to workers only through lease-authenticated API downloads. Never expose a service-role/secret key. Verify the project's email-confirmation and allowed redirect settings before launch. These checks do **not** make public arbitrary-APK execution safe.

## Optional single-tenant API key

For a private single-operator instance, enable the shared API key before starting the stack:

```bash
export BHARATSIM_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export BHARATSIM_REQUIRE_API_KEY=true
docker compose up --build -d
```

The key is passed to the API and the nginx container as a server-side environment variable. Nginx injects it only on proxied `/api/` requests; it is not embedded in the Vite bundle or returned to browser JavaScript. Keep the key private and rotate it by restarting the stack with a new value. This is a **shared single-tenant gate**, not user identity, tenant isolation, or a substitute for a production authentication system. If the key is required but missing or shorter than 32 characters, the API fails closed.

To run the default loopback-only local evaluation without this gate, leave `BHARATSIM_REQUIRE_API_KEY` unset. Do not expose the stack publicly.

## Optional local worker

The Compose stack does not run an Android emulator. Provision a disposable emulator separately and configure a random BHARATSIM_WORKER_TOKEN in the shell before starting the API. Use the same token on the worker. Start worker/agent.py on a host that can reach the published loopback port, with an explicit ANDROID_SERIAL and BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true. For loopback-only local testing, set BHARATSIM_API_URL=http://127.0.0.1:8080 and BHARATSIM_ALLOW_INSECURE_HTTP=true in the worker environment.

Do not use plain HTTP for remote workers. Use HTTPS and a restricted network path for any remote deployment.

## Production deployment blockers

Do not expose this stack directly to the public internet. Before public use, verify the existing Supabase Auth sign-in/session refresh against the live project's provider, email-confirmation, redirect, expiry and logout settings, and run cross-user authorization tests against the deployed environment. Then add enforced rate limits/quotas, durable report/log/screenshot object storage and retention, strict worker VM isolation, egress restrictions, active-job cancellation with process teardown, audit logging, backups, monitoring, and a reviewed TLS/reverse-proxy configuration. Owner-scoped run deletion and integrity-checked report export are implemented; they do not provide active-job cancellation or durable artifact lifecycle. The shared worker token protects machine-to-machine endpoints; it is not user authentication. The local Compose UI binds to 127.0.0.1 by design.
