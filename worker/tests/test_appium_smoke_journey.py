import unittest
from unittest.mock import call, patch

from worker.tests import appium_smoke_journey as journey


class ProbeParsingTests(unittest.TestCase):
    def test_sample_summary_reports_count_median_and_spread(self):
        summary = journey.summarize_samples([
            {"duration_ms": 100},
            {"duration_ms": 150},
            {"duration_ms": 220},
        ])
        self.assertEqual(summary, {
            "sample_count": 3,
            "successful_samples": 3,
            "failed_samples": 0,
            "min_ms": 100,
            "max_ms": 220,
            "spread_ms": 120,
            "median_ms": 150,
        })

    def test_parses_successful_probe_status(self):
        parsed = journey.parse_probe_text(
            "HTTP 206 · 347 ms · CELLULAR · probe 3 · bytes 64000 · attempts 2"
        )
        self.assertEqual(parsed, {
            "http_status": 206,
            "duration_ms": 347,
            "transport": "CELLULAR",
            "sequence": 3,
            "bytes_read": 64000,
            "attempts": 2,
        })

    def test_rejects_incomplete_or_failed_probe_status(self):
        self.assertIsNone(journey.parse_probe_text("Network probe running"))
        self.assertIsNone(journey.parse_probe_text("Network probe failed: SocketTimeoutException"))


class ProxyPathTests(unittest.TestCase):
    def test_preflight_enables_network_and_requires_healthy_proxy(self):
        with (
            patch.object(journey, "adb", return_value="Cellular active networks: {100}") as adb,
            patch.object(journey, "proxy_request", return_value={"status": "ok"}) as proxy,
        ):
            evidence = journey.prepare_proxy_path()

        self.assertEqual(evidence["status"], "ready")
        self.assertTrue(evidence["active_transport_network_present"])
        self.assertEqual(evidence["proxy_health"], {"status": "ok"})
        adb.assert_has_calls([
            call("shell", "settings", "put", "global", "airplane_mode_on", "0"),
            call("shell", "cmd", "connectivity", "airplane-mode", "disable"),
            call("shell", "svc", "wifi", "enable"),
            call("shell", "svc", "data", "enable"),
            call("shell", "dumpsys", "connectivity", timeout=8),
        ])
        proxy.assert_called_once_with("GET", "/health")

    def test_preflight_fails_if_no_android_network_is_active(self):
        with (
            patch.object(journey, "adb", return_value="WiFi active networks: {}"),
            patch.object(journey, "proxy_request") as proxy,
            patch.object(journey.time, "monotonic", side_effect=[0, 61]),
            patch.object(journey.time, "sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "no active network"):
                journey.prepare_proxy_path()
        proxy.assert_not_called()

    def test_preflight_rejects_unhealthy_proxy(self):
        with (
            patch.object(journey, "adb", return_value="Ethernet active networks: {101}"),
            patch.object(journey, "proxy_request", return_value={"status": "starting"}),
        ):
            with self.assertRaisesRegex(RuntimeError, "not healthy"):
                journey.prepare_proxy_path()

    def test_profile_readback_must_match_requested_values(self):
        config = {
            "generation": 4,
            "label": "latency-only",
            "delay_ms": 150,
            "rate_kbps": 0,
        }
        with patch.object(
            journey, "proxy_request",
            return_value={"status": "ok", "config": config},
        ) as request:
            self.assertEqual(journey.set_proxy_profile("latency-only", 150, 0), config)
        request.assert_called_once_with("POST", "/config", {
            "label": "latency-only",
            "delay_ms": 150,
            "rate_kbps": 0,
        })

    def test_profile_readback_mismatch_fails_closed(self):
        with patch.object(
            journey, "proxy_request",
            return_value={"status": "ok", "config": {
                "generation": 4, "label": "latency-only",
                "delay_ms": 50, "rate_kbps": 0,
            }},
        ):
            with self.assertRaisesRegex(RuntimeError, "readback mismatch"):
                journey.set_proxy_profile("latency-only", 150, 0)

    def test_wait_for_proxy_event_requires_allowlisted_host_ip_generation_and_bytes(self):
        event = {
            "id": 9,
            "host": "raw.githubusercontent.com",
            "port": 443,
            "generation": 7,
            "status": "completed",
            "upstream_ip": "192.0.2.10",
            "bytes_upstream_to_client": journey.PROBE_BYTES,
        }
        with (
            patch.object(journey, "EXPECTED_HOST", "raw.githubusercontent.com"),
            patch.object(journey, "EXPECTED_IP", "192.0.2.10"),
            patch.object(journey, "proxy_metrics", return_value={
                "last_event_id": 9, "events": [event],
            }) as metrics,
        ):
            result = journey.wait_for_proxy_event(after_id=8, generation=7)
        self.assertEqual(result, event)
        metrics.assert_called_once_with(8)

    def test_proxy_event_with_unexpected_upstream_ip_is_rejected(self):
        event = {
            "id": 9,
            "host": "raw.githubusercontent.com",
            "port": 443,
            "generation": 7,
            "status": "completed",
            "upstream_ip": "198.51.100.20",
            "bytes_upstream_to_client": journey.PROBE_BYTES,
        }
        with (
            patch.object(journey, "EXPECTED_HOST", "raw.githubusercontent.com"),
            patch.object(journey, "EXPECTED_IP", "192.0.2.10"),
            patch.object(journey, "proxy_metrics", return_value={
                "last_event_id": 9, "events": [event],
            }),
        ):
            with self.assertRaisesRegex(RuntimeError, "unexpected upstream IP"):
                journey.wait_for_proxy_event(after_id=8, generation=7)

    def test_reset_is_verified_only_after_baseline_readback(self):
        with patch.object(
            journey, "proxy_request",
            side_effect=[
                {"status": "ok"},
                {"status": "ok", "config": {
                    "label": "baseline", "delay_ms": 0, "rate_kbps": 0,
                }},
            ],
        ) as request:
            result = journey.reset_proxy()
        self.assertEqual(result["status"], "verified")
        self.assertEqual(request.call_args_list, [
            call("POST", "/reset"),
            call("GET", "/health"),
        ])

    def test_reset_readback_mismatch_is_unverified(self):
        with patch.object(
            journey, "proxy_request",
            side_effect=[
                {"status": "ok"},
                {"status": "ok", "config": {
                    "label": "latency-only", "delay_ms": 150, "rate_kbps": 0,
                }},
            ],
        ):
            result = journey.reset_proxy()
        self.assertEqual(result["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
