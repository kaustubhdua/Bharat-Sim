-- Local-only compatibility bootstrap for the reviewed BharatSim migrations.
-- This is NOT a production Supabase replacement. The service_role account is
-- the local container's bootstrap superuser; never reuse these credentials remotely.
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY
);
GRANT USAGE ON SCHEMA auth TO service_role;
GRANT SELECT ON auth.users TO service_role;
