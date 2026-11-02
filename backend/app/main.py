from __future__ import annotations

import asyncio
import hashlib
import hmac
import http.client
import json
import os
import re
import sqlite3
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, quote, urlsplit

import jwt
from .sarvam import SarvamProviderError, SarvamRateLimited, translate_report_text
from .evidence_fusion import fuse_worker_report
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent


def default_data_dir() -> Path:
    # Vercel's deployment filesystem is read-only; /tmp is the writable scratch area.
    if os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/bharatsim")
    return APP_DIR.parent / "data"


DATA_DIR = Path(os.getenv("BHARATSIM_DATA_DIR", str(default_data_dir())))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "bharatsim.sqlite3"
DATABASE_URL = os.getenv("BHARATSIM_DATABASE_URL", "").strip()
APP_ENV = os.getenv("BHARATSIM_ENV", "development").strip().lower()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
# Prefer the modern opaque secret key; retain the legacy service_role JWT as a
# compatibility fallback while Supabase phases legacy keys out.
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
STORAGE_API_KEY = SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY
STORAGE_BUCKET = os.getenv("BHARATSIM_STORAGE_BUCKET", "bharatsim-private").strip()
STORAGE_ENABLED = bool(SUPABASE_URL and STORAGE_API_KEY and STORAGE_BUCKET)


def is_serverless_runtime() -> bool:
    """Return true on platforms where local disk is ephemeral between invocations."""
    return os.getenv("VERCEL") == "1" or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def requires_persistent_database() -> bool:
    """Production and serverless deployments must never use temporary SQLite state."""
    return APP_ENV in {"production", "prod"} or is_serverless_runtime()


def should_initialize_local_database() -> bool:
    """Only local development may create and use the SQLite fallback."""
    return not requires_persistent_database()


AUTH_REQUIRED = os.getenv("BHARATSIM_AUTH_REQUIRED", "false").strip().lower() == "true"
_jwks_client: PyJWKClient | None = None


def verify_supabase_access_token(token: str) -> str:
    """Verify a Supabase user access token against the project's asymmetric JWKS."""
    global _jwks_client
    if not SUPABASE_URL.startswith("https://"):
        raise ValueError("SUPABASE_URL must be an HTTPS URL")
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
            cache_jwk_set=True, lifespan=600, timeout=5,
        )
    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token, signing_key.key, algorithms=["ES256", "RS256"],
        audience="authenticated", issuer=f"{SUPABASE_URL}/auth/v1",
        options={"require": ["exp", "iat", "sub", "iss", "aud"]}, leeway=5,
    )
    if claims.get("role") != "authenticated" or claims.get("is_anonymous") is True:
        raise InvalidTokenError("A non-anonymous authenticated user token is required")
    return str(uuid.UUID(str(claims["sub"])))


def validate_auth_configuration(environment: dict[str, str] | None = None) -> None:
    values = os.environ if environment is None else environment
    if values.get("BHARATSIM_AUTH_REQUIRED", "false").strip().lower() == "true":
        if not values.get("SUPABASE_URL", "").strip().startswith("https://"):
            raise RuntimeError("BHARATSIM_AUTH_REQUIRED=true requires an HTTPS SUPABASE_URL")



def validate_database_configuration(database_url: str, app_env: str) -> None:
    """Fail closed on missing production persistence or plaintext remote PostgreSQL."""
    production = app_env in {"production", "prod"}
    if production and not database_url:
        raise RuntimeError(
            "BHARATSIM_ENV=production requires BHARATSIM_DATABASE_URL; refusing to start with local SQLite"
        )
    if not database_url:
        return

    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise RuntimeError("BHARATSIM_DATABASE_URL must be a valid PostgreSQL URL")
    query = parse_qs(parsed.query)
    sslmode = query.get("sslmode", ["prefer"])[-1].lower()
    host = parsed.hostname.lower().strip("[]")
    local_hosts = {"localhost", "127.0.0.1", "::1", "postgres"}
    secure_modes = {"require", "verify-ca", "verify-full"}
    if sslmode not in secure_modes and (production or host not in local_hosts):
        raise RuntimeError(
            "Remote/production PostgreSQL connections must set sslmode=require or stronger; "
            "use sslmode=disable only for local development/test databases"
        )


# Configuration is validated by readiness checks, not at module import. Serverless
# platforms must be able to start the ASGI app so liveness and actionable 503
# readiness responses remain observable when production secrets are missing.

def validate_runtime_security_config(environment: dict[str, str] | None = None) -> None:
    """Refuse production startup without verified user auth and private server credentials.

    Supabase JWT verification and owner-scoped queries are the user-data boundary.
    The optional shared API key is only for private single-tenant gateways.
    """
    values = os.environ if environment is None else environment
    mode = values.get("BHARATSIM_ENV", "development").strip().lower()
    if mode not in {"production", "prod"}:
        return
    # Verified Supabase user JWTs are the public-user authentication boundary.
    # The optional shared API key is intended for private single-tenant deployments
    # and must never be exposed to browser code.
    if values.get("BHARATSIM_AUTH_REQUIRED", "false").strip().lower() != "true":
        raise RuntimeError("Production startup blocked: enable BHARATSIM_AUTH_REQUIRED=true")
    if values.get("BHARATSIM_REQUIRE_API_KEY", "false").strip().lower() == "true" and len(values.get("BHARATSIM_API_KEY", "")) < 32:
        raise RuntimeError("Production startup blocked: BHARATSIM_API_KEY must contain at least 32 characters when the shared API-key gate is enabled")
    if not values.get("SUPABASE_URL", "").strip().startswith("https://"):
        raise RuntimeError("Production startup blocked: configure SUPABASE_URL for Supabase Auth and Storage")
    storage_key = values.get("SUPABASE_SECRET_KEY", "").strip() or values.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if len(storage_key) < 32:
        raise RuntimeError("Production startup blocked: configure a server-only SUPABASE_SECRET_KEY (preferred) or legacy SUPABASE_SERVICE_ROLE_KEY for private artifact storage")
    if not values.get("BHARATSIM_STORAGE_BUCKET", "bharatsim-private").strip():
        raise RuntimeError("Production startup blocked: configure BHARATSIM_STORAGE_BUCKET")


MAX_UPLOAD_BYTES = max(1, min(int(os.getenv("BHARATSIM_MAX_UPLOAD_MB", "150")), 150)) * 1024 * 1024
MAX_APK_ENTRIES = 10000
MAX_APK_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_APK_COMPRESSION_RATIO = 1000


def _storage_connection_and_path(object_path: str):
    if not STORAGE_ENABLED or not SUPABASE_URL.startswith("https://"):
        raise RuntimeError("Private Supabase Storage is not configured")
    parsed = urlsplit(SUPABASE_URL)
    encoded_bucket = quote(STORAGE_BUCKET, safe="")
    encoded_path = "/".join(quote(part, safe="") for part in object_path.split("/"))
    endpoint = f"/storage/v1/object/{encoded_bucket}/{encoded_path}"
    return http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=180), endpoint


def _storage_headers(content_type: str = "application/octet-stream") -> dict[str, str]:
    headers = {
        "apikey": STORAGE_API_KEY,
        "Content-Type": content_type,
    }
    # Modern sb_secret_* keys are opaque API keys, not JWTs. Supabase expects
    # them in the apikey header only; legacy service_role keys remain JWT bearers.
    if not SUPABASE_SECRET_KEY:
        headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
    return headers


def upload_private_object(source: Path, object_path: str) -> None:
    """Stream an APK into the private bucket without loading it into memory."""
    connection, endpoint = _storage_connection_and_path(object_path)
    try:
        connection.putrequest("POST", endpoint)
        headers = _storage_headers("application/vnd.android.package-archive")
        headers["Content-Length"] = str(source.stat().st_size)
        headers["x-upsert"] = "false"
        for name, value in headers.items():
            connection.putheader(name, value)
        connection.endheaders()
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                connection.send(chunk)
        response = connection.getresponse()
        body = response.read(2048)
        if response.status not in (200, 201):
            raise RuntimeError(f"Supabase Storage upload failed ({response.status}): {body.decode('utf-8', 'replace')}")
    finally:
        connection.close()


def create_private_upload_url(object_path: str) -> str:
    """Create a short-lived signed upload URL for a server-generated private object path."""
    connection, endpoint = _storage_connection_and_path(object_path)
    signed_endpoint = endpoint.replace("/object/", "/object/upload/sign/", 1)
    payload = b"{}"
    headers = _storage_headers("application/json")
    headers["Content-Length"] = str(len(payload))
    try:
        connection.request("POST", signed_endpoint, body=payload, headers=headers)
        response = connection.getresponse()
        body = response.read(8192)
        if response.status != 200:
            raise RuntimeError(f"Supabase signed upload URL failed ({response.status})")
        result = json.loads(body.decode("utf-8"))
        relative_url = result.get("url") if isinstance(result, dict) else None
        if not isinstance(relative_url, str) or not relative_url.startswith("/object/upload/sign/"):
            raise RuntimeError("Supabase returned an invalid signed upload URL")
        # The returned path is relative to /storage/v1. Never accept an upstream host.
        return f"{SUPABASE_URL}/storage/v1{relative_url}"
    finally:
        connection.close()


def build_tus_signed_upload_config(signed_url: str) -> dict[str, str]:
    """Convert a standard signed-upload URL into Supabase's signed TUS endpoint/token pair."""
    parsed = urlsplit(signed_url)
    token = parse_qs(parsed.query).get("token", [None])[0]
    if parsed.scheme != "https" or not parsed.hostname or not isinstance(token, str) or len(token) < 32:
        raise RuntimeError("Supabase returned an invalid signed upload capability")
    storage_host = parsed.hostname
    if storage_host.endswith(".supabase.co"):
        storage_host = storage_host.removesuffix(".supabase.co") + ".storage.supabase.co"
    return {
        "upload_token": token,
        "tus_endpoint": f"https://{storage_host}/storage/v1/upload/resumable",
    }

def private_object_size(object_path: str) -> int | None:
    """Read object size using a server-authenticated HEAD request."""
    connection, endpoint = _storage_connection_and_path(object_path)
    try:
        connection.request("HEAD", endpoint, headers=_storage_headers())
        response = connection.getresponse()
        response.read(1024)
        if response.status == 404:
            return None
        if response.status != 200:
            raise RuntimeError(f"Supabase object verification failed ({response.status})")
        value = response.getheader("Content-Length")
        return int(value) if value and value.isdigit() else None
    finally:
        connection.close()


