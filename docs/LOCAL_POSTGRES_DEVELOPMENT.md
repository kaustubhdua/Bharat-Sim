# Self-contained local PostgreSQL mode

This repository can run the BharatSim API and dashboard with a local PostgreSQL database without a managed Supabase database URL, server key, or Vercel deployment. This is a development/integration environment, **not a production substitute**.

## Start

Requirements: Docker Engine and the Docker Compose plugin.

Set a unique local-only password before starting. The Compose file intentionally refuses to start if it is missing; it has no known/default database password.

```bash
export BHARATSIM_LOCAL_POSTGRES_PASSWORD="$(openssl rand -hex 32)"

docker compose up --build -d
docker compose ps
docker compose logs --tail=100 postgres api web
```

Open the dashboard at http://localhost:8080. The web port is bound to loopback only. PostgreSQL has no published host port and is reachable only on the private Compose network.

The PostgreSQL container bootstraps a minimal local `auth.users` compatibility table, then applies the BharatSim core, foreign-key-index and signed-upload-size schema. The API connects to that database using the existing PostgreSQL adapter. APK files use the existing local filesystem path because the Supabase Storage service is not part of this local stack.

## Verify persistence

```bash
docker compose exec postgres psql -U service_role -d bharatsim -c \
  "select table_name from information_schema.tables where table_schema='bharatsim' order by table_name;"
curl --fail http://localhost:8080/health/ready
```

For an API-level persistence check, submit a valid fixture APK through the dashboard or the documented local API flow, restart only the API, and verify that the run remains visible. The CI PostgreSQL integration workflow exercises real PostgreSQL-backed API restart persistence.

## Reset local data

This deletes the local PostgreSQL database and uploaded APK files:

```bash
docker compose down -v
```

Do not run this if you need to preserve local test data.

## Important security and fidelity boundaries

- The local database bootstrap is intentionally minimal. It supplies only the `auth.users` foreign-key target and local roles needed by the BharatSim migrations; it does not run Supabase Auth, PostgREST, Realtime, or Storage.
- The local Compose API defaults to development mode. Do not expose it to an untrusted network or use real customer APKs/data.
- `BHARATSIM_LOCAL_POSTGRES_PASSWORD` is mandatory. The local `service_role` is the container's database bootstrap superuser so it can run the app against RLS-enabled tables without production role emulation. Use a unique local secret; never reuse it remotely or commit it.
- Supabase Auth/JWT verification, private object storage, signed TUS uploads and production ownership boundaries still require the managed or properly self-hosted Supabase services and server-only credentials.
- This mode does not execute APKs. The ADB worker remains an explicitly controlled test runner; public execution and Firecracker isolation flags must remain disabled until the isolated-host acceptance gates pass.
- For production Supabase, follow the official [Supabase self-hosting guide](https://supabase.com/docs/guides/self-hosting/docker). Self-hosting transfers responsibility for host security, patching, backups, disaster recovery, monitoring and availability to the operator.
