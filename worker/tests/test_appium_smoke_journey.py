import unittest
from unittest.mock import patch

from worker.tests import appium_smoke_journey as journey


class SupportedRoutePreflightTests(unittest.TestCase):
    def _fake_adb(self, connectivity):
        def run(*args, **kwargs):
            command = tuple(args)
            if command == ("shell", "ip", "route", "show", "table", "all"):
                return "default via 10.0.2.2 dev rmnet_data0"
            if command == ("shell", "ip", "-6", "route", "show", "table", "all"):
                return ""
            if command == ("shell", "ip", "rule", "show"):
                return "0: from all lookup local"
            if command == ("shell", "dumpsys", "connectivity"):
                return connectivity
            if command == ("emu", "gsm", "status"):
                return "gsm voice state: home\ngsm data state: home"
            return ""
        return run

    def test_preflight_accepts_active_cellular_network(self):
        with patch.object(
            journey, "adb",
            side_effect=self._fake_adb("Cellular active networks: {100}"),
        ) as adb_call, patch.object(journey.time, "sleep"):
            journey.prepare_supported_transport()
        self.assertTrue(any(call.args[:3] == ("shell", "dumpsys", "connectivity") for call in adb_call.call_args_list))
        self.assertTrue(any(call.args[:3] == ("shell", "cmd", "connectivity") for call in adb_call.call_args_list))

    def test_preflight_accepts_active_ethernet_network(self):
        with patch.object(
            journey, "adb",
            side_effect=self._fake_adb("Ethernet active networks: {101}"),
        ):
            journey.prepare_supported_transport()

    def test_preflight_rejects_wifi_only(self):
        self.assertFalse(journey.has_supported_active_transport(
            "WiFi active networks: {100}\nCellular active networks: {}\nEthernet active networks: {}"
        ))

    def test_preflight_fails_with_diagnostics_when_no_supported_network_exists(self):
        with (
            patch.object(
                journey, "adb",
                side_effect=self._fake_adb(
                    "WiFi active networks: {100}\nCellular active networks: {}\nEthernet active networks: {}"
                ),
            ),
            patch.object(journey.time, "sleep"),
            patch.object(journey.time, "monotonic", side_effect=[0, *range(0, 32)]),
        ):
            with self.assertRaisesRegex(RuntimeError, "no active supported cellular/Ethernet network") as error:
                journey.prepare_supported_transport()
        self.assertIn("IPv4 routes=", str(error.exception))
        self.assertIn("connectivity=", str(error.exception))


class ProbeExecutionEngine:
    """Exact behavioral model of Android MainActivity.java probe retry and deadline logic."""
    PROBE_TIMEOUT_MS = 45_000
    ATTEMPT_TIMEOUT_MS = 20_000
    SOCKET_READ_TIMEOUT_MS = 10_000

    def __init__(self):
        self.current_time_ms = 0
        self.log_messages = []

    def remaining_timeout_ms(self, attempt_deadline, probe_deadline):
        now = self.current_time_ms
        overall_remaining = probe_deadline - now
        if overall_remaining <= 0:
            raise TimeoutError("Android HTTPS probe exceeded its 45-second overall deadline")
        attempt_remaining = attempt_deadline - now
        if attempt_remaining <= 0:
            raise TimeoutError("Probe attempt exceeded its 20-second deadline")
        return max(1, min(self.SOCKET_READ_TIMEOUT_MS, min(attempt_remaining, overall_remaining)))

    def execute_probe(self, socket_reader, sequence=1, transport="CELLULAR"):
        probe_deadline = self.current_time_ms + self.PROBE_TIMEOUT_MS
        for attempt in (1, 2):
            started = self.current_time_ms
            now = self.current_time_ms
            remaining_overall = probe_deadline - now
            if remaining_overall <= 0:
                msg = f"Android HTTPS probe exceeded its {self.PROBE_TIMEOUT_MS // 1000}-second overall deadline"
                self.log_messages.append(f"BHARATSIM_NETWORK_PROBE status=ERROR transport={transport} probe={sequence} attempts={attempt-1}")
                return {
                    "status": "ERROR",
                    "transport": transport,
                    "probe": sequence,
                    "attempts": attempt - 1,
                    "error": "SocketTimeoutException",
                    "message": msg,
                    "ui_text": f"Network probe failed: SocketTimeoutException · {msg}",
                }
            attempt_budget = (
                min(self.ATTEMPT_TIMEOUT_MS, max(1000, remaining_overall - 2000))
                if attempt < 2
                else min(self.ATTEMPT_TIMEOUT_MS, remaining_overall)
            )
            attempt_deadline = now + attempt_budget
            try:
                bytes_read = socket_reader(self, attempt, attempt_deadline, probe_deadline)
                duration = self.current_time_ms - started
                self.log_messages.append(
                    f"BHARATSIM_NETWORK_PROBE status=HTTP_200 duration_ms={duration} transport={transport} probe={sequence} bytes_read={bytes_read} attempts={attempt}"
                )
                ui_text = f"HTTP 200 · {duration} ms · {transport} · probe {sequence} · bytes {bytes_read} · attempts {attempt}"
                return {
                    "status": "HTTP_200",
                    "duration_ms": duration,
                    "transport": transport,
                    "probe": sequence,
                    "bytes_read": bytes_read,
                    "attempts": attempt,
                    "ui_text": ui_text,
                }
            except Exception as exc:
                now_after_catch = self.current_time_ms
                if isinstance(exc, (OSError, TimeoutError)) and attempt < 2 and now_after_catch < (probe_deadline - 1000):
                    self.log_messages.append(
                        f"BHARATSIM_NETWORK_PROBE retrying sequence={sequence} attempt={attempt} after={exc.__class__.__name__} message=\"{exc}\""
                    )
                    self.current_time_ms += attempt * 1000
                    continue
                duration = self.current_time_ms - started
                self.log_messages.append(
                    f"BHARATSIM_NETWORK_PROBE status=ERROR transport={transport} probe={sequence} attempts={attempt}"
                )
                err_cls = "SocketTimeoutException" if isinstance(exc, TimeoutError) else exc.__class__.__name__
                msg = str(exc)
                ui_text = f"Network probe failed: {err_cls} · {msg}"
                return {
                    "status": "ERROR",
                    "transport": transport,
                    "probe": sequence,
                    "attempts": attempt,
                    "error": err_cls,
                    "message": msg,
                    "ui_text": ui_text,
                }
        return {"status": "ERROR", "attempts": 2}