def open_private_object(object_path: str):
    """Open a private object response for a worker-only streamed download."""
    connection, endpoint = _storage_connection_and_path(object_path)
    try:
        connection.request("GET", endpoint, headers=_storage_headers())
        response = connection.getresponse()
        if response.status != 200:
            body = response.read(2048)
            raise RuntimeError(f"Supabase Storage download failed ({response.status}): {body.decode('utf-8', 'replace')}")
        return connection, response
    except Exception:
        connection.close()
        raise


def delete_private_object(object_path: str) -> None:
    """Delete an object by path using the private server credential."""
    if not STORAGE_ENABLED:
        raise RuntimeError("Private Supabase Storage is not configured")
    parsed = urlsplit(SUPABASE_URL)
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=60)
    endpoint = f"/storage/v1/object/{quote(STORAGE_BUCKET, safe='')}"
    payload = json.dumps({"prefixes": [object_path]}).encode("utf-8")
    headers = _storage_headers("application/json")
    headers["Content-Length"] = str(len(payload))
    try:
        connection.request("DELETE", endpoint, body=payload, headers=headers)
        response = connection.getresponse()
        body = response.read(2048)
        if response.status not in (200, 204, 404):
            raise RuntimeError(f"Supabase Storage delete failed ({response.status}): {body.decode('utf-8', 'replace')}")
    finally:
        connection.close()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="BharatSim API",
    version="0.1.0",
    description="Evidence-first Android resilience testing. APK execution requires a separately provisioned worker.",
)
allowed_origins = [x.strip() for x in os.getenv("BHARATSIM_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-BharatSim-API-Key"],
)

@app.middleware("http")
async def enforce_api_authentication(request: Request, call_next):
    """Enforce private API key and optional Supabase identity on customer-data routes."""
    if request.url.path.startswith("/api/v1/") and os.getenv("BHARATSIM_REQUIRE_API_KEY", "false").lower() == "true":
        expected = os.getenv("BHARATSIM_API_KEY", "")
        if len(expected) < 32:
            return JSONResponse(status_code=503, content={"detail": "Private API key is not configured safely"})
        supplied = request.headers.get("X-BharatSim-API-Key", "")
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key"})
    database_protected = (
        request.url.path == "/api/v1/runs"
        or request.url.path.startswith("/api/v1/runs/")
        or request.url.path in {"/api/v1/analyses", "/api/v1/workers"}
        or request.url.path.startswith("/api/v1/uploads/")
    )
    # Pasted-log analysis is stateless when no run_id is supplied. It still
    # requires a verified user identity in production, but not PostgreSQL.
    auth_protected = database_protected or request.url.path in {
        "/api/v1/analyze/logs", "/api/v1/translate/report"
    }
    if APP_ENV in {"production", "prod"} and auth_protected:
        if not AUTH_REQUIRED or not SUPABASE_URL.startswith("https://"):
            return JSONResponse(status_code=503, content={"detail": "Production authentication is not configured"})
    if APP_ENV in {"production", "prod"} and database_protected:
        if not DATABASE_URL:
            return JSONResponse(status_code=503, content={"detail": "Production persistence is not configured"})
        if (request.url.path.startswith("/api/v1/uploads/") or
                (request.method == "POST" and request.url.path == "/api/v1/runs")) and not STORAGE_ENABLED:
            return JSONResponse(status_code=503, content={"detail": "Private APK storage is not configured"})
    if AUTH_REQUIRED and auth_protected:
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip() or len(token) > 16384:
            return JSONResponse(status_code=401, content={"detail": "A valid Supabase access token is required"}, headers={"WWW-Authenticate": "Bearer"})
        try:
            request.state.owner_id = await asyncio.to_thread(verify_supabase_access_token, token.strip())
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired Supabase access token"}, headers={"WWW-Authenticate": "Bearer"})
    return await call_next(request)


