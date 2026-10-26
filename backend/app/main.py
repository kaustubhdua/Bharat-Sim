from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("BHARATSIM_DATA_DIR", str(APP_DIR.parent / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "bharatsim.sqlite3"
MAX_UPLOAD_BYTES = max(1, min(int(os.getenv("BHARATSIM_MAX_UPLOAD_MB", "150")), 150)) * 1024 * 1024
MAX_APK_ENTRIES = 10000
MAX_APK_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_APK_COMPRESSION_RATIO = 1000
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-BharatSim-API-Key"],
)

@app.middleware("http")
async def enforce_shared_api_key(request: Request, call_next):
    """Optional single shared-key gate for private deployments; not multi-tenant auth."""
    if request.url.path.startswith("/api/v1/") and os.getenv("BHARATSIM_REQUIRE_API_KEY", "false").lower() == "true":
        expected = os.getenv("BHARATSIM_API_KEY", "")
        if len(expected) < 32:
            return JSONResponse(status_code=503, content={"detail": "API authentication is required but BHARATSIM_API_KEY is not configured safely"})
        supplied = request.headers.get("X-BharatSim-API-Key", "")
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key"})
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

class PlanRequest(BaseModel):
    persona_ids: list[str] = Field(default_factory=lambda: ["budget-android", "edge-village"])
    app_category: str = "general"
    critical_flows: list[str] = Field(default_factory=lambda: ["cold start", "login", "primary action", "network retry"])
    max_scenarios: int = Field(default=6, ge=1, le=20)

class LogAnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_000_000)
    persona_id: str = "budget-android"
    run_id: str | None = None

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

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
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
        # Backward-compatible schema migration for databases created by earlier MVP commits.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        migrations = {
            "lease_token": "TEXT",
            "lease_until": "TEXT",
            "worker_id": "TEXT",
            "updated_at": "TEXT",
            "attempts": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in migrations.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")

init_db()


def cleanup_expired_uploads() -> None:
    """Expire abandoned APK uploads after 24 hours and remove old terminal-run APKs."""
    now = datetime.now(timezone.utc)
    cutoff = datetime.fromtimestamp(now.timestamp() - 24 * 60 * 60, timezone.utc).isoformat()
    now_text = now.isoformat()
    with db() as conn:
        rows = conn.execute(
            "SELECT id,apk_path,status,lease_until FROM runs WHERE apk_path IS NOT NULL AND created_at < ?",
            (cutoff,),
        ).fetchall()
        for row in rows:
            if row["status"] == "leased" and row["lease_until"] and row["lease_until"] >= now_text:
                continue
            path = Path(row["apk_path"]).resolve()
            if path.parent != UPLOAD_DIR.resolve():
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            if row["status"] in ("awaiting_worker", "queued", "leased"):
                conn.execute(
                    "UPDATE runs SET status='failed',error='APK upload expired before execution',apk_path=NULL,"
                    "lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                    (now_text, row["id"]),
                )
            else:
                conn.execute("UPDATE runs SET apk_path=NULL WHERE id=?", (row["id"],))


cleanup_expired_uploads()


def failure_fingerprint(line: str) -> str:
    normalized = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", line)
    normalized = re.sub(r"\b\d+\b", "<N>", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:12]

def analyze_log_text(text: str, persona_id: str = "budget-android") -> dict[str, Any]:
    """Deterministic baseline detector. Signals are evidence, not proof of root cause."""
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
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, line in enumerate(lines, start=1):
        for kind, pattern, title in rules:
            if pattern.search(line):
                fingerprint = failure_fingerprint(f"{kind}:{line}")
                key = (kind, fingerprint)
                if key not in seen:
                    seen.add(key)
                    findings.append({
                        "id": fingerprint, "kind": kind, "title": title,
                        "severity": "critical" if kind in ("crash", "anr", "oom") else "high" if kind in ("storage", "network") else "medium",
                        "evidence": [{"line": index, "text": line[:600]}],
                        "fingerprint": fingerprint,
                        "explanation": {
                            "crash": "The log contains a fatal process or exception marker. Inspect the adjacent stack trace to locate the originating frame.",
                            "anr": "The log contains an ANR or input-dispatch timeout marker. Main-thread traces and timing are needed to confirm the blocking operation.",
                            "oom": "The log contains a memory allocation or low-memory marker. Compare heap/native memory, process importance and device RAM.",
                            "network": "The log contains a connection or timeout failure. Check retry behavior, cancellation, timeout budgets and offline UI state.",
                            "strictmode": "The log contains a StrictMode or main-thread disk I/O marker. Profile the affected interaction before attributing user-visible jank.",
                            "storage": "The log contains a storage exhaustion marker. Check free-space handling, cache eviction and write-failure recovery.",
                        }[kind],
                        "recommendation": {
                            "crash": "Review the first app-owned frame in the full stack trace and add a regression test for this path.",
                            "anr": "Capture a thread dump and move blocking I/O or long work off the main thread.",
                            "oom": "Capture a memory profile; bound caches and release large references on lifecycle transitions.",
                            "network": "Use bounded retries with exponential backoff, explicit timeouts and a recoverable offline state.",
                            "strictmode": "Move disk operations off the main thread and measure frame latency around the affected flow.",
                            "storage": "Handle ENOSPC explicitly and test cache cleanup and failed writes with low free space.",
                        }[kind],
                    })
                break
    critical = sum(1 for x in findings if x["severity"] == "critical")
    high = sum(1 for x in findings if x["severity"] == "high")
    medium = sum(1 for x in findings if x["severity"] == "medium")
    # Transparent heuristic, not a market/population estimate.
    score = max(0, min(100, 100 - critical * 28 - high * 14 - medium * 6))
    return {
        "id": str(uuid.uuid4()), "created_at": utcnow(), "persona": PERSONAS[persona_id],
        "source": "uploaded-log-text", "evidence_lines": len(lines),
        "findings": findings, "summary": {
            "finding_count": len(findings), "critical": critical, "high": high, "medium": medium,
            "clean": len(findings) == 0,
        },
        "bharat_score": {
            "value": score, "label": "Log resilience heuristic",
            "method": "100 − 28×critical − 14×high − 6×medium, clamped to 0–100",
            "warning": "Based only on detected markers in supplied logs; not a device-population estimate or proof of app quality.",
        },
        "limitations": [
            "Log markers are heuristic signals and may include false positives or miss failures.",
            "Root-cause statements are hypotheses until corroborated by full traces and reproduction.",
            "This analysis does not mean the APK was installed or executed.",
        ],
    }