class ProbeRetryAndDeadlineDeterministicTests(unittest.TestCase):
    def test_complete_socket_stall(self):
        engine = ProbeExecutionEngine()

        def stall_reader(eng, attempt, attempt_deadline, probe_deadline):
            timeout = eng.remaining_timeout_ms(attempt_deadline, probe_deadline)
            self.assertEqual(timeout, engine.SOCKET_READ_TIMEOUT_MS)
            eng.current_time_ms += timeout
            raise TimeoutError("Read timed out")

        result = engine.execute_probe(stall_reader, sequence=5)
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["error"], "SocketTimeoutException")
        self.assertIn("Read timed out", result["message"])
        self.assertEqual(result["ui_text"], "Network probe failed: SocketTimeoutException · Read timed out")
        self.assertTrue(any("retrying sequence=5 attempt=1" in msg for msg in engine.log_messages))

    def test_slow_trickle_never_completes(self):
        engine = ProbeExecutionEngine()
        attempts_seen = []

        def trickle_reader(eng, attempt, attempt_deadline, probe_deadline):
            attempts_seen.append(attempt)
            total = 0
            while total < 500_000:
                eng.remaining_timeout_ms(attempt_deadline, probe_deadline)
                eng.current_time_ms += 1000
                total += 100
            return total

        result = engine.execute_probe(trickle_reader, sequence=5)
        self.assertEqual(attempts_seen, [1, 2])
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["attempts"], 2)
        self.assertIn("20-second deadline", result["message"])
        self.assertTrue(any("retrying sequence=5 attempt=1" in msg for msg in engine.log_messages))

    def test_timeout_followed_by_successful_retry(self):
        engine = ProbeExecutionEngine()

        def recover_on_second_attempt(eng, attempt, attempt_deadline, probe_deadline):
            if attempt == 1:
                eng.remaining_timeout_ms(attempt_deadline, probe_deadline)
                eng.current_time_ms += 20_000
                raise TimeoutError("Probe attempt exceeded its 20-second deadline")
            eng.current_time_ms += 1200
            return 500_000

        result = engine.execute_probe(recover_on_second_attempt, sequence=5)
        self.assertEqual(result["status"], "HTTP_200")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["bytes_read"], 500_000)
        self.assertIn("attempts 2", result["ui_text"])

        parsed = journey.parse_probe_text(result["ui_text"])
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["http_status"], 200)
        self.assertEqual(parsed["attempts"], 2)
        self.assertEqual(parsed["sequence"], 5)
        self.assertEqual(parsed["bytes_read"], 500_000)

    def test_overall_deadline_exhaustion(self):
        engine = ProbeExecutionEngine()

        def exhausted_reader(eng, attempt, attempt_deadline, probe_deadline):
            eng.current_time_ms = 46_000
            eng.remaining_timeout_ms(attempt_deadline, probe_deadline)
            return 500_000

        result = engine.execute_probe(exhausted_reader, sequence=5)
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("45-second overall deadline", result["message"])

    def test_correct_failure_reporting_after_retries(self):
        engine = ProbeExecutionEngine()

        def permanent_failure(eng, attempt, attempt_deadline, probe_deadline):
            eng.current_time_ms += 5000
            raise OSError("Connection reset by peer")

        result = engine.execute_probe(permanent_failure, sequence=7)
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["error"], "OSError")
        self.assertIn("Connection reset by peer", result["message"])
        self.assertEqual(
            result["ui_text"],
            "Network probe failed: OSError · Connection reset by peer",
        )
        self.assertIsNone(journey.parse_probe_text(result["ui_text"]))


if __name__ == "__main__":
    unittest.main()