def validate_apk_archive(path: Path) -> None:
    """Bound central-directory complexity before any archive content is decompressed."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_APK_ENTRIES:
                raise HTTPException(status_code=415, detail="APK archive has an invalid or excessive entry count")
            if "AndroidManifest.xml" not in {item.filename for item in infos}:
                raise HTTPException(status_code=415, detail="ZIP archive is missing AndroidManifest.xml and is not a valid APK")
            uncompressed = 0
            for item in infos:
                if item.flag_bits & 0x1:
                    raise HTTPException(status_code=415, detail="Encrypted APK archive entries are not accepted")
                uncompressed += item.file_size
                if uncompressed > MAX_APK_UNCOMPRESSED_BYTES:
                    raise HTTPException(status_code=413, detail="APK expands beyond the allowed uncompressed size")
                if item.file_size > 0:
                    if item.compress_size == 0 or item.file_size / item.compress_size > MAX_APK_COMPRESSION_RATIO:
                        raise HTTPException(status_code=415, detail="APK contains a suspicious compression ratio")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=415, detail="Uploaded APK is not a valid ZIP archive")

PERSONAS: dict[str, dict[str, Any]] = {
    "budget-android": {
        "id": "budget-android", "name": "Budget Android", "device": "Android 10 · 2 GB RAM",
        "ram_mb": 2048, "storage_free_mb": 600, "network": "unstable-4g",
        "latency_ms": 180, "down_kbps": 1200, "up_kbps": 350, "packet_loss_pct": 2,
        "battery_saver": True, "risk": "high",
        "description": "Constrained memory and storage with variable mobile connectivity.",
    },
    "edge-village": {
        "id": "edge-village", "name": "Edge / weak signal", "device": "Android 11 · 3 GB RAM",
        "ram_mb": 3072, "storage_free_mb": 900, "network": "high-latency",
        "latency_ms": 450, "down_kbps": 256, "up_kbps": 96, "packet_loss_pct": 8,
        "battery_saver": True, "risk": "critical",
        "description": "Slow throughput, high latency and intermittent packet loss.",
    },
    "storage-pressure": {
        "id": "storage-pressure", "name": "Low storage", "device": "Android 10 · 2 GB RAM",
        "ram_mb": 2048, "storage_free_mb": 180, "network": "moderate-4g",
        "latency_ms": 90, "down_kbps": 2500, "up_kbps": 700, "packet_loss_pct": 0,
        "battery_saver": False, "risk": "high",
        "description": "Small free-storage budget to expose cache and download assumptions.",
    },
    "baseline": {
        "id": "baseline", "name": "Baseline", "device": "Android 14 · 6 GB RAM",
        "ram_mb": 6144, "storage_free_mb": 8000, "network": "good-4g",
        "latency_ms": 35, "down_kbps": 12000, "up_kbps": 3000, "packet_loss_pct": 0,
        "battery_saver": False, "risk": "low",
        "description": "Control profile for comparison; still runs only when a worker is available.",
    },
}

APP_CATEGORIES = {
    "general": ("network", "retry", "payment", "login"),
    "ecommerce": ("checkout", "cart", "order", "payment", "inventory", "product", "search"),
    "fintech": ("payment", "transfer", "upi", "balance", "authentication", "login", "statement"),
    "social": ("feed", "message", "chat", "upload", "image", "notification", "video"),
    "education": ("course", "lesson", "video", "quiz", "download", "sync", "assignment"),
    "delivery": ("location", "map", "tracking", "order", "payment", "address", "route"),
    "media": ("playback", "stream", "video", "audio", "buffer", "download", "offline"),
}


class PlanRequest(BaseModel):
    persona_ids: list[str] = Field(default_factory=lambda: ["budget-android", "edge-village"], max_length=8)
    app_category: Literal["general", "ecommerce", "fintech", "social", "education", "delivery", "media"] = "general"
    critical_flows: list[str] = Field(default_factory=lambda: ["cold start", "login", "primary action", "network retry"], max_length=10)
    max_scenarios: int = Field(default=6, ge=1, le=20)

class LogAnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_000_000)
    persona_id: str = "budget-android"
    run_id: str | None = None

class SarvamTranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target_language_code: Literal["hi-IN", "ta-IN", "mr-IN"]

class SignedUploadRequest(BaseModel):
    persona_id: str = "budget-android"
    filename: str = Field(min_length=5, max_length=255)
    size_bytes: int = Field(gt=0, le=157286400)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

class WorkerClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")

class WorkerHeartbeatRequest(BaseModel):
    lease_token: str = Field(min_length=32, max_length=200)

class WorkerResultRequest(BaseModel):
    lease_token: str = Field(min_length=32, max_length=200)
    status: Literal["completed", "failed"]
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=2000)

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def postgres_placeholders(query: str) -> str:
    """Translate SQLite '?' placeholders without rewriting quoted SQL literals."""
    output: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(query):
        char = query[index]
        if quote:
            output.append(char)
            if char == quote:
                if index + 1 < len(query) and query[index + 1] == quote:
                    output.append(query[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in ("'", '"'):
            quote = char
            output.append(char)
        elif char == "?":
            output.append("%s")
        else:
            output.append(char)
        index += 1
    return "".join(output)


class PostgresCompatConnection:
    """Small adapter for existing parameterized SQL while moving to PostgreSQL.

    The application still must enforce user ownership before customer data is enabled.
    """
    def __init__(self, connection):
        self._connection = connection

    def execute(self, query: str, parameters=()):
        return self._connection.execute(postgres_placeholders(query), parameters)

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()


@contextmanager
def db():
    if requires_persistent_database() and not DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="Persistent PostgreSQL is not configured for this serverless deployment.",
        )
    if DATABASE_URL:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("BHARATSIM_DATABASE_URL requires the psycopg[binary] dependency") from exc
        # Transaction poolers do not preserve session-level settings between
        # clients. Set the private schema path locally for this transaction only.
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None)
        conn = PostgresCompatConnection(raw)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        if DATABASE_URL:
            conn.execute("SET LOCAL search_path TO bharatsim, public")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _event_json(payload: dict[str, Any] | None) -> str:
    """Serialize bounded, caller-curated metadata; never pass credentials or raw logs."""
    encoded = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 8_000:
        return json.dumps({"truncated": True, "original_bytes": len(encoded.encode("utf-8"))})
    return encoded


def record_run_event(conn, run_id: str, event_type: str, actor_type: str = "system",
                     actor_id: str | None = None, payload: dict[str, Any] | None = None) -> None:
    if actor_type not in {"user", "worker", "system"}:
        raise ValueError("Invalid run-event actor type")
    conn.execute(
        "INSERT INTO run_events(run_id,event_type,actor_type,actor_id,payload_json) VALUES(?,?,?,?,?)",
        (run_id, event_type[:80], actor_type, actor_id, _event_json(payload)),
    )


def record_audit_event(conn, owner_id: str | None, actor_type: str, actor_id: str | None,
                       action: str, resource_type: str, resource_id: str | None,
                       metadata: dict[str, Any] | None = None) -> None:
    if actor_type not in {"user", "worker", "system", "admin"}:
        raise ValueError("Invalid audit-event actor type")
    conn.execute(
        "INSERT INTO audit_events(owner_id,actor_type,actor_id,action,resource_type,resource_id,metadata_json) VALUES(?,?,?,?,?,?,?)",
        (owner_id, actor_type, actor_id, action[:120], resource_type[:80], resource_id, _event_json(metadata)),
    )


def init_db() -> None:
    if DATABASE_URL:
        # Schema is managed only by versioned Supabase migrations; never create or
        # mutate production tables implicitly during application startup.
        with db() as conn:
            row = conn.execute(
                "SELECT to_regclass('bharatsim.runs') AS runs, "
                "to_regclass('bharatsim.run_events') AS run_events, "
                "to_regclass('bharatsim.audit_events') AS audit_events"
            ).fetchone()
            if not row or not row["runs"] or not row["run_events"] or not row["audit_events"]:
                raise RuntimeError(
                    "Supabase is configured but BharatSim core/run-event/audit tables are missing; apply the reviewed Supabase migrations first"
                )
        return

    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
            apk_name TEXT, apk_sha256 TEXT, apk_path TEXT, persona_id TEXT NOT NULL,
            result_json TEXT, error TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, run_id TEXT,
            persona_id TEXT NOT NULL, result_json TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY, last_seen TEXT NOT NULL, status TEXT NOT NULL,
            current_run_id TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS quotas (
            owner_id TEXT PRIMARY KEY,
            daily_run_limit INTEGER NOT NULL DEFAULT 10 CHECK (daily_run_limit > 0),
            active_run_limit INTEGER NOT NULL DEFAULT 2 CHECK (active_run_limit > 0),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS run_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actor_type TEXT NOT NULL CHECK (actor_type IN ('user','worker','system')),
            actor_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS run_events_run_created_idx ON run_events(run_id,created_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT,
            actor_type TEXT NOT NULL CHECK (actor_type IN ('user','worker','system','admin')),
            actor_id TEXT,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS audit_events_owner_created_idx ON audit_events(owner_id,created_at DESC)")
        # Backward-compatible schema migration for local MVP databases.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        migrations = {
            "lease_token": "TEXT",
            "lease_until": "TEXT",
            "worker_id": "TEXT",
            "updated_at": "TEXT",
            "attempts": "INTEGER NOT NULL DEFAULT 0",
            "owner_id": "TEXT",
            "apk_storage_path": "TEXT",
            "apk_size_bytes": "INTEGER",
        }
        analysis_columns = {row["name"] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()}
        if "owner_id" not in analysis_columns:
            conn.execute("ALTER TABLE analyses ADD COLUMN owner_id TEXT")
        for column, definition in migrations.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")

# SQLite is a local-development convenience only. Vercel/AWS functions must
# never create or use ephemeral /tmp database files, even in preview mode.
if should_initialize_local_database():
    init_db()


def enforce_run_quota(conn, owner_id: str | None, now: datetime | None = None) -> None:
    """Serialize per-user run creation and enforce daily/active limits."""
    if not owner_id:
        return

    if DATABASE_URL:
        conn.execute(
            "INSERT INTO quotas(owner_id) VALUES(?) ON CONFLICT(owner_id) DO NOTHING",
            (owner_id,),
        )
        quota = conn.execute(
            "SELECT daily_run_limit,active_run_limit FROM quotas WHERE owner_id=? FOR UPDATE",
            (owner_id,),
        ).fetchone()
    else:
        conn.execute("INSERT OR IGNORE INTO quotas(owner_id) VALUES(?)", (owner_id,))
        quota = conn.execute(
            "SELECT daily_run_limit,active_run_limit FROM quotas WHERE owner_id=?",
            (owner_id,),
        ).fetchone()

    if not quota:
        raise HTTPException(status_code=503, detail="Run quota configuration is unavailable.")

    current = now or datetime.now(timezone.utc)
    current = current.astimezone(timezone.utc)
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    daily_count = conn.execute(
        "SELECT COUNT(*) AS total FROM runs WHERE owner_id=? AND created_at>=?",
        (owner_id, day_start),
    ).fetchone()["total"]
    active_count = conn.execute(
        "SELECT COUNT(*) AS total FROM runs WHERE owner_id=? AND status IN ('awaiting_worker','queued','leased','running')",
        (owner_id,),
    ).fetchone()["total"]

    if active_count >= quota["active_run_limit"]:
        raise HTTPException(
            status_code=429,
            detail=f"Active test-run limit reached ({quota['active_run_limit']}). Wait for a run to finish or delete a queued run.",
            headers={"Retry-After": "60"},
        )
    if daily_count >= quota["daily_run_limit"]:
        next_day = current.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        retry_after = max(1, int((next_day - current).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail=f"Daily test-run limit reached ({quota['daily_run_limit']}). Try again after 00:00 UTC.",
            headers={"Retry-After": str(retry_after)},
        )


def cleanup_expired_uploads() -> None:
    """Expire abandoned APK uploads after 24 hours and remove old terminal-run APKs."""
    now = datetime.now(timezone.utc)
    cutoff = datetime.fromtimestamp(now.timestamp() - 24 * 60 * 60, timezone.utc).isoformat()
    now_text = now.isoformat()
    with db() as conn:
        rows = conn.execute(
            "SELECT id,apk_path,apk_storage_path,status,lease_until FROM runs WHERE (apk_path IS NOT NULL OR apk_storage_path IS NOT NULL) AND created_at < ?",
            (cutoff,),
        ).fetchall()
        for row in rows:
            if row["status"] == "leased" and row["lease_until"] and row["lease_until"] >= now_text:
                continue
            if row["apk_path"]:
                path = Path(row["apk_path"]).resolve()
                if path.parent != UPLOAD_DIR.resolve():
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    continue
            if row["apk_storage_path"]:
                try:
                    delete_private_object(row["apk_storage_path"])
                except Exception:
                    continue
            if row["status"] in ("awaiting_worker", "queued", "leased"):
                conn.execute(
                    "UPDATE runs SET status='failed',error='APK upload expired before execution',apk_path=NULL,apk_storage_path=NULL,"
                    "lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                    (now_text, row["id"]),
                )
            else:
                conn.execute("UPDATE runs SET apk_path=NULL,apk_storage_path=NULL WHERE id=?", (row["id"],))


def should_run_startup_cleanup() -> bool:
    """Run filesystem/database cleanup only in local development processes.

    Vercel functions are short-lived and may be imported before production
    persistence is configured. Import-time cleanup can otherwise open the
    ephemeral SQLite fallback and crash the entire ASGI function. Production
    cleanup belongs in a separately scheduled job with explicit DB credentials.
    """
    return (
        APP_ENV not in {"production", "prod"}
        and os.getenv("VERCEL") != "1"
        and not os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    )


if should_run_startup_cleanup():
    cleanup_expired_uploads()


def failure_fingerprint(line: str) -> str:
    normalized = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", line)
    normalized = re.sub(r"\b\d+\b", "<N>", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:12]

def _redact_log_evidence(value: str) -> str:
    """Remove common credentials before log snippets are returned or persisted."""
    value = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\b\s*[:=]\s*)[^\s,;&]+", r"\1[REDACTED]", value)
    value = re.sub(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "[REDACTED_JWT]", value)
    return value[:600]


def analyze_log_text(text: str, persona_id: str = "budget-android") -> dict[str, Any]:
    """Build deterministic Failure DNA and evidence-linked hypotheses from supplied logcat.

    This is deliberately rule-based: it does not claim an LLM diagnosis, confirmed
    root cause, device-population exposure, or successful APK execution.
    """
    if persona_id not in PERSONAS:
        raise ValueError("Unknown persona_id")
    lines = text.splitlines()
    rules = [
        ("crash", re.compile(r"FATAL EXCEPTION|Fatal signal|Process .* has died|SIGSEGV", re.I), "Application crash signal"),
        ("anr", re.compile(r"ANR in |Application Not Responding|Input dispatching timed out", re.I), "Application-not-responding signal"),
        ("oom", re.compile(r"OutOfMemoryError|Failed to allocate .*bytes|low memory killer|lmkd.*kill", re.I), "Memory pressure signal"),
        ("network", re.compile(r"UnknownHostException|SocketTimeoutException|ConnectException|ECONNRESET|Network is unreachable", re.I), "Network failure signal"),
        ("strictmode", re.compile(r"StrictMode policy violation|disk read on main thread|disk write on main thread", re.I), "Potential main-thread blocking signal"),
        ("storage", re.compile(r"ENOSPC|No space left on device|SQLiteFullException", re.I), "Storage exhaustion signal"),
    ]
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for index, line in enumerate(lines, start=1):
        for kind, pattern, title in rules:
            if pattern.search(line):
                fingerprint = failure_fingerprint(f"{kind}:{line}")
                key = (kind, fingerprint)
                group = groups.setdefault(key, {
                    "id": fingerprint,
                    "kind": kind,
                    "title": title,
                    "severity": "critical" if kind in ("crash", "anr", "oom") else "high" if kind in ("storage", "network") else "medium",
                    "fingerprint": fingerprint,
                    "line_numbers": [],
                    "evidence": [],
                    "first_line": index,
                    "last_line": index,
                })
                group["line_numbers"].append(index)
                group["last_line"] = index
                if len(group["evidence"]) < 5:
                    group["evidence"].append({"line": index, "text": _redact_log_evidence(line)})
                break

    persona = PERSONAS[persona_id]
    risk_multiplier = {"critical": 1.25, "high": 1.10, "low": 0.80}.get(persona["risk"], 1.0)
    explanations = {
        "crash": ("The log contains a fatal process or exception marker. Inspect the adjacent stack trace to locate the originating frame.",
                  "Review the first app-owned frame in the full stack trace and add a regression test for this path.",
                  ["Inspect the complete exception and cause chain.", "Identify the first app-owned stack frame.", "Reproduce on the same Android/API level."]),
        "anr": ("The log contains an ANR or input-dispatch timeout marker. Main-thread traces and timing are needed to confirm the blocking operation.",
                "Capture a thread dump and move blocking I/O or long work off the main thread.",
                ["Inspect the ANR traces and main-thread stack.", "Correlate input-dispatch timestamps with slow operations.", "Repeat the interaction with a profiler attached."]),
        "oom": ("The log contains a memory allocation or low-memory marker. Compare heap/native memory, process importance and device RAM.",
                "Capture a memory profile; bound caches and release large references on lifecycle transitions.",
                ["Compare Java heap, native heap and process RSS.", "Inspect large allocations and cache retention.", "Repeat under a measured low-memory device or emulator condition."]),
        "network": ("The log contains a connection or timeout failure. Check retry behavior, cancellation, timeout budgets and offline UI state.",
                    "Use bounded retries with exponential backoff, explicit timeouts and a recoverable offline state.",
                    ["Inspect DNS/connect/read timeout boundaries.", "Verify retry backoff, cancellation and idempotency.", "Repeat with measured latency, bandwidth and disconnect conditions."]),
        "strictmode": ("The log contains a StrictMode or main-thread disk I/O marker. Profile the affected interaction before attributing user-visible jank.",
                       "Move disk operations off the main thread and measure frame latency around the affected flow.",
                       ["Inspect the StrictMode policy and stack.", "Move blocking I/O off the main thread.", "Measure frame time during the affected interaction."]),
        "storage": ("The log contains a storage exhaustion marker. Check free-space handling, cache eviction and write-failure recovery.",
                    "Handle ENOSPC explicitly and test cache cleanup and failed writes with low free space.",
                    ["Inspect the failing path and available disk space.", "Verify cache eviction and transactional write recovery.", "Repeat with a measured storage budget."]),
    }
    findings: list[dict[str, Any]] = []
    for group in sorted(groups.values(), key=lambda item: (item["first_line"], item["kind"], item["fingerprint"])):
        explanation, recommendation, validation = explanations[group["kind"]]
        base = {"critical": 100, "high": 72, "medium": 44}[group["severity"]]
        priority_score = min(100, round(base * risk_multiplier))
        first_index = group["first_line"] - 1
        context_start = max(0, first_index - 2)
        context_end = min(len(lines), first_index + 3)
        group["occurrence_count"] = len(group["line_numbers"])
        group["evidence_context"] = [
            {"line": i + 1, "text": _redact_log_evidence(lines[i]), "relation": "match" if i + 1 == group["first_line"] else "context"}
            for i in range(context_start, context_end)
        ]
        group["explanation"] = explanation
        group["recommendation"] = recommendation
        group["impact_priority"] = {
            "score": priority_score,
            "label": "relative diagnostic priority",
            "persona_risk": persona["risk"],
            "warning": "Not an estimate of affected users or population exposure.",
        }
        group["root_cause_hypothesis"] = {
            "statement": explanation,
            "confidence": "low",
            "validation_steps": validation,
            "status": "unconfirmed",
        }
        findings.append(group)

    critical = sum(1 for item in findings if item["severity"] == "critical")
    high = sum(1 for item in findings if item["severity"] == "high")
    medium = sum(1 for item in findings if item["severity"] == "medium")
    score = max(0, min(100, 100 - critical * 28 - high * 14 - medium * 6))
    total_occurrences = sum(item["occurrence_count"] for item in findings)
    impact_score = max((item["impact_priority"]["score"] for item in findings), default=0)
    dna = [{
        "fingerprint": item["fingerprint"],
        "kind": item["kind"],
        "severity": item["severity"],
        "occurrence_count": item["occurrence_count"],
        "line_numbers": item["line_numbers"],
        "first_line": item["first_line"],
        "last_line": item["last_line"],
    } for item in findings]
    return {
        "id": str(uuid.uuid4()), "created_at": utcnow(), "persona": persona,
        "source": "uploaded-log-text", "analysis_mode": "deterministic-rule-based",
        "evidence_lines": len(lines), "findings": findings,
        "failure_dna": {
            "groups": dna,
            "group_count": len(dna),
            "total_occurrences": total_occurrences,
            "method": "Normalized line fingerprints grouped by signal category; occurrences and source line numbers are retained.",
        },
        "root_cause_hypotheses": [item["root_cause_hypothesis"] | {"finding_id": item["id"], "kind": item["kind"]} for item in findings],
        "user_impact": {
            "priority_score": impact_score,
            "label": "Relative exposure heuristic",
            "persona_risk": persona["risk"],
            "drivers": [item["kind"] for item in findings if item["impact_priority"]["score"] == impact_score] if impact_score else [],
            "assumptions": [
                "Priority combines signal severity with the selected persona's authored risk tier.",
                "This is not an affected-user estimate; no install base, geography, or telemetry denominator is available.",
                "This score orders investigation work; it is not a population estimate.",
            ],
        },
        "summary": {
            "finding_count": len(findings), "critical": critical, "high": high, "medium": medium,
            "occurrence_count": total_occurrences, "clean": len(findings) == 0,
        },
        "bharat_score": {
            "value": score, "label": "Log resilience heuristic",
            "method": "100 − 28×critical − 14×high − 6×medium, clamped to 0–100",
            "warning": "Based only on detected markers in supplied logs; not a device-population estimate or proof of app quality.",
        },
        "limitations": [
            "Log markers are heuristic signals and may include false positives or miss failures.",
            "Failure DNA groups normalized log markers; it does not prove two incidents share the same root cause.",
            "Root-cause statements are low-confidence hypotheses until corroborated by full traces and reproduction.",
            "User impact is a relative persona/severity priority heuristic, not an affected-user or market estimate.",
            "Credentials detected in evidence snippets are redacted before the analysis is returned or stored.",
            "This analysis does not mean the APK was installed or executed.",
        ],
    }

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/")
def root():
    # Keep the legacy API root useful in local backend-only development, while
    # serving the dashboard at the single public origin in the unified build.
    index = _FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    return {"name": "BharatSim API", "version": "0.1.0", "docs": "/docs", "status": APP_ENV}

@app.get("/health/live")
def health_live():
    return {"status": "alive", "timestamp": utcnow()}

@app.get("/health/ready")
def health_ready():
    """Report API dependencies separately from worker execution availability.

    In production, a reachable database alone is not enough: verified user
    authentication and private artifact storage must also be configured.
    Never expose credential values or infer worker readiness from API health.
    """
    worker_token_configured = len(os.getenv("BHARATSIM_WORKER_TOKEN", "")) >= 32
    worker_configured = worker_token_configured and production_worker_execution_enabled()
    worker_online = False
    production = APP_ENV in {"production", "prod"}
    database_ok = False
    try:
        # Production must never report a temporary local SQLite file as its
        # persistence layer. Verify the configured Postgres schema as well as
        # basic connectivity before advertising readiness.
        if requires_persistent_database() and not DATABASE_URL:
            raise RuntimeError("Persistent PostgreSQL URL is not configured for this serverless deployment")
        validate_database_configuration(DATABASE_URL, APP_ENV)
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
            if DATABASE_URL:
                schema = conn.execute(
                    "SELECT to_regclass('bharatsim.runs') AS runs, "
                    "to_regclass('bharatsim.run_events') AS run_events, "
                    "to_regclass('bharatsim.audit_events') AS audit_events"
                ).fetchone()
                if not schema or not all(schema[key] for key in ("runs", "run_events", "audit_events")):
                    raise RuntimeError("BharatSim production schema is incomplete")
            database_ok = True
            if worker_configured:
                rows = conn.execute("SELECT last_seen,status FROM workers ORDER BY last_seen DESC LIMIT 50").fetchall()
                now = datetime.now(timezone.utc)
                for row in rows:
                    try:
                        seen = datetime.fromisoformat(row["last_seen"])
                        if seen.tzinfo is None:
                            seen = seen.replace(tzinfo=timezone.utc)
                        if (now - seen).total_seconds() <= 90 and row["status"] != "offline":
                            worker_online = True
                            break
                    except (TypeError, ValueError):
                        continue
    except Exception:
        database_ok = False
        worker_online = False

    auth_configured = AUTH_REQUIRED and SUPABASE_URL.startswith("https://")
    storage_configured = STORAGE_ENABLED and SUPABASE_URL.startswith("https://")
    auth_required = production or AUTH_REQUIRED
    storage_required = requires_persistent_database()
    auth_ok = auth_configured if auth_required else True
    storage_ok = storage_configured if storage_required else True
    api_ready = database_ok and auth_ok and storage_ok

    worker_state = (
        "online" if worker_online
        else "safety_gate_closed" if worker_token_configured and not worker_configured
        else "offline" if worker_configured
        else "not_configured"
    )
    payload = {
        # API readiness is independent from Android execution readiness.
        "status": "ready" if api_ready else "not_ready",
        "api_readiness": "ready" if api_ready else "not_ready",
        "execution_readiness": "ready" if api_ready and worker_online else "not_ready",
        "database": "available" if database_ok else "unavailable",
        "authentication": "configured" if auth_configured else "unavailable",
        "authentication_required": auth_required,
        "private_storage": "configured" if storage_configured else "unavailable",
        "private_storage_required": storage_required,
        "apk_execution_worker": worker_state,
        "worker_online": worker_online,
        "worker_execution_enabled": worker_configured,
        "execution_capability": "external-worker-required",
        "timestamp": utcnow(),
    }
    return JSONResponse(status_code=200 if api_ready else 503, content=payload)

@app.get("/api/v1/personas")
def list_personas():
    return {"items": list(PERSONAS.values())}

@app.post("/api/v1/plan")
def create_plan(request: PlanRequest):
    """Select risk-prioritized persona/flow scenarios and expose pairwise interactions."""
    unknown = sorted(set(request.persona_ids) - set(PERSONAS))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown persona IDs: {', '.join(unknown)}")
    flows = []
    seen_flows = set()
    for raw_flow in request.critical_flows:
        flow = re.sub(r"\s+", " ", raw_flow).strip()[:80]
        if flow and flow.casefold() not in seen_flows:
            flows.append(flow)
            seen_flows.add(flow.casefold())
    flows = flows or ["cold start", "login", "primary action", "network retry"]
    category_keywords = APP_CATEGORIES[request.app_category]
    scenarios = []
    interaction_candidates = 0
    for pid in request.persona_ids:
        persona = PERSONAS[pid]
        conditions: list[dict[str, Any]] = []
        if persona["latency_ms"] >= 150:
            conditions.append({"id": "high_latency", "label": "High network latency", "target": f'{persona["latency_ms"]} ms'})
        if persona["down_kbps"] <= 1200:
            conditions.append({"id": "limited_bandwidth", "label": "Limited download bandwidth", "target": f'{persona["down_kbps"]} kbps'})
        if persona["storage_free_mb"] < 300:
            conditions.append({"id": "low_storage", "label": "Low free storage", "target": f'{persona["storage_free_mb"]} MB'})
        if persona["battery_saver"]:
            conditions.append({"id": "battery_saver", "label": "Battery saver enabled", "target": "enabled"})
        if persona["ram_mb"] <= 3072:
            conditions.append({"id": "low_memory_profile", "label": "Low-memory device profile", "target": f'{persona["ram_mb"]} MB (profile target; not a verified RAM cap)'})

        interactions = []
        for index, left in enumerate(conditions):
            for right in conditions[index + 1:]:
                interaction_candidates += 1
                pair = {left["id"], right["id"]}
                bonus = 8
                if pair == {"high_latency", "limited_bandwidth"}:
                    bonus = 18
                    hypothesis = "High latency × limited bandwidth may amplify request timeouts and retry storms."
                elif pair == {"low_storage", "battery_saver"}:
                    bonus = 12
                    hypothesis = "Low storage × battery saver may expose deferred writes, background scheduling and cache cleanup issues."
                elif pair == {"low_storage", "limited_bandwidth"}:
                    bonus = 14
                    hypothesis = "Low storage × limited bandwidth may expose partial-download cleanup and resumability defects."
                elif pair == {"high_latency", "battery_saver"}:
                    bonus = 12
                    hypothesis = "High latency × battery saver may expose lifecycle cancellation and background retry defects."
                elif pair == {"low_memory_profile", "high_latency"}:
                    bonus = 14
                    hypothesis = "Low-memory profile × high latency may expose retained request state and process-recreation defects."
                else:
                    hypothesis = f'{left["label"]} × {right["label"]} may expose an interaction not visible in isolated tests.'
                interactions.append({
                    "conditions": [left["id"], right["id"]],
                    "labels": [left["label"], right["label"]],
                    "risk_bonus": bonus,
                    "hypothesis": hypothesis,
                    "validation": "Run the paired condition on a disposable target and compare with each single-condition baseline.",
                })

        for flow in flows:
            score = 25
            score += 25 if persona["risk"] == "critical" else 15 if persona["risk"] == "high" else 0
            category_sensitive = any(keyword in flow.casefold() for keyword in category_keywords)
            score += 15 if category_sensitive else 0
            score += 10 if persona["storage_free_mb"] < 300 else 0
            interaction_bonus = min(25, max((item["risk_bonus"] for item in interactions), default=0))
            score = min(100, score + interaction_bonus)
            scenarios.append({
                "id": f"{pid}:{re.sub(r'[^a-z0-9]+', '-', flow.lower()).strip('-')}",
                "persona_id": pid,
                "persona_name": persona["name"],
                "flow": flow,
                "app_category": request.app_category,
                "category_flow_sensitive": category_sensitive,
                "risk_score": min(100, score),
                "reason": f"Deterministic test-ordering heuristic using persona risk, {request.app_category}-specific critical-flow keywords and pairwise condition interactions; not predicted failure probability.",
                "requested_conditions": conditions,
                "interaction_hypotheses": interactions,
                "interaction_count": len(interactions),
                "interaction_risk_bonus": interaction_bonus,
            })
    scenarios.sort(key=lambda item: (-item["risk_score"], item["id"]))
    selected = scenarios[:request.max_scenarios]
    selected_interactions = sum(item["interaction_count"] for item in selected)
    return {
        "generated_at": utcnow(),
        "strategy": "deterministic-category-aware-risk-and-pairwise-interaction-v3",
        "app_category": request.app_category,
        "critical_flows": flows,
        "scenarios": selected,
        "total_candidates": len(scenarios),
        "interaction_hunter": {
            "candidate_pairwise_interactions": interaction_candidates,
            "selected_scenario_interactions": selected_interactions,
            "method": "Enumerates pairs of authored persona conditions and ranks scenarios by persona risk, category-specific critical-flow sensitivity, and the strongest pairwise risk bonus.",
            "warning": "These are test-selection hypotheses. They do not mean conditions were applied or that a failure was observed.",
        },
    }

@app.post("/api/v1/uploads/sign")
def sign_apk_upload(payload: SignedUploadRequest, request: Request):
    """Create a private, time-limited upload URL so APK bytes bypass Vercel's 4.5 MB function limit."""
    if not STORAGE_ENABLED:
        raise HTTPException(status_code=503, detail="Direct private APK uploads are not configured on this server.")
    if payload.persona_id not in PERSONAS:
        raise HTTPException(status_code=422, detail="Unknown persona_id")
    if payload.size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"APK exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB limit")
    cleanup_expired_uploads()
    safe_name = payload.filename.replace("\\", "/").rsplit("/", 1)[-1].strip()[:180]
    if not safe_name.lower().endswith(".apk"):
        raise HTTPException(status_code=415, detail="Upload must have an .apk filename")
    owner_id = getattr(request.state, "owner_id", None)
    with db() as conn:
        enforce_run_quota(conn, owner_id, datetime.now(timezone.utc))
    run_id = str(uuid.uuid4())
    object_path = f"runs/{run_id}/input.apk"
    try:
        signed_url = create_private_upload_url(object_path)
        upload_capability = build_tus_signed_upload_config(signed_url)
    except Exception:
        raise HTTPException(status_code=503, detail="Private APK upload could not be prepared. No run was queued.")
    created = utcnow()
    try:
        with db() as conn:
            enforce_run_quota(conn, owner_id, datetime.now(timezone.utc))
            conn.execute(
                "INSERT INTO runs(id,created_at,status,apk_name,apk_sha256,apk_path,persona_id,result_json,error,updated_at,owner_id,apk_storage_path,apk_size_bytes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, created, "awaiting_worker", safe_name, payload.sha256, None, payload.persona_id, None, None, created, owner_id, object_path, payload.size_bytes),
            )
            actor_type = "user" if owner_id else "system"
            record_run_event(conn, run_id, "run_created", actor_type, owner_id, {
                "persona_id": payload.persona_id, "apk_name": safe_name,
                "apk_size_bytes": payload.size_bytes, "upload_method": "tus",
            })
            record_audit_event(conn, owner_id, actor_type, owner_id, "run.created", "run", run_id, {
                "persona_id": payload.persona_id, "apk_size_bytes": payload.size_bytes, "upload_method": "tus",
            })
    except Exception:
        # The signed URL is short-lived and the object has not been uploaded yet.
        raise
    return {
        "run_id": run_id,
        "upload_token": upload_capability["upload_token"],
        "tus_endpoint": upload_capability["tus_endpoint"],
        "object_path": object_path,
        "expires_in_seconds": 7200,
        "message": "A resumable private upload is ready. Upload the APK in retryable chunks, then confirm the upload.",
    }


