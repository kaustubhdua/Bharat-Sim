import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker import emulator_lifecycle as lifecycle


class FakeProcess:
    pid = 4321
    returncode = None

    def __init__(self):
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def kill(self):
        self.killed = True
        self.returncode = -9


def completed(args, stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class EmulatorSerialValidationTests(unittest.TestCase):
    def test_accepts_even_emulator_console_ports(self):
        self.assertEqual(lifecycle.parse_emulator_port("emulator-5554"), 5554)
        self.assertEqual(lifecycle.parse_emulator_port("emulator-5560"), 5560)

    def test_rejects_non_emulator_and_invalid_ports(self):
        for serial in ("127.0.0.1:5555", "emulator-5555", "emulator-9999", "emulator-55", ""):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                lifecycle.parse_emulator_port(serial)


class EmulatorRecycleTests(unittest.TestCase):
    def test_recycle_kills_old_device_and_starts_wiped_avd_on_same_port(self):
        fake_process = FakeProcess()
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "emulator.log"

            def fake_run(args, timeout=10):
                args = list(args)
                calls.append(args)
                if args == ["/fake/android/emulator", "-list-avds"]:
                    return completed(args, "bharatsim-api35\n")
                if args == ["adb", "devices"]:
                    return completed(args, "List of devices attached\n")
                if args == ["adb", "-s", "emulator-5554", "get-state"]:
                    return completed(args, "device\n")
                if args == ["adb", "-s", "emulator-5554", "shell", "getprop", "sys.boot_completed"]:
                    return completed(args, "1\n")
                if args == ["adb", "-s", "emulator-5554", "shell", "pm", "path", "android"]:
                    return completed(args, "package:/system/framework/framework-res.apk\n")
                return completed(args, "OK\n")

            def fake_popen(args, **kwargs):
                calls.append(list(args))
                self.assertTrue(kwargs["start_new_session"])
                self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
                return fake_process

            with patch.dict(os.environ, {
                "BHARATSIM_EMULATOR_ACCEL": "off",
                "BHARATSIM_EMULATOR_LOG": str(log_path),
            }, clear=False):
                result = lifecycle.recycle_emulator(
                    "emulator-5554",
                    "bharatsim-api35",
                    boot_timeout_seconds=60,
                    emulator_binary="/fake/android/emulator",
                    run=fake_run,
                    popen=fake_popen,
                    sleep=lambda _seconds: None,
                    monotonic=lambda: 1.0,
                )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["wipe_data"])
        self.assertFalse(result["snapshot_reused"])
        self.assertEqual(result["serial"], "emulator-5554")
        launch = next(args for args in calls if args and args[0] == "/fake/android/emulator" and "-avd" in args)
        self.assertIn("-wipe-data", launch)
        self.assertIn("-no-snapshot", launch)
        self.assertEqual(launch[launch.index("-port") + 1], "5554")
        self.assertIn(["adb", "-s", "emulator-5554", "emu", "kill"], calls)

    def test_missing_avd_fails_before_stopping_any_device(self):
        calls = []

        def fake_run(args, timeout=10):
            calls.append(list(args))
            if args == ["/fake/android/emulator", "-list-avds"]:
                return completed(args, "other-avd\n")
            return completed(args)

        with patch.dict(os.environ, {"BHARATSIM_EMULATOR_ACCEL": "off"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "was not found"):
                lifecycle.recycle_emulator(
                    "emulator-5554",
                    "bharatsim-api35",
                    emulator_binary="/fake/android/emulator",
                    run=fake_run,
                    popen=lambda *args, **kwargs: self.fail("must not launch without the configured AVD"),
                )
        self.assertEqual(calls, [["/fake/android/emulator", "-list-avds"]])

    def test_boot_failure_terminates_new_emulator_process(self):
        fake_process = FakeProcess()

        def fake_run(args, timeout=10):
            args = list(args)
            if args == ["/fake/android/emulator", "-list-avds"]:
                return completed(args, "bharatsim-api35\n")
            if args == ["adb", "-s", "emulator-5554", "get-state"]:
                return completed(args, "", "device offline", 1)
            if args == ["adb", "devices"]:
                return completed(args, "List of devices attached\n")
            return completed(args)

        ticks = iter(range(1000))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "BHARATSIM_EMULATOR_ACCEL": "off",
            "BHARATSIM_EMULATOR_LOG": str(Path(directory) / "emulator.log"),
        }, clear=False):
            with self.assertRaisesRegex(RuntimeError, "did not complete boot"):
                lifecycle.recycle_emulator(
                    "emulator-5554",
                    "bharatsim-api35",
                    boot_timeout_seconds=60,
                    emulator_binary="/fake/android/emulator",
                    run=fake_run,
                    popen=lambda *args, **kwargs: fake_process,
                    sleep=lambda _seconds: None,
                    monotonic=lambda: float(next(ticks)),
                )
        self.assertTrue(fake_process.terminated)


if __name__ == "__main__":
    unittest.main()
