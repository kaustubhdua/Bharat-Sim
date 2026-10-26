import io
import os
import zipfile

from fastapi.testclient import TestClient

from app import main


def apk_bytes():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", b"test manifest")
        archive.writestr("classes.dex", b"test dex")
    return stream.getvalue()


def prepare_isolated_db(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    upload_dir = data_dir / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(main, "DB_PATH", data_dir / "test.sqlite3")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "UPLOAD_DIR", upload_dir)
    monkeypatch.setenv("BHARATSIM_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("BHARATSIM_WORKER_TOKEN", "worker-test-secret-" + "x" * 40)
    main.init_db()
    return TestClient(main.app)


def test_worker_claim_requires_worker_token(monkeypatch, tmp_path):
    client = prepare_isolated_db(monkeypatch, tmp_path)
    response = client.post("/internal/worker/claim", json={"worker_id": "test-worker"})
    assert response.status_code == 401


def test_worker_claim_download_and_result_round_trip(monkeypatch, tmp_path):
    client = prepare_isolated_db(monkeypatch, tmp_path)
    token = os.environ["BHARATSIM_WORKER_TOKEN"]
    headers = {"X-BharatSim-Worker-Token": token}

    apk_content = apk_bytes()
    created = client.post(
        "/api/v1/runs",
        data={"persona_id": "baseline"},
        files={"apk": ("tiny-test.apk", apk_content, "application/vnd.android.package-archive")},
    )
    assert created.status_code == 200
    run = created.json()
    assert run["status"] == "queued"
    run_id = run["id"]

    claimed = client.post("/internal/worker/claim", headers=headers, json={"worker_id": "ci-worker-1"})
    assert claimed.status_code == 200
    job = claimed.json()["job"]
    assert job["id"] == run_id
    assert job["attempt"] == 1

    downloaded = client.get(
        f"/internal/worker/runs/{run_id}/apk",
        headers={**headers, "X-BharatSim-Lease-Token": job["lease_token"]},
    )
    assert downloaded.status_code == 200
    assert downloaded.content == apk_content

    report = {
        "status": "completed",
        "schema_version": "1.0",
        "apk_sha256": run["apk"]["sha256"],
        "steps": [{"name": "test-fixture", "return_code": 0}],
        "limitations": ["This is a protocol test fixture, not a real emulator run."],
    }
    submitted = client.post(
        f"/internal/worker/runs/{run_id}/result",
        headers=headers,
        json={"lease_token": job["lease_token"], "status": "completed", "result": report},
    )
    assert submitted.status_code == 200
    assert submitted.json()["evidence_saved"] is True
    assert submitted.json()["apk_deleted"] is True
    assert not (main.UPLOAD_DIR / f"{run_id}.apk").exists()

    fetched = client.get(f"/api/v1/runs/{run_id}").json()
    assert fetched["status"] == "completed"
    assert fetched["result"]["schema_version"] == "1.0"
    assert client.get("/api/v1/workers").json()["online_count"] == 1

    stale = client.post(
        f"/internal/worker/runs/{run_id}/result",
        headers=headers,
        json={"lease_token": job["lease_token"], "status": "completed", "result": report},
    )
    assert stale.status_code == 409


def test_worker_cannot_claim_success_without_completed_report(monkeypatch, tmp_path):
    client = prepare_isolated_db(monkeypatch, tmp_path)
    token = os.environ["BHARATSIM_WORKER_TOKEN"]
    headers = {"X-BharatSim-Worker-Token": token}
    created = client.post(
        "/api/v1/runs",
        data={"persona_id": "baseline"},
        files={"apk": ("tiny-test.apk", apk_bytes(), "application/vnd.android.package-archive")},
    )
    run_id = created.json()["id"]
    job = client.post("/internal/worker/claim", headers=headers, json={"worker_id": "ci-worker-2"}).json()["job"]
    response = client.post(
        f"/internal/worker/runs/{run_id}/result",
        headers=headers,
        json={"lease_token": job["lease_token"], "status": "completed", "result": {"status": "failed"}},
    )
    assert response.status_code == 422

def test_abandoned_apk_upload_expires_after_retention_window(monkeypatch, tmp_path):
    client = prepare_isolated_db(monkeypatch, tmp_path)
    token = os.environ["BHARATSIM_WORKER_TOKEN"]
    created = client.post(
        "/api/v1/runs",
        data={"persona_id": "baseline"},
        files={"apk": ("expired.apk", apk_bytes(), "application/vnd.android.package-archive")},
    )
    run_id = created.json()["id"]
    apk_path = main.UPLOAD_DIR / f"{run_id}.apk"
    assert apk_path.exists()
    with main.db() as conn:
        conn.execute("UPDATE runs SET created_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", run_id))
    main.cleanup_expired_uploads()
    fetched = client.get(f"/api/v1/runs/{run_id}").json()
    assert fetched["status"] == "failed"
    assert fetched["error"] == "APK upload expired before execution"
    assert not apk_path.exists()

