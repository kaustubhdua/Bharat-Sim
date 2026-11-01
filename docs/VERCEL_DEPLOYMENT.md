# Vercel deployment and common1 Supabase wiring

This runbook describes the two existing Vercel projects and the environment contract expected by the code. It does not contain credentials.

## Existing projects (audited 2026-11-01)

| Role | Vercel project | Framework | Stable project alias |
|---|---|---|---|
| Dashboard | `bharat-sim-81g2` | Vite | `https://bharat-sim-81g2.vercel.app` |
| API | `bharat-sim` | FastAPI | `https://bharat-sim-bay.vercel.app` |

Both projects currently report Vercel SSO protection enabled for all non-custom domains. Their latest production deployments report READY, but the projects report `live: false`. A READY build is not proof of an authenticated, persistent, publicly accessible application. Keep SSO protection enabled until the app-level authentication and persistence checks below pass.

## Environment-variable audit

The latest environment inspection (2026-11-01) confirms that the public frontend variable names are now aligned:

- Dashboard: `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_PUBLISHABLE_KEY` are configured for Production and Preview. The Preview API URL is branch-specific.
- API: `SUPABASE_URL`, `BHARATSIM_ENV`, `BHARATSIM_AUTH_REQUIRED`, `BHARATSIM_STORAGE_BUCKET`, and `BHARATSIM_CORS_ORIGINS` are configured. Preview uses development mode with ephemeral SQLite; Production is set to production mode.
- API credentials `BHARATSIM_DATABASE_URL` and `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`) are not present in the inspected environment. `BHARATSIM_WORKER_TOKEN` and `SARVAM_API_KEY` are also not configured.
- Never rename a server secret to a `NEXT_PUBLIC_*` or `VITE_*` variable. Only the Supabase publishable key belongs in the browser.

## Dashboard project variables

Configure these on the `bharat-sim-81g2` Vercel project for Production and Preview:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` (Production) | `https://bharat-sim-bay.vercel.app` |
| `VITE_API_BASE_URL` (Preview) | The matching backend branch alias, currently `https://bharat-sim-git-feat-tus-resumable-apk-upload-jyc-website.vercel.app` |
| `VITE_SUPABASE_URL` | The HTTPS project URL for common1 |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | The common1 publishable key (the code also accepts the legacy `VITE_SUPABASE_ANON_KEY`) |

The current frontend defaults `VITE_API_BASE_URL` to an empty string. Because the dashboard and API are separate Vercel projects, leaving it empty sends requests to the dashboard origin rather than the FastAPI project. Production and Preview use separate values so a preview dashboard does not accidentally call the production API.

## API project variables

Configure these on the `bharat-sim` Vercel project. Keep every value server-side:

| Variable | Requirement |
|---|---|
| `BHARATSIM_ENV` | `production` |
| `BHARATSIM_DATABASE_URL` | common1 Supabase **Transaction pooler** URI from the dashboard Connect panel, with `sslmode=require` |
| `SUPABASE_URL` | common1 HTTPS project URL |
| `SUPABASE_SECRET_KEY` | common1 modern `sb_secret_...` server-only key (preferred); sent in `apikey` only. Legacy `SUPABASE_SERVICE_ROLE_KEY` JWT is supported as fallback. |
| `BHARATSIM_AUTH_REQUIRED` | `true` |
| `BHARATSIM_STORAGE_BUCKET` | `bharatsim-private` |
| `BHARATSIM_CORS_ORIGINS` | Exact dashboard origin(s), comma-separated; include the production dashboard aliases and the active preview dashboard branch alias; remove stale branch aliases when preview deployments are retired |
| `BHARATSIM_WORKER_TOKEN` | Strong random value of at least 32 characters, only after the isolated worker is provisioned |
| `SARVAM_API_KEY` | Optional server-only key; required to enable the Sarvam capability |

The API's production startup requires PostgreSQL, verified Supabase Auth, and the server-side Storage credential. When Storage is enabled, the dashboard requests a short-lived signed upload capability and transfers APK bytes directly to the private bucket using the TUS resumable protocol in 6 MiB chunks; this bypasses Vercel Functions' 4.5 MB request-body cap and supports retries after unstable-network interruptions. The API checks the stored object size before queueing, and the worker independently checks the SHA-256. Without Storage configured, the production UI blocks files larger than 4 MB rather than letting Vercel return a 413. The API uses `/tmp/bharatsim` as writable scratch space on Vercel. The optional shared `BHARATSIM_API_KEY` is not required for a Supabase-authenticated browser application and must not be placed in frontend code. Leave `BHARATSIM_REQUIRE_API_KEY=false` unless a private server-side gateway is deliberately configured to inject it.

### Why transaction pooler mode

