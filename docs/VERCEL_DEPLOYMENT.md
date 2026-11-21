# BharatSim — current Vercel deployment and environment audit

Audit date: 22 November 2026
Project: bharat-sim-81g2 (unified frontend + FastAPI runtime)
Stable alias: https://bharat-sim-81g2.vercel.app

## Deployment status

- Latest inspected Production deployment is READY on commit 76f5b7e67d7dd400be9a0e3e7900907e77b0611f.
- Current GitHub main is ccb85d56a88299bd9cbc33da6c153a47645ccc83, two commits ahead of that deployment.
- Refresh deployment after final PR merges. Verify exact deployed SHA and run live/readiness/authenticated browser smoke; READY alone is not acceptance.

## Environment metadata

Sensitive values were not decrypted.

### Present in visible Production inventory
- BHARATSIM_ENV=production
- BHARATSIM_AUTH_REQUIRED=true
- BHARATSIM_STORAGE_BUCKET=bharatsim-private
- BHARATSIM_DATABASE_URL (sensitive; value/target unverified)
- SUPABASE_URL (sensitive; value/target unverified)
- VITE_SUPABASE_URL=https://gpkyzastnibffyuxhtix.supabase.co
- VITE_SUPABASE_PUBLISHABLE_KEY
- sarvam_api (sensitive; code explicitly supports this lowercase compatibility alias as well as SARVAM_API_KEY)
- BHARATSIM_MAX_UPLOAD_MB=50

### Missing from complete visible Production inventory
- SUPABASE_SECRET_KEY
- SUPABASE_SERVICE_ROLE_KEY

The backend enables private Storage only when SUPABASE_URL, one server-only secret/service-role key and the bucket name are present. Do not substitute the browser publishable key.

## Supabase project reconciliation

The browser URL references project gpkyzastnibffyuxhtix, absent from the connected Supabase project list. The only active/healthy project in that list is common 1 (hkyieaovolkethovyenb), shared with GenomeGuard. Its private bharatsim-private bucket exists, but its BharatSim migration history is only 4/9, live runs/workers schemas lack newer columns, and there are zero run rows and zero APK objects.

Do not change VITE_SUPABASE_URL, server-side SUPABASE_URL, or apply migrations until the owner confirms the authoritative project and backup/restore plan. Never paste service credentials into GitHub, frontend variables or chat.

## Upload limit

The API code supports APKs up to 500 MB using 45 MB parts, but Production currently sets BHARATSIM_MAX_UPLOAD_MB=50. Raise it only after server-side Storage credentials, correct project identity and multipart upload/download/delete tests pass. The bucket's 150 MiB limit applies per object; 45 MB parts stay below that cap.

## Worker safety

The following Production flags are present and false:
- BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED
- BHARATSIM_WORKER_ISOLATION_ATTESTED
- BHARATSIM_WORKER_EGRESS_RESTRICTED

Personal laptop workers are owner-scoped convenience workers, not per-job microVM isolation. Keep public arbitrary APK execution disabled until a dedicated worker host and default-deny egress are independently accepted.