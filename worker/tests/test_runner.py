import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from worker.runner import (
    apply_emulator_network_profile,
    parse_emulator_network_status,
    parse_fixture_network_probe,
    reset_emulator_network_profile,
    valid_package_name,
)


class PackageNameValidationTests(unittest.TestCase):
    def test_accepts_android_style_package_names(self):
        for value in ("com.example.app", "org.example_2.client", "a.b", "com.Example.App"):
            with self.subTest(value=value):
                self.assertTrue(valid_package_name(value))

    def test_rejects_shell_metacharacters_and_malformed_names(self):
        for value in (
            "com.example;id",
            "com.example$(id)",
            "com.example && reboot",
            "com.example app",
            "com",
            ".example.app",
            "com..app",
            "com.example/",
            "",
        ):
            with self.subTest(value=value):
                self.assertFalse(valid_package_name(value))





class EmulatorNetworkProfileTests(unittest.TestCase):
    STATUS = """Current network status:
 download speed: 1200000 bits/s (146.5 KB/s)
 upload speed: 350000 bits/s (42.7 KB/s)
 minimum latency: 180 ms
 maximum latency: 180 ms
 OK
"""

    def test_parse_status_readback(self):
        self.assertEqual(
            parse_emulator_network_status(self.STATUS),
            {
                "download_bps": 1200000,
                "upload_bps": 350000,
                "minimum_latency_ms": 180,
                "maximum_latency_ms": 180,
            },
        )
        self.assertIsNone(parse_emulator_network_status("OK\\nKO: invalid command"))

    def test_applies_and_verifies_emulator_control_plane_without_overclaiming_traffic_path(self):
        ok = CompletedProcess(args=[], returncode=0, stdout="OK\\n", stderr="")
        status = CompletedProcess(args=[], returncode=0, stdout=self.STATUS, stderr="")
        with patch("worker.runner.run_cmd", side_effect=[ok, ok, status]) as run:
            evidence = apply_emulator_network_profile("emulator-5554", 180, 1200, 350, 2.0)
        self.assertEqual(evidence["control_plane"]["status"], "verified")
        self.assertTrue(evidence["network_constraints_applied"])
        self.assertFalse(evidence["traffic_path_verified"])
        self.assertIn("packet_loss", evidence["unsupported_controls"])
        self.assertIn("ram_pressure", evidence["unsupported_controls"])
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[0].args[0][-1], "180")
        self.assertEqual(run.call_args_list[1].args[0][-1], "350:1200")

    def test_parse_fixture_probe_from_filtered_logcat(self):
        evidence = parse_fixture_network_probe(
            "06-01 10:00:00.000 I BharatSimNetworkProbe: "
            "BHARATSIM_NETWORK_PROBE status=HTTP_200 duration_ms=91 transport=CELLULAR"
        )
        self.assertEqual(
            evidence,
            {"http_status": 200, "duration_ms": 91, "transport": "CELLULAR"},
        )

    def test_refuses_to_claim_emulator_controls_for_physical_device(self):
        with patch("worker.runner.run_cmd") as run:
            evidence = apply_emulator_network_profile("R58M123ABC", 180, 1200, 350, 0)
        self.assertEqual(evidence["control_plane"]["status"], "unsupported")
        self.assertFalse(evidence.get("network_constraints_applied", False))
        run.assert_not_called()

    def test_reset_requires_verified_default_readback(self):
        ok = CompletedProcess(args=[], returncode=0, stdout="OK\\n", stderr="")
        status = CompletedProcess(
            args=[], returncode=0,
            stdout="""Current network status:
 download speed: 0 bits/s (0.0 KB/s)
 upload speed: 0 bits/s (0.0 KB/s)
 minimum latency: 0 ms
 maximum latency: 0 ms
 OK
""", stderr=""
        )
        with patch("worker.runner.run_cmd", side_effect=[ok, ok, status]):
            evidence = reset_emulator_network_profile("emulator-5554")
        self.assertEqual(evidence["status"], "verified")




if __name__ == "__main__":
    unittest.main()