Vercel functions are short-lived/serverless. Supabase recommends the shared Transaction pooler for serverless application traffic. The backend's psycopg connection sets `prepare_threshold=None`, because transaction pooler mode does not support prepared statements. It applies `SET LOCAL search_path TO bharatsim, public` inside every transaction rather than relying on session-level state, which transaction poolers do not preserve. Use the exact URI shown by common1's Connect panel rather than guessing a pooler hostname or region. Keep SSL enabled.

## Supabase prerequisites

1. Confirm the `bharatsim` schema and the `bharatsim-private` bucket exist in common1. The bucket must remain private.
2. Confirm the core, foreign-key-index, and signed-upload size migrations are present in remote migration history.
3. Enable the email/password Auth provider if password sign-in is the selected onboarding method.
4. Set the allowed redirect URLs for the dashboard's production and preview origins.
5. Never grant browser roles direct access to the private `bharatsim` schema or any server-side Supabase secret key.

## Environment state observed during the 2026-11-01 integration pass

The following non-secret configuration has been applied directly to the two Vercel projects:

- Frontend: `VITE_API_BASE_URL` is split by target (production API alias for Production, matching feature-branch API alias for Preview); common1 `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` are configured for both.
- Backend: `SUPABASE_URL`, `BHARATSIM_AUTH_REQUIRED=true`, `BHARATSIM_STORAGE_BUCKET=bharatsim-private`, and explicit CORS origins are configured for both.
- Backend: `BHARATSIM_ENV=production` is Production-only. Preview uses `BHARATSIM_ENV=development` and is for protected UI/integration smoke tests only; its SQLite `/tmp` database is ephemeral and must not be used for real user data.

The following required values are not present in the inspected Vercel environment and must be added before production can start: `BHARATSIM_DATABASE_URL`, `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`). `BHARATSIM_WORKER_TOKEN` and `SARVAM_API_KEY` are also not configured. The production API deliberately fails closed without the database and server-only Storage credential. No production deployment or real APK upload/execution is claimed.
## Deployment audit observed on 2026-11-01

- The latest Production deployment for both Vercel projects still references commit `e20f933523bbda56c4a4688d1260a93d8265c3fc`. The current GitHub `main` commit is newer: `a8f4b3310c5d5b0dfca161a6500d31087de887fa`.
- The frontend's most recent preview build for an intermediate TUS-fix commit failed because its tests still expected the old `/storage/v1/upload/resumable/sign` path. The tests and implementation were corrected, the corresponding GitHub CI build passed, and the fix was merged into `main`. That earlier failed Vercel preview is not the current main build.
- Subsequent Vercel deployment-creation requests were rejected with HTTP 402, resource `api-deployments-free-per-day`, because the team exceeded 100 deployments in the daily window. Vercel returned a 24-hour retry period. Do not repeatedly retry or bypass this limit; wait for the quota window to reset or have the account owner resolve the plan limit.
- Both projects still have SSO protection enabled for non-custom domains. The latest production deployment records are READY, but they are old builds and do not prove that the newly merged code is live.

This means GitHub `main` is updated, but the current Vercel Production aliases have **not** been verified against the latest commit. Once the deployment quota resets, deploy a Preview from the current main commit first, inspect the build logs and protected preview, then deploy Production only after the missing database and Storage credentials have been added.

## Safe rollout order

1. Add the missing server-only API variables directly in Vercel; the frontend variable names are already aligned. Do not expose service-role, database, worker, or Sarvam secrets to the browser.
2. Verify the API starts with PostgreSQL and that `/health/ready` reports database readiness. Confirm a create/read/delete run round trip persists across separate API invocations.
3. Verify sign-up/sign-in, refresh, expiry, sign-out, and cross-user 404/denial behavior against common1.
4. Verify private APK upload, lease-authorized worker download, terminal cleanup, and object deletion.
5. Configure `VITE_API_BASE_URL` and exact CORS origins; test dashboard API requests with an authenticated user.
6. Provision the worker on a disposable VM with strict egress and resource limits; then add `BHARATSIM_WORKER_TOKEN` and verify a real upload-to-report journey.
7. Add `SARVAM_API_KEY` only if the Sarvam partner feature is required; verify a real Hindi, Tamil, and Marathi translation call.
8. Only after these checks pass, review whether Vercel SSO protection can be disabled for the production aliases. Application-level Supabase Auth must remain enabled.

## Current blockers

The Vercel variable audit confirms that the public frontend variable names and non-secret backend settings are now aligned. It still does not show the required API database URL or server-side Supabase secret key. No database password or Supabase secret/service-role credential is available through the current project inspection. These values must be added by the project owner directly in Vercel; do not paste them into GitHub or chat. The latest production deployments still point to an older commit, and the projects remain SSO-protected. Until the credentials are added and the new commit is deployed and verified, the production API must not be considered connected to common1, and the dashboard must not be considered end-to-end live.
