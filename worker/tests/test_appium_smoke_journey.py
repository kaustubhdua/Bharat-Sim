import unittest
from pathlib import Path
from unittest.mock import patch

from worker.tests import appium_smoke_journey as journey


class AndroidProbeTimeoutContractTests(unittest.TestCase):
    def test_fixture_has_a_bounded_90_second_overall_deadline(self):
        source = (Path(__file__).resolve().parents[2] / "smoke-android/app/src/main/java/org/bharatsim/smokeapp/MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("PROBE_TIMEOUT_MS = 90_000", source)
        self.assertIn("exceeded its 90-second overall deadline", source)


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
        self.assertTrue(any(call.args[:4] == ("shell", "svc", "data", "enable") for call in adb_call.call_args_list))

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


if __name__ == "__main__":
    unittest.main()