def test_worker_cannot_submit_evidence_for_a_different_apk(monkeypatch, tmp_path):
    client = prepare_isolated_db(monkeypatch, tmp_path)
    headers = {"X-BharatSim-Worker-Token": os.environ["BHARATSIM_WORKER_TOKEN"]}
    created = client.post(
        "/api/v1/runs",
        data={"persona_id": "baseline"},
        files={"apk": ("hash-check.apk", apk_bytes(), "application/vnd.android.package-archive")},
    )
    run = created.json()
    job = client.post(
        "/internal/worker/claim", headers=headers, json={"worker_id": "hash-check-worker"}
    ).json()["job"]
    response = client.post(
        f"/internal/worker/runs/{run['id']}/result",
        headers=headers,
        json={
            "lease_token": job["lease_token"],
            "status": "completed",
            "result": {"status": "completed", "apk_sha256": "0" * 64},
        },
    )
    assert response.status_code == 422
    assert "SHA-256" in response.json()["detail"]



def test_expired_worker_lease_is_reclaimed_and_old_token_is_rejected(monkeypatch, tmp_path):
    client = prepare_isolated_db(monkeypatch, tmp_path)
    headers = {"X-BharatSim-Worker-Token": os.environ["BHARATSIM_WORKER_TOKEN"]}
    created = client.post(
        "/api/v1/runs",
        data={"persona_id": "baseline"},
        files={"apk": ("retry.apk", apk_bytes(), "application/vnd.android.package-archive")},
    )
    run_id = created.json()["id"]

    first = client.post(
        "/internal/worker/claim", headers=headers, json={"worker_id": "worker-before-crash"}
    ).json()["job"]
    with main.db() as conn:
        conn.execute(
            "UPDATE runs SET lease_until=? WHERE id=?",
            ("2000-01-01T00:00:00+00:00", run_id),
        )

    second = client.post(
        "/internal/worker/claim", headers=headers, json={"worker_id": "worker-after-restart"}
    ).json()["job"]
    assert second["id"] == run_id
    assert second["attempt"] == 2
    assert second["lease_token"] != first["lease_token"]

    stale_download = client.get(
        f"/internal/worker/runs/{run_id}/apk",
        headers={**headers, "X-BharatSim-Lease-Token": first["lease_token"]},
    )
    assert stale_download.status_code == 409

    stale_result = client.post(
        f"/internal/worker/runs/{run_id}/result",
        headers=headers,
        json={
            "lease_token": first["lease_token"],
            "status": "failed",
            "result": {"status": "failed", "error": "late old-worker callback"},
            "error": "late old-worker callback",
        },
    )
    assert stale_result.status_code == 409
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "leased"


def test_run_fails_closed_after_three_expired_worker_leases(monkeypatch, tmp_path):
    client = prepare_isolated_db(monkeypatch, tmp_path)
    headers = {"X-BharatSim-Worker-Token": os.environ["BHARATSIM_WORKER_TOKEN"]}
    created = client.post(
        "/api/v1/runs",
        data={"persona_id": "baseline"},
        files={("apk"): ("never-finishes.apk", apk_bytes(), "application/vnd.android.package-archive")},
    )
    run_id = created.json()["id"]

    for attempt in range(1, 4):
        claimed = client.post(
            "/internal/worker/claim", headers=headers, json={"worker_id": f"worker-{attempt}"}
        ).json()["job"]
        assert claimed["attempt"] == attempt
        with main.db() as conn:
            conn.execute(
                "UPDATE runs SET lease_until=? WHERE id=?",
                ("2000-01-01T00:00:00+00:00", run_id),
            )

    # A further claim performs expiry maintenance, marks exhausted work failed,
    # and must not hand the abandoned run to a fourth worker attempt.
    response = client.post(
        "/internal/worker/claim", headers=headers, json={"worker_id": "worker-4"}
    )
    assert response.status_code == 200
    assert response.json()["job"] is None
    final = client.get(f"/api/v1/runs/{run_id}").json()
    assert final["status"] == "failed"
    assert final["error"] == "Worker lease expired after maximum attempts"
