# Vercel deployment and common1 Supabase wiring

This runbook describes the two existing Vercel projects and the environment contract expected by the code. It does not contain credentials.

## Existing projects (audited 2026-11-01)

| Role | Vercel project | Framework | Stable project alias |
|---|---|---|---|
| Dashboard | `bharat-sim-81g2` | Vite | `https://bharat-sim-81g2.vercel.app` |
| API | `bharat-sim` | FastAPI | `https://bharat-sim-bay.vercel.app` |

Both projects report Vercel SSO protection enabled for non-custom domains. The latest production deployments are READY and have the stable aliases assigned, but they serve commit `2b125971f8ab6c7c0e943d57790b4ae631021dbd`; GitHub `main` is two commits ahead at `453e417be76562288afc956e545c2d5822643e07`. GitHub's latest Vercel deployment checks report `build-rate-limit`, so the current main revision and new PR previews have not been deployed. A READY build is not proof of an authenticated, persistent, working application. Keep SSO protection enabled until the app-level authentication and persistence checks below pass.

## Environment-variable audit

The latest environment inspection (2026-11-01) confirms that the public frontend variable names are now aligned:

- Dashboard: `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_PUBLISHABLE_KEY` are configured for Production and Preview. The Production API base URL is correct. The current Preview API base URL still points to an older `feat/tus-resumable-apk-upload` branch alias; refresh it only after a matching backend preview deployment is available, and do not treat it as a validated preview.
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

The following required values are not present in the inspected Vercel environment and must be added before production can start: `BHARATSIM_DATABASE_URL`, `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`). `BHARATSIM_WORKER_TOKEN` and `SARVAM_API_KEY` are also not configured. The production API deliberately fails closed without the database and server-only Storage credential. Vercel Production deployment artifacts exist, but no operational production release, live common1 persistence, real APK upload, or Android worker execution is claimed.
## Deployment audit observed on 2026-11-01

- The latest Production deployment for both Vercel projects is READY at commit `2b125971f8ab6c7c0e943d57790b4ae631021dbd`. GitHub `main` is currently `453e417be76562288afc956e545c2d5822643e07` (two commits ahead). The production aliases therefore do not yet include the latest main commit.
- The frontend's most recent preview build for an intermediate TUS-fix commit failed because its tests still expected the old `/storage/v1/upload/resumable/sign` path. The tests and implementation were corrected, the corresponding GitHub CI build passed, and the fix was merged into `main`. That earlier failed Vercel preview is not the current main build.
- GitHub's Vercel status checks currently report `build-rate-limit` for both projects. Do not repeatedly retry or bypass the account's build limit; wait for Vercel to permit builds again or have the account owner resolve the plan limit.
- Both projects still have SSO protection enabled for non-custom domains. The latest production deployment records are READY and aliases are assigned, but they serve the previous main commit. The backend is also missing required production database and Storage credentials, so READY must not be interpreted as an operational API. The production worker safety flags are explicitly present and false; worker dispatch remains closed until a disposable VM and default-deny egress policy are independently verified.

This means GitHub `main` is updated, but the current Vercel Production aliases are one commit behind. Once the build-rate limit permits deployments, deploy a Preview from current `main`, inspect build logs and the protected preview, and deploy Production only after the missing database and Storage credentials have been added.

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

The Vercel variable audit confirms that the public frontend variable names and non-secret backend settings are aligned. The backend Production environment is missing `BHARATSIM_DATABASE_URL` (the Supabase common 1 Transaction Pooler URI) and `SUPABASE_SECRET_KEY` (the server-only Supabase secret key). No database password or Supabase secret/service-role credential is available through project inspection; the project owner must add these values directly in Vercel and must not paste them into GitHub or chat. `BHARATSIM_REQUIRE_API_KEY` is an optional additional shared-key gate, not a required production setting when Supabase JWT authentication is enabled. The production API currently fails startup/readiness because the database URL and server-side secret are absent. A dedicated isolated Android worker host is also not provisioned/attested, so production APK execution must remain fail-closed. The projects remain SSO-protected. Until the credentials are added, a deployment is permitted, and production API plus worker readiness are verified, the production dashboard must not be considered end-to-end live.

### Deployment-volume protection

Both Vercel projects (bharat-sim-81g2 frontend and bharat-sim backend) have affected-project deployments enabled. With their monorepo root directories configured, Vercel skips a project deployment when a commit does not affect that project. This prevents CI-only, Android-fixture and documentation changes from consuming deployment quota.

The team currently exceeded Vercel's 100-deployments-per-day allowance. New preview/production deployments are blocked until the quota window resets (or the plan limit is raised). The CORS environment changes are saved but are not active in existing deployments until redeployed.

