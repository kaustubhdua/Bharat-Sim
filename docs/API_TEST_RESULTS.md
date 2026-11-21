# BharatSim — API Test Results

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21

## Existing verification

The CI unified ASGI/SPA smoke checks `/`, `/runs` and `/analyses` deep links, `/health/live` and `/api/v1/personas`. Backend Pytest covers the service's implemented routes and contracts. PostgreSQL integration checks clean migrations, run persistence after API restart, quota and signed-upload-related flows.

These checks are not an exhaustive generated OpenAPI/Schemathesis run. Full route-by-route auth/error/side-effect coverage is not completed.

## Read-only production results

| Endpoint | Result | Meaning |
|---|---|---|
| `/api/v1/capabilities` | HTTP 200 | Capability endpoint responds; exact deployed flags need refresh after candidate deploy |
| `/health/ready` | HTTP 503 | Database/private Storage/worker dependencies not ready |
| `/api/v1/personas` | HTTP 200 previously observed | Catalogue endpoint is accessible; this is not test execution evidence |

## Outstanding API tests

- Missing/invalid field and identifier tests for every request schema.
- Unauthorized, expired-token and two-user cross-tenant denial for every resource.
- Database failure, provider timeout, retry, duplicate submission and idempotency.
- Request size, upload content validation, abuse/rate limits, SSRF and unsafe input.
- Response schema/error consistency and database side-effect assertions.

## Reproduction

```bash
cd backend && pip install -r requirements-dev.txt && pytest -q
```

No production write calls or destructive API tests were performed in this audit.