@app.post("/api/v1/runs/{run_id}/upload-complete")
def complete_apk_upload(run_id: str, request: Request):
    """Confirm a direct upload by checking the private Storage object's actual byte size."""
    with db() as conn:
        if AUTH_REQUIRED:
            row = conn.execute(
                "SELECT id,created_at,status,apk_storage_path,apk_size_bytes,apk_name,apk_sha256,persona_id,owner_id FROM runs WHERE id=? AND owner_id=?",
                (run_id, request.state.owner_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id,created_at,status,apk_storage_path,apk_size_bytes,apk_name,apk_sha256,persona_id,owner_id FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row["status"] != "awaiting_worker" or not row["apk_storage_path"] or not row["apk_size_bytes"]:
        raise HTTPException(status_code=409, detail="Run is not waiting for a direct APK upload")
    try:
        actual_size = private_object_size(row["apk_storage_path"])
    except Exception:
        raise HTTPException(status_code=503, detail="Could not verify the private APK upload. Please retry.")
    if actual_size is None:
        raise HTTPException(status_code=409, detail="APK upload was not found in private storage yet.")
    if actual_size != row["apk_size_bytes"]:
        try:
            delete_private_object(row["apk_storage_path"])
        except Exception:
            pass
        with db() as conn:
            conn.execute(
                "UPDATE runs SET status='failed',error=?,updated_at=? WHERE id=? AND status='awaiting_worker'",
                ("Uploaded APK size did not match the signed upload request.", utcnow(), run_id),
            )
            actor_type = "user" if row["owner_id"] else "system"
            record_run_event(conn, run_id, "apk_upload_rejected", actor_type, row["owner_id"], {
                "expected_size_bytes": row["apk_size_bytes"], "actual_size_bytes": actual_size,
                "reason": "size_mismatch",
            })
            record_audit_event(conn, row["owner_id"], actor_type, row["owner_id"], "run.upload_rejected", "run", run_id, {
                "expected_size_bytes": row["apk_size_bytes"], "actual_size_bytes": actual_size,
                "reason": "size_mismatch",
            })
        raise HTTPException(status_code=422, detail="Uploaded APK size did not match the signed upload request.")
    worker_configured = len(os.getenv("BHARATSIM_WORKER_TOKEN", "")) >= 32
    status = "queued" if worker_configured else "awaiting_worker"
    with db() as conn:
        if AUTH_REQUIRED:
            changed = conn.execute(
                "UPDATE runs SET status=?,updated_at=? WHERE id=? AND owner_id=? AND status='awaiting_worker'",
                (status, utcnow(), run_id, request.state.owner_id),
            ).rowcount
        else:
            changed = conn.execute(
                "UPDATE runs SET status=?,updated_at=? WHERE id=? AND status='awaiting_worker'",
                (status, utcnow(), run_id),
            ).rowcount
        if not changed:
            raise HTTPException(status_code=409, detail="Run changed while the upload was being confirmed.")
        actor_type = "user" if row["owner_id"] else "system"
        record_run_event(conn, run_id, "apk_upload_verified", actor_type, row["owner_id"], {
            "apk_size_bytes": actual_size, "upload_method": "tus", "status": status,
        })
        record_audit_event(conn, row["owner_id"], actor_type, row["owner_id"], "run.apk_upload_verified", "run", run_id, {
            "apk_size_bytes": actual_size, "upload_method": "tus", "status": status,
        })
    message = (
        "APK upload verified in private storage and queued for an authenticated worker."
        if status == "queued" else
        "APK upload verified in private storage. This run is awaiting an execution worker."
    )
    return {
        "id": run_id,
        "created_at": row["created_at"],
        "status": status,
        "apk": {"name": row["apk_name"], "sha256": row["apk_sha256"], "size_bytes": actual_size, "uploaded": True},
        "persona": PERSONAS[row["persona_id"]],
        "message": message,
    }


@app.post("/api/v1/runs")
async def create_run(
    request: Request,
    persona_id: str = Form("budget-android"),
    apk: UploadFile = File(...),
):
    if not apk.filename:
        raise HTTPException(status_code=422, detail="An APK file is required to register a test run")
    if requires_persistent_database() and not STORAGE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Private Supabase Storage is required for APK uploads on serverless deployments.",
        )
    cleanup_expired_uploads()
    if persona_id not in PERSONAS:
        raise HTTPException(status_code=422, detail="Unknown persona_id")
    owner_id = getattr(request.state, "owner_id", None)
    with db() as conn:
        enforce_run_quota(conn, owner_id, datetime.now(timezone.utc))
    run_id = str(uuid.uuid4())
    apk_name = None
    apk_hash = None
    apk_path = None
    apk_storage_path = None
    if apk is not None and apk.filename:
        safe_name = Path(apk.filename).name[:180]
        if not safe_name.lower().endswith(".apk"):
            raise HTTPException(status_code=415, detail="Upload must have an .apk filename")
        target = UPLOAD_DIR / f"{run_id}.apk"
        digest = hashlib.sha256()
        total = 0
        prefix = b""
        try:
            with target.open("wb") as out:
                while chunk := await apk.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail=f"APK exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB limit")
                    if len(prefix) < 4:
                        prefix += chunk[:4-len(prefix)]
                    digest.update(chunk)
                    out.write(chunk)
            if prefix[:2] != b"PK":
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=415, detail="File does not look like a ZIP-based APK (missing PK header)")
            validate_apk_archive(target)
            if STORAGE_ENABLED:
                apk_storage_path = f"runs/{run_id}/input.apk"
                try:
                    await asyncio.to_thread(upload_private_object, target, apk_storage_path)
                except Exception as exc:
                    raise HTTPException(status_code=503, detail="Private APK storage is unavailable; upload was not queued") from exc
                target.unlink(missing_ok=True)
            else:
                apk_path = str(target)
        except Exception:
            target.unlink(missing_ok=True)
            if apk_storage_path:
                try:
                    delete_private_object(apk_storage_path)
                except Exception:
                    pass
            raise
        apk_name, apk_hash = safe_name, digest.hexdigest()
    worker_configured = len(os.getenv("BHARATSIM_WORKER_TOKEN", "")) >= 32
    status = "queued" if (apk_path or apk_storage_path) and worker_configured else "awaiting_worker"
    created = utcnow()
    try:
        with db() as conn:
            enforce_run_quota(conn, owner_id, datetime.now(timezone.utc))
            conn.execute(
                "INSERT INTO runs(id,created_at,status,apk_name,apk_sha256,apk_path,persona_id,result_json,error,updated_at,owner_id,apk_storage_path) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, created, status, apk_name, apk_hash, apk_path, persona_id, None, None, created, owner_id, apk_storage_path),
            )
            actor_type = "user" if owner_id else "system"
            record_run_event(conn, run_id, "run_created", actor_type, owner_id, {
                "persona_id": persona_id, "apk_name": apk_name, "apk_sha256": apk_hash,
                "upload_method": "multipart", "status": status,
            })
            record_audit_event(conn, owner_id, actor_type, owner_id, "run.created", "run", run_id, {
                "persona_id": persona_id, "apk_name": apk_name, "apk_sha256": apk_hash,
                "upload_method": "multipart", "status": status,
            })
    except Exception:
        if apk_storage_path:
            try:
                delete_private_object(apk_storage_path)
            except Exception:
                pass
        if apk_path:
            Path(apk_path).unlink(missing_ok=True)
        raise
    message = (
        "APK queued for an authenticated worker. Execution is not complete until the worker submits evidence."
        if status == "queued" else
        "Upload recorded. No execution worker is configured, so this run is awaiting a worker; no APK execution is claimed."
    )
    return {
        "id": run_id, "created_at": created, "status": status,
        "apk": {"name": apk_name, "sha256": apk_hash, "uploaded": bool(apk_name)},
        "persona": PERSONAS[persona_id],
        "message": message,
    }