@app.get("/")
def root():
    return {"name": "BharatSim API", "version": "0.1.0", "docs": "/docs", "status": "development"}

@app.get("/health/live")
def health_live():
    return {"status": "alive", "timestamp": utcnow()}

@app.get("/health/ready")
def health_ready():
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
        database_ok = True
    except sqlite3.Error:
        database_ok = False
    payload = {
        "status": "ready" if database_ok else "not_ready",
        "database": "available" if database_ok else "unavailable",
        "apk_execution_worker": "configured" if len(os.getenv("BHARATSIM_WORKER_TOKEN", "")) >= 32 else "not_configured",
        "execution_capability": "external-worker-required",
        "authentication_required": os.getenv("BHARATSIM_REQUIRE_API_KEY", "false").lower() == "true",
        "timestamp": utcnow(),
    }
    return JSONResponse(status_code=200 if database_ok else 503, content=payload)

@app.get("/api/v1/personas")
def list_personas():
    return {"items": list(PERSONAS.values())}

@app.post("/api/v1/plan")
def create_plan(request: PlanRequest):
    unknown = sorted(set(request.persona_ids) - set(PERSONAS))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown persona IDs: {', '.join(unknown)}")
    scenarios = []
    for pid in request.persona_ids:
        persona = PERSONAS[pid]
        for flow in request.critical_flows:
            score = 25
            score += 25 if persona["risk"] == "critical" else 15 if persona["risk"] == "high" else 0
            score += 15 if any(k in flow.lower() for k in ("network", "retry", "payment", "login")) else 0
            score += 10 if persona["storage_free_mb"] < 300 else 0
            scenarios.append({
                "id": f"{pid}:{re.sub(r'[^a-z0-9]+', '-', flow.lower()).strip('-')}",
                "persona_id": pid, "persona_name": persona["name"], "flow": flow,
                "risk_score": min(100, score),
                "reason": "Risk heuristic prioritizes constrained profiles and network-sensitive flows; score is a test-ordering aid, not predicted failure probability.",
            })
    scenarios.sort(key=lambda x: (-x["risk_score"], x["id"]))
    selected = scenarios[:request.max_scenarios]
    return {"generated_at": utcnow(), "strategy": "deterministic-risk-heuristic-v1", "scenarios": selected, "total_candidates": len(scenarios)}

@app.post("/api/v1/runs")
async def create_run(
    persona_id: str = Form("budget-android"),
    apk: UploadFile | None = File(default=None),
):
    cleanup_expired_uploads()
    if persona_id not in PERSONAS:
        raise HTTPException(status_code=422, detail="Unknown persona_id")
    run_id = str(uuid.uuid4())
    apk_name = None
    apk_hash = None
    apk_path = None
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
        except Exception:
            target.unlink(missing_ok=True)
            raise
        apk_name, apk_hash, apk_path = safe_name, digest.hexdigest(), str(target)
    worker_configured = len(os.getenv("BHARATSIM_WORKER_TOKEN", "")) >= 32
    status = "queued" if apk_path and worker_configured else "awaiting_worker"
    created = utcnow()
    with db() as conn:
        conn.execute(
            "INSERT INTO runs(id,created_at,status,apk_name,apk_sha256,apk_path,persona_id,result_json,error,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (run_id, created, status, apk_name, apk_hash, apk_path, persona_id, None, None, created),
        )
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
def list_runs(limit: int = 25):
    limit = max(1, min(limit, 100))
    with db() as conn:
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


