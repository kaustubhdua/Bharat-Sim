import unittest
import urllib.request

from worker.agent import NoRedirectHandler, WorkerError, annotate_execution_scope, persona_network_cli_args, redact_report_text, redact_sensitive_text, resolve_api_url


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


if __name__ == "__main__":
    unittest.main()