@app.get("/api/v1/runs")
def list_runs(request: Request, limit: int = 25):
    limit = max(1, min(limit, 100))
    with db() as conn:
        if AUTH_REQUIRED:
            rows = conn.execute("SELECT id,created_at,status,apk_name,apk_sha256,persona_id,error FROM runs WHERE owner_id=? ORDER BY created_at DESC LIMIT ?", (request.state.owner_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT id,created_at,status,apk_name,apk_sha256,persona_id,error FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [dict(row) for row in rows]}

def require_worker_token(request: Request) -> None:
    """Authenticate a separately deployed worker with a high-entropy shared secret."""
    expected = os.getenv("BHARATSIM_WORKER_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Worker integration is not configured")
    supplied = request.headers.get("X-BharatSim-Worker-Token", "")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid worker token")


def production_worker_execution_enabled() -> bool:
    """Require an attested host before any serverless deployment can dispatch APKs."""
    if is_serverless_runtime() and APP_ENV not in {"production", "prod"}:
        return False
    if APP_ENV not in {"production", "prod"}:
        return True
    return all(
        os.getenv(name, "false").strip().lower() == "true"
        for name in (
            "BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED",
            "BHARATSIM_WORKER_ISOLATION_ATTESTED",
            "BHARATSIM_WORKER_EGRESS_RESTRICTED",
        )
    )


def require_production_worker_execution_approval() -> None:
    if not production_worker_execution_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Public APK execution is disabled. Enable it only after provisioning a disposable worker VM, "
                "independently verifying isolation and default-deny egress, and setting all three worker safety flags."
            ),
        )


