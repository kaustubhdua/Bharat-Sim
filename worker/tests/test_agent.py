import os
import subprocess
import sys
import unittest
import urllib.request
from pathlib import Path

from worker.agent import NoRedirectHandler, WorkerError, annotate_execution_scope, persona_network_cli_args, redact_report_text, redact_sensitive_text, resolve_api_url


class AgentEntrypointTests(unittest.TestCase):
    def test_documented_direct_script_entrypoint_imports_package(self):
        root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        for key in ("BHARATSIM_API_URL", "BHARATSIM_WORKER_TOKEN", "ANDROID_SERIAL",
                    "BHARATSIM_ENABLE_LOCAL_APK_EXECUTION", "BHARATSIM_ALLOW_INSECURE_HTTP"):
            env.pop(key, None)
        completed = subprocess.run(
            [sys.executable, "worker/agent.py"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("BHARATSIM_API_URL", completed.stderr)
        self.assertNotIn("ModuleNotFoundError", completed.stderr)


class ExecutionScopeTruthfulnessTests(unittest.TestCase):
    def test_smoke_completion_is_not_an_app_health_pass(self):
        report = {"status": "completed"}
        annotate_execution_scope(report, {"persona_id": "edge-village"})
        self.assertEqual(report["execution_scope"], "install_launch_logcat_smoke")
        self.assertEqual(report["requested_persona_id"], "edge-village")
        self.assertFalse(report["constraints_applied"])
        self.assertEqual(report["constraint_verification"], "unsupported_not_applied")
        self.assertIn("does not prove the app is healthy", report["result_interpretation"])

    def test_verified_network_control_remains_partial_and_does_not_claim_app_path(self):
        report = {
            "status": "completed",
            "network_profile": {
                "control_plane": {"status": "verified"},
                "network_constraints_applied": True,
                "traffic_path_verified": False,
            },
        }
        annotate_execution_scope(report, {"persona_id": "baseline"})
        self.assertFalse(report["constraints_applied"])
        self.assertTrue(report["network_constraints_applied"])
        self.assertIn("active app traffic path", report["constraint_verification"])
        self.assertIn("not proven", report["result_interpretation"])

    def test_missing_persona_is_not_invented(self):
        report = {}
        annotate_execution_scope(report, {})
        self.assertEqual(report["requested_persona_id"], "unknown")
        self.assertFalse(report["constraints_applied"])


class WorkerRedirectSecurityTests(unittest.TestCase):
    def test_credential_bearing_requests_are_not_redirected(self):
        handler = NoRedirectHandler()
        request = urllib.request.Request("https://bharatsim.example/internal/worker/claim")
        redirected = handler.redirect_request(
            request, None, 302, "Found", {"Location": "https://attacker.example/steal"}, 
            "https://attacker.example/steal",
        )
        self.assertIsNone(redirected)


class WorkerApiUrlSecurityTests(unittest.TestCase):
    def test_accepts_internal_relative_worker_paths(self):
        self.assertEqual(
            resolve_api_url("https://api.example/base", "/internal/worker/claim"),
            "https://api.example/internal/worker/claim",
        )

    def test_rejects_absolute_external_urls(self):
        for path in (
            "https://attacker.example/internal/worker/claim",
            "//attacker.example/internal/worker/claim",
            "http://api.example/internal/worker/claim",
            "https://user:pass@api.example/internal/worker/claim",
        ):
            with self.subTest(path=path), self.assertRaises(WorkerError):
                resolve_api_url("https://api.example", path)

    def test_rejects_non_worker_routes_and_fragments(self):
        for path in ("/api/v1/runs", "/internal/admin/secrets", "/internal/worker/claim#fragment"):
            with self.subTest(path=path), self.assertRaises(WorkerError):
                resolve_api_url("https://api.example", path)



class PersonaNetworkArgumentTests(unittest.TestCase):
    def test_translates_persona_targets_to_runner_arguments(self):
        args = persona_network_cli_args({
            "persona_id": "edge-village",
            "persona_profile": {
                "latency_ms": 450,
                "down_kbps": 256,
                "up_kbps": 96,
                "packet_loss_pct": 8,
            },
        })
        self.assertEqual(args, [
            "--network-latency-ms", "450",
            "--network-down-kbps", "256",
            "--network-up-kbps", "96",
            "--network-loss-pct", "8.0",
        ])

    def test_missing_profile_preserves_legacy_job_compatibility(self):
        self.assertEqual(persona_network_cli_args({"persona_id": "legacy"}), [])
        self.assertEqual(persona_network_cli_args({"persona_profile": {}}), [])

    def test_rejects_invalid_or_out_of_range_network_targets(self):
        invalid_profiles = [
            {"latency_ms": 2001, "down_kbps": 1000, "up_kbps": 1000, "packet_loss_pct": 0},
            {"latency_ms": 10, "down_kbps": 0, "up_kbps": 1000, "packet_loss_pct": 0},
            {"latency_ms": 10, "down_kbps": 1000, "up_kbps": 1000, "packet_loss_pct": 101},
            {"latency_ms": "invalid", "down_kbps": 1000, "up_kbps": 1000, "packet_loss_pct": 0},
        ]
        for profile in invalid_profiles:
            with self.subTest(profile=profile), self.assertRaises(WorkerError):
                persona_network_cli_args({"persona_profile": profile})

    def test_rejects_non_object_profile(self):
        with self.assertRaises(WorkerError):
            persona_network_cli_args({"persona_profile": "edge-village"})


class WorkerEvidenceRedactionTests(unittest.TestCase):
    def test_redacts_bearer_password_query_token_and_jwt_patterns(self):
        text = (
            "Authorization: Bearer abc.def.secret "
            "password=hunter2 "
            "GET /callback?access_token=topsecret "
            "jwt=eyJabcdefghijk.abcdefghijk.abcdefghijk"
        )
        redacted = redact_sensitive_text(text)
        for secret in ("abc.def.secret", "hunter2", "topsecret", "eyJabcdefghijk.abcdefghijk.abcdefghijk"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED"), 4)

    def test_redacts_nested_report_strings_without_mutating_evidence_types(self):
        report = {
            "logcat_tail": 'request {"api_key":"key-value-secret"}',
            "steps": [{"stderr_tail": "refresh_token=refresh-secret", "return_code": 0}],
            "constraints_applied": False,
        }
        cleaned = redact_report_text(report)
        self.assertNotIn("key-value-secret", str(cleaned))
        self.assertNotIn("refresh-secret", str(cleaned))
        self.assertIs(cleaned["constraints_applied"], False)
        self.assertEqual(cleaned["steps"][0]["return_code"], 0)


class AgentPersonaPassingAndTimeoutTests(unittest.TestCase):
    def test_complete_persona_information_reaches_runner(self):
        import json
        import subprocess
        from pathlib import Path
        from unittest.mock import MagicMock, patch
        from worker.agent import run_job

        job = {
            "id": "run-123",
            "lease_token": "a" * 32,
            "apk_sha256": "0" * 64,
            "heartbeat_url": "/internal/worker/runs/run-123/heartbeat",
            "result_url": "/internal/worker/runs/run-123/result",
            "persona_id": "budget-android",
            "persona_profile": {
                "id": "budget-android",
                "latency_ms": 180,
                "down_kbps": 1200,
                "up_kbps": 350,
                "packet_loss_pct": 2.0,
                "battery_saver": True,
                "storage_free_mb": 600,
                "ram_mb": 2048,
            },
        }

        captured_command = []
        captured_profile_content = []

        def mock_subprocess_run(cmd, **kwargs):
            captured_command.extend(cmd)
            if "--persona-profile" in cmd:
                p_idx = cmd.index("--persona-profile") + 1
                p_file = Path(cmd[p_idx])
                if p_file.is_file():
                    captured_profile_content.append(json.loads(p_file.read_text(encoding="utf-8")))

            # Create a mock report in artifacts dir
            out_idx = cmd.index("--out") + 1
            out_dir = Path(cmd[out_idx])
            out_dir.mkdir(parents=True, exist_ok=True)
            report_file = out_dir / "test.report.json"
            report_file.write_text(
                json.dumps({
                    "status": "completed",
                    "network_profile": {"control_plane": {"status": "verified"}, "network_constraints_applied": True},
                    "condition_evidence": {
                        "persona_id": "budget-android",
                        "overall_status": "applied_and_verified",
                        "traffic_path_verified": False,
                    },
                }),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        mock_request = MagicMock(return_value={"ok": True})

        with patch("worker.agent.download_apk"), \
             patch("worker.agent.request_json", mock_request), \
             patch("subprocess.run", side_effect=mock_subprocess_run):
            run_job("https://api.example", "t" * 32, "emulator-5554", job, duration=10)

        # 1. Verify --persona-profile passed
        self.assertIn("--persona-profile", captured_command)
        self.assertEqual(len(captured_profile_content), 1)
        passed_data = captured_profile_content[0]
        self.assertEqual(passed_data["id"], "budget-android")
        self.assertEqual(passed_data["battery_saver"], True)
        self.assertEqual(passed_data["storage_free_mb"], 600)

        # 2. Verify existing network arguments are preserved
        self.assertIn("--network-latency-ms", captured_command)
        self.assertIn("--network-down-kbps", captured_command)
        self.assertIn("--network-up-kbps", captured_command)
        self.assertIn("--network-loss-pct", captured_command)

        # 3. Verify condition_evidence survives result submission
        result_call = [call for call in mock_request.call_args_list if call.args[2] == job["result_url"]][0]
        submitted_payload = result_call.args[3]
        self.assertEqual(submitted_payload["status"], "completed")
        self.assertIn("condition_evidence", submitted_payload["result"])
        self.assertEqual(submitted_payload["result"]["condition_evidence"]["persona_id"], "budget-android")
        self.assertFalse(submitted_payload["result"]["condition_evidence"]["traffic_path_verified"])

    def test_runner_timeout_triggers_safe_cleanup_fallback(self):
        import subprocess
        from unittest.mock import MagicMock, patch
        from worker.agent import run_job

        job = {
            "id": "run-timeout-1",
            "lease_token": "b" * 32,
            "apk_sha256": "1" * 64,
            "heartbeat_url": "/internal/worker/runs/run-timeout-1/heartbeat",
            "result_url": "/internal/worker/runs/run-timeout-1/result",
            "persona_id": "edge-village",
            "persona_profile": {"id": "edge-village", "latency_ms": 450, "down_kbps": 256, "up_kbps": 96},
        }

        mock_reset = MagicMock(return_value={"status": "verified"})
        mock_request = MagicMock(return_value={"ok": True})

        def mock_subprocess_timeout(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=360)

        with patch("worker.agent.download_apk"), \
             patch("worker.agent.request_json", mock_request), \
             patch("worker.agent.reset_target_safely", mock_reset), \
             patch("subprocess.run", side_effect=mock_subprocess_timeout):
            run_job("https://api.example", "t" * 32, "emulator-5554", job, duration=10)

        # Verify fallback reset was called
        mock_reset.assert_called_with("emulator-5554")

        # Verify submission sent failed status
        result_call = [call for call in mock_request.call_args_list if call.args[2] == job["result_url"]][0]
        submitted_payload = result_call.args[3]
        self.assertEqual(submitted_payload["status"], "failed")
        self.assertIn("timed out", submitted_payload["error"])


if __name__ == "__main__":
    unittest.main()