@app.post("/internal/worker/claim")
def worker_claim(request: Request, payload: WorkerClaimRequest):
    require_worker_token(request)
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
            "SELECT id,apk_name,apk_sha256,persona_id,attempts FROM runs "
            "WHERE status='queued' AND apk_path IS NOT NULL ORDER BY created_at ASC LIMIT 1"
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
        "SELECT id,status,lease_token,lease_until,apk_path,apk_sha256 FROM runs WHERE id=?", (run_id,)
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
        path = Path(row["apk_path"]).resolve()
        if not path.is_file() or path.parent != UPLOAD_DIR.resolve():
            raise HTTPException(status_code=410, detail="APK artifact is no longer available")
        return FileResponse(path, media_type="application/vnd.android.package-archive", filename=f"{run_id}.apk")


@app.post("/internal/worker/runs/{run_id}/heartbeat")
def worker_heartbeat(run_id: str, request: Request, payload: WorkerHeartbeatRequest):
    require_worker_token(request)
    now = datetime.now(timezone.utc)
    new_lease = datetime.fromtimestamp(now.timestamp() + 300, timezone.utc).isoformat()
    with db() as conn:
        require_live_lease(conn, run_id, payload.lease_token)
        conn.execute(
            "UPDATE runs SET lease_until=?, updated_at=? WHERE id=? AND status='leased' AND lease_token=?",
            (new_lease, now.isoformat(), run_id, payload.lease_token),
        )
        conn.execute(
            "UPDATE workers SET last_seen=?,status='running',current_run_id=? WHERE id=(SELECT worker_id FROM runs WHERE id=?)",
            (now.isoformat(), run_id, run_id),
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
        if payload.result.get("apk_sha256") and payload.result["apk_sha256"] != lease["apk_sha256"]:
            raise HTTPException(status_code=422, detail="Worker report APK SHA-256 does not match the queued artifact")
        worker = conn.execute("SELECT worker_id FROM runs WHERE id=?", (run_id,)).fetchone()
        conn.execute(
            "UPDATE runs SET status=?, result_json=?, error=?, lease_token=NULL, lease_until=NULL, updated_at=? WHERE id=?",
            (payload.status, encoded, payload.error, utcnow(), run_id),
        )
        if worker and worker["worker_id"]:
            conn.execute(
                "UPDATE workers SET last_seen=?,status='idle',current_run_id=NULL WHERE id=?",
                (utcnow(), worker["worker_id"]),
            )
        apk_path = Path(lease["apk_path"]).resolve() if lease["apk_path"] else None
    # The bounded report is persisted first; remove the uploaded executable after the terminal result.
    apk_deleted = False
    if apk_path and apk_path.parent == UPLOAD_DIR.resolve():
        try:
            apk_path.unlink(missing_ok=True)
            apk_deleted = not apk_path.exists()
        except OSError:
            apk_deleted = False
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
        items.append({"id": row["id"], "last_seen": row["last_seen"], "status": row["status"] if online else "offline",
                      "online": online, "current_run_id": row["current_run_id"] if online else None})
    return {"items": items, "online_count": sum(1 for item in items if item["online"])}


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str):
    with db() as conn:
        row = conn.execute("SELECT id,created_at,status,apk_name,apk_sha256,persona_id,result_json,error FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    result = dict(row)
    result["result"] = json.loads(result.pop("result_json")) if result.get("result_json") else None
    return result

@app.post("/api/v1/analyze/logs")
def analyze_logs(request: LogAnalysisRequest):
    if request.persona_id not in PERSONAS:
        raise HTTPException(status_code=422, detail="Unknown persona_id")
    result = analyze_log_text(request.text, request.persona_id)
    with db() as conn:
        conn.execute("INSERT INTO analyses(id,created_at,run_id,persona_id,result_json) VALUES(?,?,?,?,?)",
                     (result["id"], result["created_at"], request.run_id, request.persona_id, json.dumps(result)))
    return result

@app.get("/api/v1/analyses")
def list_analyses(limit: int = 20):
    limit = max(1, min(limit, 100))
    with db() as conn:
        rows = conn.execute("SELECT result_json FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [json.loads(row["result_json"]) for row in rows]}

@app.get("/api/v1/capabilities")
def capabilities():
    worker = len(os.getenv("BHARATSIM_WORKER_TOKEN", "")) >= 32
    return {
        "apk_upload": True, "log_analysis": True, "risk_planner": True,
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
        "sarvam_translation": False,
        "notes": [
            "Worker dispatch is configured only when BHARATSIM_WORKER_TOKEN is set; android_execution remains false here because this API cannot prove a live emulator has executed an APK. Check /api/v1/workers for recent worker heartbeats.",
            "The worker supports Android Emulator console latency and bandwidth controls with readback and reset verification. Full persona shaping remains false because packet loss, outage/recovery, resource pressure, and arbitrary-app traffic verification are not supported.",
            "Sarvam translation is not wired into this application.",
            "Worker result payloads are bounded and protected by lease tokens; inline artifact payloads are limited to 250 KB.",
        ],
    }