@app.post("/internal/worker/claim")
def worker_claim(request: Request, payload: WorkerClaimRequest):
    require_worker_token(request)
    require_production_worker_execution_approval()
    cleanup_expired_uploads()
    now = datetime.now(timezone.utc)
    now_text = now.isoformat()
    lease_until = datetime.fromtimestamp(now.timestamp() + 300, timezone.utc).isoformat()
    lease_token = uuid.uuid4().hex + uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            "INSERT INTO workers(id,last_seen,status,current_run_id) VALUES(?,?,?,NULL) "
            "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen,status='idle',current_run_id=NULL",
            (payload.worker_id, now_text, "idle"),
        )
        expired_leases = conn.execute(
            "SELECT id,owner_id,worker_id,attempts FROM runs WHERE status='leased' AND lease_until < ?",
            (now_text,),
        ).fetchall()
        for expired in expired_leases:
            record_run_event(conn, expired["id"], "worker_lease_expired", "system", None, {
                "worker_id": expired["worker_id"], "attempts": expired["attempts"],
            })
            record_audit_event(conn, expired["owner_id"], "system", None, "run.lease_expired", "run", expired["id"], {
                "worker_id": expired["worker_id"], "attempts": expired["attempts"],
            })
        conn.execute(
            "UPDATE runs SET status='queued', lease_token=NULL, lease_until=NULL, worker_id=NULL, updated_at=? "
            "WHERE status='leased' AND lease_until < ? AND attempts < 3",
            (now_text, now_text),
        )
        conn.execute(
            "UPDATE runs SET status='failed', error='Worker lease expired after maximum attempts', updated_at=? "
            "WHERE status='leased' AND lease_until < ? AND attempts >= 3",
            (now_text, now_text),
        )
        row = conn.execute(
            "SELECT id,apk_name,apk_sha256,persona_id,attempts,owner_id FROM runs "
            "WHERE status='queued' AND (apk_path IS NOT NULL OR apk_storage_path IS NOT NULL) ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return {"job": None}
        updated = conn.execute(
            "UPDATE runs SET status='leased', lease_token=?, lease_until=?, worker_id=?, attempts=attempts+1, updated_at=? "
            "WHERE id=? AND status='queued'",
            (lease_token, lease_until, payload.worker_id, now_text, row["id"]),
        )
        if updated.rowcount != 1:
            return {"job": None}
        conn.execute(
            "UPDATE workers SET last_seen=?, status='running', current_run_id=? WHERE id=?",
            (now_text, row["id"], payload.worker_id),
        )
        record_run_event(conn, row["id"], "worker_claimed", "worker", payload.worker_id, {
            "attempt": row["attempts"] + 1,
        })
        record_audit_event(conn, row["owner_id"], "worker", payload.worker_id, "worker.run_claimed", "run", row["id"], {
            "attempt": row["attempts"] + 1,
        })
        return {"job": {
            "id": row["id"], "apk_name": row["apk_name"], "apk_sha256": row["apk_sha256"],
            "persona_id": row["persona_id"], "attempt": row["attempts"] + 1,
            "persona_profile": PERSONAS.get(row["persona_id"], {}),
            "lease_token": lease_token, "lease_until": lease_until,
            "apk_url": f"/internal/worker/runs/{row['id']}/apk",
            "heartbeat_url": f"/internal/worker/runs/{row['id']}/heartbeat",
            "result_url": f"/internal/worker/runs/{row['id']}/result",
        }}


def require_live_lease(conn: sqlite3.Connection, run_id: str, lease_token: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id,status,lease_token,lease_until,apk_path,apk_storage_path,apk_sha256,owner_id,worker_id,attempts FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if row["status"] != "leased" or not row["lease_token"] or not hmac.compare_digest(row["lease_token"], lease_token):
        raise HTTPException(status_code=409, detail="Worker lease is stale or no longer owns this run")
    if row["lease_until"] and row["lease_until"] < utcnow():
        raise HTTPException(status_code=409, detail="Worker lease expired; claim the job again")
    return row


@app.get("/internal/worker/runs/{run_id}/apk")
def worker_download_apk(run_id: str, request: Request, lease_token: str = Header(..., alias="X-BharatSim-Lease-Token")):
    require_worker_token(request)
    with db() as conn:
        row = require_live_lease(conn, run_id, lease_token)
        if row["apk_storage_path"]:
            try:
                connection, response = open_private_object(row["apk_storage_path"])
            except Exception as exc:
                raise HTTPException(status_code=502, detail="Private APK artifact could not be retrieved") from exc
            def stream_object():
                try:
                    while chunk := response.read(1024 * 1024):
                        yield chunk
                finally:
                    response.close()
                    connection.close()
            headers = {"Content-Disposition": f'attachment; filename="{run_id}.apk"'}
            length = response.getheader("Content-Length")
            if length:
                headers["Content-Length"] = length
            return StreamingResponse(stream_object(), media_type="application/vnd.android.package-archive", headers=headers)
        if not row["apk_path"]:
            raise HTTPException(status_code=410, detail="APK artifact is no longer available")
        path = Path(row["apk_path"]).resolve()
        if not path.is_file() or path.parent != UPLOAD_DIR.resolve():
            raise HTTPException(status_code=410, detail="APK artifact is no longer available")
        return FileResponse(path, media_type="application/vnd.android.package-archive", filename=f"{run_id}.apk")


@app.post("/internal/worker/runs/{run_id}/heartbeat")
def worker_heartbeat(run_id: str, request: Request, payload: WorkerHeartbeatRequest):
    require_worker_token(request)
    now = datetime.now(timezone.utc)
    new_lease = datetime.fromtimestamp(now.timestamp() + 300, timezone.utc).isoformat()
    now_text = now.isoformat()
    with db() as conn:
        require_live_lease(conn, run_id, payload.lease_token)
        updated = conn.execute(
            "UPDATE runs SET lease_until=?, updated_at=? "
            "WHERE id=? AND status='leased' AND lease_token=? AND lease_until IS NOT NULL AND lease_until>=?",
            (new_lease, now_text, run_id, payload.lease_token, now_text),
        )
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="Worker lease changed or expired before heartbeat")
        conn.execute(
            "UPDATE workers SET last_seen=?,status='running',current_run_id=? WHERE id=(SELECT worker_id FROM runs WHERE id=?)",
            (now_text, run_id, run_id),
        )
    return {"ok": True, "lease_until": new_lease}


@app.post("/internal/worker/runs/{run_id}/result")
def worker_submit_result(run_id: str, request: Request, payload: WorkerResultRequest):
    require_worker_token(request)
    encoded = json.dumps(payload.result, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 250_000:
        raise HTTPException(status_code=413, detail="Worker result exceeds the 250 KB inline limit")
    with db() as conn:
        lease = require_live_lease(conn, run_id, payload.lease_token)
        if payload.status == "completed" and payload.result.get("status") != "completed":
            raise HTTPException(status_code=422, detail="Completed result must include report status=completed")
        if payload.status == "failed" and payload.result.get("status") not in (None, "failed"):
            raise HTTPException(status_code=422, detail="Failed result must not contain a completed report")
        reported_hash = payload.result.get("apk_sha256")
        if payload.status == "completed" and (
            not isinstance(reported_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", reported_hash)
        ):
            raise HTTPException(status_code=422, detail="Completed result must include a valid APK SHA-256")
        if reported_hash is not None and (
            not isinstance(reported_hash, str)
            or not hmac.compare_digest(reported_hash, str(lease["apk_sha256"] or ""))
        ):
            raise HTTPException(status_code=422, detail="Worker report APK SHA-256 does not match the queued artifact")
        now_text = utcnow()
        worker = conn.execute("SELECT worker_id FROM runs WHERE id=?", (run_id,)).fetchone()
        updated = conn.execute(
            "UPDATE runs SET status=?, result_json=?, error=?, lease_token=NULL, lease_until=NULL, updated_at=? "
            "WHERE id=? AND status='leased' AND lease_token=? AND lease_until IS NOT NULL AND lease_until>=?",
            (payload.status, encoded, payload.error, now_text, run_id, payload.lease_token, now_text),
        )
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="Worker lease changed or expired before result submission")
        actor_id = lease["worker_id"] or (worker["worker_id"] if worker else None)
        action = "run.completed" if payload.status == "completed" else "run.failed"
        record_run_event(conn, run_id, "worker_result_submitted", "worker", actor_id, {
            "status": payload.status, "attempt": lease["attempts"], "apk_sha256": reported_hash,
        })
        record_audit_event(conn, lease["owner_id"], "worker", actor_id, action, "run", run_id, {
            "status": payload.status, "attempt": lease["attempts"], "apk_sha256": reported_hash,
        })
        if worker and worker["worker_id"]:
            conn.execute(
                "UPDATE workers SET last_seen=?,status='idle',current_run_id=NULL WHERE id=?",
                (now_text, worker["worker_id"]),
            )
        apk_path = Path(lease["apk_path"]).resolve() if lease["apk_path"] else None
    apk_storage_path = lease["apk_storage_path"]
    # The bounded report is persisted first; remove the uploaded executable after the terminal result.
    apk_deleted = not apk_storage_path and not apk_path
    if apk_path and apk_path.parent == UPLOAD_DIR.resolve():
        try:
            apk_path.unlink(missing_ok=True)
            apk_deleted = not apk_path.exists()
        except OSError:
            apk_deleted = False
    if apk_storage_path:
        try:
            delete_private_object(apk_storage_path)
            apk_deleted = True
        except Exception:
            apk_deleted = False
    if apk_deleted:
        with db() as conn:
            conn.execute("UPDATE runs SET apk_path=NULL,apk_storage_path=NULL WHERE id=?", (run_id,))
    return {"id": run_id, "status": payload.status, "evidence_saved": True, "apk_deleted": apk_deleted}


@app.get("/api/v1/workers")
def worker_status():
    now = datetime.now(timezone.utc)
    with db() as conn:
        rows = conn.execute("SELECT id,last_seen,status,current_run_id FROM workers ORDER BY last_seen DESC LIMIT 50").fetchall()
    items = []
    for row in rows:
        try:
            seen = datetime.fromisoformat(row["last_seen"])
            online = (now - seen).total_seconds() <= 90
        except (TypeError, ValueError):
            online = False
        # Do not expose a worker's current run ID: it may belong to another tenant.
        items.append({"id": row["id"], "last_seen": row["last_seen"], "status": row["status"] if online else "offline",
                      "online": online, "busy": bool(online and row["current_run_id"])})
    return {"items": items, "online_count": sum(1 for item in items if item["online"])}


@app.delete("/api/v1/runs/{run_id}")
def delete_run(run_id: str, request: Request):
    """Delete a user's run and its associated evidence; never interrupt an active worker."""
    with db() as conn:
        if AUTH_REQUIRED:
            row = conn.execute(
                "SELECT id,status,apk_path,apk_storage_path,owner_id FROM runs WHERE id=? AND owner_id=?",
                (run_id, request.state.owner_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id,status,apk_path,apk_storage_path,owner_id FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        if row["status"] in ("leased", "running"):
            raise HTTPException(
                status_code=409,
                detail="This run is being executed by a worker. Wait for it to finish before deleting its evidence.",
            )
        # Transition first so a concurrent worker claim cannot acquire this queued run
        # while the external object is being deleted. Keep the row if cleanup fails so
        # the user can retry deletion safely.
        if AUTH_REQUIRED:
            updated = conn.execute(
                "UPDATE runs SET status='cancelled',error='Deleted by owner',lease_token=NULL,lease_until=NULL,updated_at=? "
                "WHERE id=? AND owner_id=? AND status NOT IN ('leased','running')",
                (utcnow(), run_id, request.state.owner_id),
            )
        else:
            updated = conn.execute(
                "UPDATE runs SET status='cancelled',error='Deleted by owner',lease_token=NULL,lease_until=NULL,updated_at=? "
                "WHERE id=? AND status NOT IN ('leased','running')",
                (utcnow(), run_id),
            )
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="Run state changed; refresh before deleting")
        record_audit_event(conn, row["owner_id"], "user" if row["owner_id"] else "system",
                           getattr(request.state, "owner_id", None), "run.deletion_requested", "run", run_id,
                           {"previous_status": row["status"]})
        conn.execute(
            "UPDATE workers SET status='idle',current_run_id=NULL WHERE current_run_id=?",
            (run_id,),
        )

    apk_path = Path(row["apk_path"]).resolve() if row["apk_path"] else None
    if apk_path:
        if apk_path.parent != UPLOAD_DIR.resolve():
            raise HTTPException(status_code=503, detail="Run was cancelled, but its local APK path failed the storage safety check")
        try:
            apk_path.unlink(missing_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Run was cancelled, but its local APK could not be deleted; retry deletion") from exc
    if row["apk_storage_path"]:
        try:
            delete_private_object(row["apk_storage_path"])
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Run was cancelled, but its private APK could not be deleted; retry deletion") from exc

    with db() as conn:
        if AUTH_REQUIRED:
            conn.execute(
                "DELETE FROM analyses WHERE run_id=? AND owner_id=?",
                (run_id, request.state.owner_id),
            )
            deleted = conn.execute(
                "DELETE FROM runs WHERE id=? AND owner_id=? AND status='cancelled'",
                (run_id, request.state.owner_id),
            )
        else:
            conn.execute("DELETE FROM analyses WHERE run_id=?", (run_id,))
            deleted = conn.execute(
                "DELETE FROM runs WHERE id=? AND status='cancelled'",
                (run_id,),
            )
        if deleted.rowcount != 1:
            raise HTTPException(status_code=409, detail="Run cleanup completed, but the record changed; refresh and retry")
        record_audit_event(conn, row["owner_id"], "user" if row["owner_id"] else "system",
                           getattr(request.state, "owner_id", None), "run.deleted", "run", run_id, {})
    return {"id": run_id, "deleted": True}


@app.get("/api/v1/runs/{run_id}/report")
def export_run_report(run_id: str, request: Request):
    """Export a completed worker report with stable report and file integrity hashes."""
    with db() as conn:
        if AUTH_REQUIRED:
            row = conn.execute(
                "SELECT id,created_at,status,apk_name,apk_sha256,persona_id,result_json,error "
                "FROM runs WHERE id=? AND owner_id=?",
                (run_id, request.state.owner_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id,created_at,status,apk_name,apk_sha256,persona_id,result_json,error "
                "FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if not row["result_json"]:
        raise HTTPException(status_code=409, detail="No worker report is available for this run yet")
    report = json.loads(row["result_json"])
    diagnostics = fuse_worker_report(report)
    canonical_report = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_diagnostics = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    export = {
        "schema_version": "1.0",
        "generated_at": utcnow(),
        "run": {
            "id": row["id"],
            "created_at": row["created_at"],
            "status": row["status"],
            "apk_name": row["apk_name"],
            "apk_sha256": row["apk_sha256"],
            "persona_id": row["persona_id"],
            "error": row["error"],
        },
        "report": report,
        "diagnostics": diagnostics,
        "integrity": {
            "report_sha256": hashlib.sha256(canonical_report).hexdigest(),
            "report_hash_method": "SHA-256 of the original worker report JSON serialized with sorted keys and compact separators",
            "diagnostics_sha256": hashlib.sha256(canonical_diagnostics).hexdigest(),
            "diagnostics_hash_method": "SHA-256 of derived evidence synthesis JSON serialized with sorted keys and compact separators",
        },
    }
    content = json.dumps(export, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    file_digest = hashlib.sha256(content).hexdigest()
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="bharatsim-run-report.json"',
            "Cache-Control": "private, no-store",
            "ETag": f'"{file_digest}"',
            "X-Content-SHA256": file_digest,
        },
    )


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str, request: Request):
    with db() as conn:
        if AUTH_REQUIRED:
            row = conn.execute("SELECT id,created_at,status,apk_name,apk_sha256,persona_id,result_json,error FROM runs WHERE id=? AND owner_id=?", (run_id, request.state.owner_id)).fetchone()
        else:
            row = conn.execute("SELECT id,created_at,status,apk_name,apk_sha256,persona_id,result_json,error FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    result = dict(row)
    result["result"] = json.loads(result.pop("result_json")) if result.get("result_json") else None
    if isinstance(result["result"], dict):
        result["result"]["diagnostics"] = fuse_worker_report(result["result"])
    return result


@app.get("/api/v1/runs/{run_id}/events")
def list_run_events(run_id: str, request: Request, limit: int = 100):
    limit = max(1, min(limit, 200))
    with db() as conn:
        if AUTH_REQUIRED:
            owned = conn.execute("SELECT id FROM runs WHERE id=? AND owner_id=?", (run_id, request.state.owner_id)).fetchone()
            if not owned:
                raise HTTPException(status_code=404, detail="Run not found")
        else:
            exists = conn.execute("SELECT id FROM runs WHERE id=?", (run_id,)).fetchone()
            if not exists:
                raise HTTPException(status_code=404, detail="Run not found")
        rows = conn.execute(
            "SELECT id,event_type,created_at,actor_type,actor_id,payload_json FROM run_events WHERE run_id=? ORDER BY id ASC LIMIT ?",
            (run_id, limit),
        ).fetchall()
    return {"items": [
        {"id": row["id"], "event_type": row["event_type"], "created_at": row["created_at"],
         "actor_type": row["actor_type"], "actor_id": row["actor_id"], "payload": json.loads(row["payload_json"])}
        for row in rows
    ]}


@app.post("/api/v1/analyze/logs")
def analyze_logs(payload: LogAnalysisRequest, request: Request):
    if payload.persona_id not in PERSONAS:
        raise HTTPException(status_code=422, detail="Unknown persona_id")
    if payload.run_id:
        with db() as conn:
            if AUTH_REQUIRED:
                owned = conn.execute("SELECT id FROM runs WHERE id=? AND owner_id=?", (payload.run_id, request.state.owner_id)).fetchone()
            else:
                owned = conn.execute("SELECT id FROM runs WHERE id=?", (payload.run_id,)).fetchone()
        if not owned:
            raise HTTPException(status_code=404, detail="Run not found")
    result = analyze_log_text(payload.text, payload.persona_id)
    database_available = bool(DATABASE_URL) if requires_persistent_database() else True
    if database_available:
        result["persistence"] = {"saved": True}
        with db() as conn:
            conn.execute("INSERT INTO analyses(id,created_at,run_id,persona_id,result_json,owner_id) VALUES(?,?,?,?,?,?)",
                         (result["id"], result["created_at"], payload.run_id, payload.persona_id, json.dumps(result), getattr(request.state, "owner_id", None)))
            owner_id = getattr(request.state, "owner_id", None)
            actor_type = "user" if owner_id else "system"
            record_audit_event(conn, owner_id, actor_type, owner_id, "analysis.created", "analysis", result["id"], {
                "persona_id": payload.persona_id, "run_id": payload.run_id,
                "finding_count": result["summary"]["finding_count"],
                "occurrence_count": result["summary"].get("occurrence_count", result["summary"]["finding_count"]),
            })
            if payload.run_id:
                record_run_event(conn, payload.run_id, "log_analysis_created", actor_type, owner_id, {
                    "analysis_id": result["id"], "finding_count": result["summary"]["finding_count"],
                })
    else:
        # Stateless log analysis remains useful when production persistence is
        # not configured. Never imply that the report was saved or recoverable.
        result["persistence"] = {
            "saved": False,
            "reason": "Persistent PostgreSQL is not configured; this report is available only in the current browser session.",
        }
    return result

@app.get("/api/v1/analyses")
def list_analyses(request: Request, limit: int = 20):
    limit = max(1, min(limit, 100))
    with db() as conn:
        if AUTH_REQUIRED:
            rows = conn.execute("SELECT result_json FROM analyses WHERE owner_id=? ORDER BY created_at DESC LIMIT ?", (request.state.owner_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT result_json FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [json.loads(row["result_json"]) for row in rows]}

@app.post("/api/v1/translate/report")
def translate_report(payload: SarvamTranslationRequest):
    """Translate a user-requested, condensed report summary via Sarvam AI."""
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Translation text cannot be blank.")
    if len(os.getenv("SARVAM_API_KEY", "").strip()) < 16:
        raise HTTPException(status_code=503, detail="Sarvam translation is not configured on this server.")
    try:
        return {
            "translated_text": translate_report_text(payload.text, payload.target_language_code),
            "target_language_code": payload.target_language_code,
            "provider": "sarvam",
        }
    except SarvamRateLimited:
        raise HTTPException(status_code=429, detail="Sarvam is rate limiting translation requests. Please try again later.")
    except SarvamProviderError:
        raise HTTPException(status_code=502, detail="Sarvam translation is temporarily unavailable. Your original report is unchanged.")


@app.get("/api/v1/capabilities")
def capabilities():
    persistent_database_required = requires_persistent_database()
    database_configured = bool(DATABASE_URL) if persistent_database_required else True
    upload_available = database_configured and (STORAGE_ENABLED if persistent_database_required else True)
    direct_upload_available = database_configured and STORAGE_ENABLED
    worker = len(os.getenv("BHARATSIM_WORKER_TOKEN", "")) >= 32 and production_worker_execution_enabled()
    return {
        "database_persistence": database_configured,
        "apk_upload": upload_available, "direct_apk_upload": direct_upload_available,
        "log_analysis": True, "analysis_persistence": database_configured, "risk_planner": True,
        "failure_fingerprinting": True, "bharat_score": True,
        "android_execution": False,
        "worker_dispatch": worker,
        "network_shaping": False,
        "emulator_network_controls": {
            "latency": True,
            "bandwidth": True,
            "configuration_readback": True,
            "packet_loss": False,
            "outage_and_recovery": False,
            "arbitrary_app_traffic_verified": False,
            "scope": "Android Emulator console controls; fixture traffic-path evidence is available from CI only",
        },
        "persona_condition_simulation": {
            "supported": ["network_latency", "download_bandwidth", "battery_saver", "storage_pressure"],
            "control_plane_verifiable": ["upload_bandwidth"],
            "report_only": ["ram_constraint"],
            "unsupported": ["packet_loss", "cpu_constraint"],
            "scope": "Worker executes conditions on disposable Android Emulator targets only; active data-plane app traffic is unverified",
        },
        "sarvam_translation": len(os.getenv("SARVAM_API_KEY", "").strip()) >= 16,
        "notes": [
            "Production worker dispatch remains disabled until BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED, BHARATSIM_WORKER_ISOLATION_ATTESTED, and BHARATSIM_WORKER_EGRESS_RESTRICTED are all true. These flags are operator attestations, not cryptographic proof; independently verify the disposable VM and egress policy before enabling them.",
            "Worker dispatch is configured only when BHARATSIM_WORKER_TOKEN is set and the production safety gate is open; android_execution remains false here because this API cannot prove a live emulator has executed an APK. Check /api/v1/workers for recent worker heartbeats.",
            "The worker supports Android Emulator console latency and bandwidth controls plus reversible battery-saver and bounded storage-pressure simulation with readback/reset evidence. Full persona shaping remains false because packet loss, CPU throttling, RAM restriction, outage/recovery, and arbitrary-app traffic verification are not supported.",
            "Sarvam translation is available only when SARVAM_API_KEY is configured; only the user-selected condensed report summary is sent.",
            "When private Storage is configured, APK bytes use short-lived signed uploads directly to Supabase Storage, bypassing Vercel function request-body limits. The API verifies the stored object size before queueing.",
            "Worker result payloads are bounded and protected by lease tokens; inline artifact payloads are limited to 250 KB.",
        ],
    }


# The Vercel customer-facing project builds the Vite dashboard and serves it
# from this same FastAPI deployment. During backend-only unit tests the build
# output is absent, so the API remains independently importable.
_FRONTEND_BUILD = Path("frontend/dist")
if _FRONTEND_BUILD.is_dir():
    app.frontend("/", directory="frontend/dist", fallback="index.html")
