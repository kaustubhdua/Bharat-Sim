import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from worker.runner import (
    apply_emulator_network_profile,
    extract_logcat_signals,
    parse_emulator_network_status,
    parse_fixture_network_probe,
    reset_emulator_network_profile,
    run_adb_with_retry,
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






class AdbRetryTests(unittest.TestCase):
    def test_retries_logcat_after_transient_device_offline_and_keeps_complete_result(self):
        offline = CompletedProcess(args=[], returncode=255, stdout="partial log", stderr="")
        wait_ok = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        state_ok = CompletedProcess(args=[], returncode=0, stdout="device\n", stderr="")
        recovered = CompletedProcess(args=[], returncode=0, stdout="complete log", stderr="")
        with patch("worker.runner.run_cmd", side_effect=[offline, wait_ok, state_ok, recovered]) as run:
            result = run_adb_with_retry("emulator-5554", ["logcat", "-d"], timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "complete log")
        self.assertEqual(run.call_count, 4)
        self.assertEqual(run.call_args_list[1].args[0][-1], "wait-for-device")

    def test_does_not_turn_persistent_adb_failure_into_success(self):
        offline = CompletedProcess(args=[], returncode=255, stdout="", stderr="device offline")
        wait_ok = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        state_offline = CompletedProcess(args=[], returncode=1, stdout="", stderr="device offline")
        with patch("worker.runner.run_cmd", side_effect=[
            offline, wait_ok, state_offline, offline, wait_ok, state_offline, offline
        ]):
            result = run_adb_with_retry("emulator-5554", ["uninstall", "org.example.app"], attempts=3)
        self.assertEqual(result.returncode, 255)
        self.assertIn("device offline", result.stderr)



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





class StructuredLogcatSignalTests(unittest.TestCase):
    def test_extracts_real_marker_lines_with_bounded_context(self):
        logs = """01-01 00:00:00.000 I App: startup
01-01 00:00:01.000 E AndroidRuntime: FATAL EXCEPTION: main
01-01 00:00:01.001 E AndroidRuntime: java.lang.OutOfMemoryError: Failed allocation
01-01 00:00:02.000 E ActivityManager: ANR in com.example.app
01-01 00:00:03.000 W Network: java.net.SocketTimeoutException: timeout
01-01 00:00:04.000 E Storage: No space left on device
"""
        signals = extract_logcat_signals(logs)
        categories = [item["category"] for item in signals]
        self.assertEqual(categories, ["crash", "oom", "anr", "network", "storage"])
        self.assertEqual(signals[0]["line_number"], 2)
        self.assertIn("FATAL EXCEPTION", signals[0]["marker"])
        self.assertTrue(all(item["evidence"] for item in signals))
        self.assertTrue(all(len(line["text"]) <= 400 for item in signals for line in item["evidence"]))

    def test_caps_signal_count_to_prevent_unbounded_inline_reports(self):
        logs = "\n".join(
            f"line {index}: java.net.SocketTimeoutException: timeout"
            for index in range(40)
        )
        signals = extract_logcat_signals(logs, max_signals=500)
        self.assertEqual(len(signals), 20)
        self.assertEqual(signals[-1]["line_number"], 20)

    def test_clean_logs_return_no_synthetic_findings(self):
        self.assertEqual(extract_logcat_signals("Activity started\\nUI rendered\\n"), [])


if __name__ == "__main__":
    unittest.main()
