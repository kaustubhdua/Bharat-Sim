import unittest
from subprocess import CompletedProcess
from unittest.mock import MagicMock

from backend.app.main import PERSONAS
from worker.condition_applicator import (
    ConditionManager,
    apply_battery_saver,
    apply_storage_pressure,
    get_device_meminfo,
    get_free_storage_mb,
    parse_df_available_mb,
    parse_meminfo_mb,
    reset_battery_saver,
    reset_storage_pressure,
    reset_target_safely,
)
from worker.condition_planner import plan_conditions


class ConditionApplicatorTests(unittest.TestCase):
    def test_parse_df_available_mb(self):
        sample_output = """Filesystem     1K-blocks     Used Available Use% Mounted on
/dev/block/dm-0   5800000  1200000   4600000  21% /data
"""
        avail_mb = parse_df_available_mb(sample_output)
        self.assertEqual(avail_mb, 4600000 // 1024)

    def test_parse_meminfo_mb(self):
        sample_meminfo = """MemTotal:        3932160 kB
MemFree:          524288 kB
MemAvailable:    2097152 kB
"""
        parsed = parse_meminfo_mb(sample_meminfo)
        self.assertEqual(parsed["total_ram_mb"], 3840)
        self.assertEqual(parsed["available_ram_mb"], 2048)

    def test_battery_saver_application_and_readback(self):
        def mock_runner(args, timeout=15):
            cmd = " ".join(args)
            if "cmd battery unplug" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "settings put global low_power 1" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "settings get global low_power" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="1\n", stderr="")
            if "dumpsys battery" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="powered: false\n", stderr="")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        res = apply_battery_saver("emulator-5554", run_cmd_fn=mock_runner)
        self.assertEqual(res["apply_status"], "applied")
        self.assertEqual(res["verification_status"], "verified")
        self.assertEqual(res["commands"]["readback_low_power"], "1")

    def test_battery_saver_verification_fails_if_readback_not_one(self):
        def mock_runner(args, timeout=15):
            cmd = " ".join(args)
            if "settings get global low_power" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        res = apply_battery_saver("emulator-5554", run_cmd_fn=mock_runner)
        self.assertEqual(res["verification_status"], "unverified")

    def test_battery_saver_reset(self):
        def mock_runner(args, timeout=15):
            cmd = " ".join(args)
            if "settings get global low_power" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        res = reset_battery_saver("emulator-5554", run_cmd_fn=mock_runner)
        self.assertEqual(res["status"], "verified")
        self.assertEqual(res["readback_low_power"], "0")

    def test_storage_pressure_application_and_cleanup(self):
        df_initial = """Filesystem 1K-blocks Used Available Use% Mounted on
/dev/block/dm-0 5800000 1800000 4000000 31% /data
"""
        df_post = """Filesystem 1K-blocks Used Available Use% Mounted on
/dev/block/dm-0 5800000 5200000 600000 89% /data
"""

        def mock_runner(args, timeout=15):
            cmd = " ".join(args)
            if "df -k /data" in cmd or "df /data" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout=df_initial, stderr="")
            if "dd if=/dev/zero" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="records in\n", stderr="")
            if "ls -l /data/local/tmp" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="-rw-r--r-- 1 root root\n", stderr="")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        # Test application
        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", side_effect=[3906, 600]
        ):
            res = apply_storage_pressure(
                "emulator-5554",
                target_free_mb=600,
                safety_reserve_mb=100,
                max_allocation_mb=4000,
                run_cmd_fn=mock_runner,
            )
        self.assertEqual(res["apply_status"], "applied")
        self.assertEqual(res["verification_status"], "verified")
        self.assertGreater(res["allocated_mb"], 0)

        # Test reset
        def mock_reset_runner(args, timeout=15):
            cmd = " ".join(args)
            if "rm -f" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "ls" in cmd:
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="No such file\n")
            if "df" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout=df_initial, stderr="")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        reset_res = reset_storage_pressure("emulator-5554", run_cmd_fn=mock_reset_runner)
        self.assertEqual(reset_res["status"], "verified")
        self.assertTrue(reset_res["file_removed"])

    def test_storage_pressure_already_satisfied(self):
        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", return_value=500
        ):
            res = apply_storage_pressure("emulator-5554", target_free_mb=600)
            self.assertEqual(res["apply_status"], "already_satisfied")
            self.assertEqual(res["condition_state"], "preexisting_target_satisfied")
            self.assertEqual(res["allocated_mb"], 0)
            self.assertTrue(res["target_reached"])
            self.assertFalse(res["bounded_pressure_applied"])
            self.assertEqual(res["verification_status"], "verified")
            self.assertIn("already at or below target", res["reason"])

    def test_condition_manager_separates_preexisting_target_from_applied_constraints(self):
        plan = plan_conditions(PERSONAS["baseline"], "emulator-5554")
        manager = ConditionManager("emulator-5554", plan)
        manager.condition_records = [{
            "condition": "storage_pressure",
            "requested": True,
            "apply_status": "already_satisfied",
            "verification_status": "verified",
            "condition_state": "preexisting_target_satisfied",
            "target_reached": True,
            "bounded_pressure_applied": False,
            "allocated_mb": 0,
        }]
        evidence = manager.get_evidence()
        self.assertEqual(evidence["overall_status"], "already_satisfied")
        self.assertEqual(evidence["applied_conditions_count"], 0)
        self.assertEqual(evidence["preexisting_conditions_count"], 1)
        self.assertFalse(evidence["constraints_applied"])

    def test_storage_pressure_target_successfully_reached(self):
        def mock_runner(args, timeout=15):
            cmd = " ".join(args)
            if "dd if=/dev/zero" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="records in\n", stderr="")
            if "ls -l /data/local/tmp" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="-rw-r--r-- 1 root root\n", stderr="")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", side_effect=[1000, 500]
        ):
            res = apply_storage_pressure(
                "emulator-5554",
                target_free_mb=500,
                safety_reserve_mb=100,
                max_allocation_mb=2048,
                run_cmd_fn=mock_runner,
            )
        self.assertEqual(res["apply_status"], "applied")
        self.assertEqual(res["verification_status"], "verified")
        self.assertTrue(res["target_reached"])
        self.assertTrue(res["bounded_pressure_applied"])
        self.assertEqual(res["allocated_mb"], 500)
        self.assertEqual(res["actual_achieved_free_mb"], 500)
        self.assertIsNone(res["limitation_reason"])

    def test_storage_pressure_target_not_reachable_because_max_allocation_hit(self):
        def mock_runner(args, timeout=15):
            cmd = " ".join(args)
            if "dd if=/dev/zero" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="records in\n", stderr="")
            if "ls -l /data/local/tmp" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="-rw-r--r-- 1 root root\n", stderr="")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        # Initial 5000 MB, target 900 MB (would need 4100 MB), max allocation 2048 MB -> post_free 2952 MB
        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", side_effect=[5000, 2952]
        ):
            res = apply_storage_pressure(
                "emulator-5554",
                target_free_mb=900,
                safety_reserve_mb=100,
                max_allocation_mb=2048,
                run_cmd_fn=mock_runner,
            )
        self.assertEqual(res["apply_status"], "partially_applied")
        self.assertEqual(res["verification_status"], "verified")
        self.assertFalse(res["target_reached"])
        self.assertTrue(res["bounded_pressure_applied"])
        self.assertEqual(res["allocated_mb"], 2048)
        self.assertEqual(res["actual_achieved_free_mb"], 2952)
        self.assertIn("Bounded allocation cap of 2048 MB reached", res["limitation_reason"])
        self.assertIn("could not be fully reached", res["reason"])

    def test_storage_pressure_safety_reserve_prevents_allocation(self):
        # Initial 80 MB, safety reserve 100 MB -> cannot allocate anything safely
        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", return_value=80
        ):
            res = apply_storage_pressure(
                "emulator-5554",
                target_free_mb=30,
                safety_reserve_mb=100,
                max_allocation_mb=2048,
            )
        self.assertEqual(res["apply_status"], "skipped")
        self.assertEqual(res["verification_status"], "unverified")
        self.assertFalse(res["target_reached"])
        self.assertFalse(res["bounded_pressure_applied"])
        self.assertEqual(res["allocated_mb"], 0)
        self.assertIn("Safety reserve of 100 MB prevents any allocation", res["limitation_reason"])

    def test_storage_pressure_allocation_failure(self):
        def mock_failing_runner(args, timeout=15):
            cmd = " ".join(args)
            if "dd if=/dev/zero" in cmd:
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="dd: write error: No space left on device\n")
            if "ls -l /data/local/tmp" in cmd:
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="No such file\n")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", side_effect=[2000, 2000]
        ):
            res = apply_storage_pressure(
                "emulator-5554",
                target_free_mb=1000,
                safety_reserve_mb=100,
                max_allocation_mb=2048,
                run_cmd_fn=mock_failing_runner,
            )
        self.assertEqual(res["apply_status"], "failed")
        self.assertEqual(res["verification_status"], "unverified")
        self.assertFalse(res["target_reached"])
        self.assertFalse(res["bounded_pressure_applied"])

    def test_partial_application_is_not_reported_as_full_verification(self):
        # edge-village requests 900 MB free storage and battery_saver=True
        plan = plan_conditions(PERSONAS["edge-village"], "emulator-5554")
        mock_apply_net = MagicMock(
            return_value={"control_plane": {"status": "verified"}, "network_constraints_applied": True}
        )
        mock_reset_net = MagicMock(return_value={"status": "verified"})

        file_present = [True]
        low_power_state = ["1"]

        def mock_adb_runner(args, timeout=15):
            cmd = " ".join(args)
            if "settings put global low_power 1" in cmd:
                low_power_state[0] = "1"
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "settings put global low_power 0" in cmd:
                low_power_state[0] = "0"
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "settings get global low_power" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout=f"{low_power_state[0]}\n", stderr="")
            if "rm -f" in cmd:
                file_present[0] = False
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "ls" in cmd:
                if file_present[0]:
                    return CompletedProcess(args=args, returncode=0, stdout="-rw-r--r--\n", stderr="")
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="No such file\n")
            if "dd if=/dev/zero" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "cat /proc/meminfo" in cmd:
                return CompletedProcess(
                    args=args, returncode=0, stdout="MemTotal: 2097152 kB\nMemAvailable: 1048576 kB\n", stderr=""
                )
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        # Emulate 5000 MB initial free, post-allocation 2952 MB (capped at 2048 MB)
        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", side_effect=[5000, 2952, 2952, 5000]
        ):
            manager = ConditionManager(
                "emulator-5554",
                plan,
                run_cmd_fn=mock_adb_runner,
                apply_network_fn=mock_apply_net,
                reset_network_fn=mock_reset_net,
            )
            with manager:
                evidence = manager.get_evidence()
                # constraints_applied MUST be False because edge-village target was only partially achieved (and packet loss unsupported)
                self.assertFalse(evidence["constraints_applied"])
                self.assertNotEqual(evidence["overall_status"], "applied_and_verified")
                self.assertIn("partially_applied", evidence["overall_status"])

                stor_record = next(c for c in evidence["conditions"] if c["condition"] == "storage_pressure")
                self.assertEqual(stor_record["apply_status"], "partially_applied")
                self.assertEqual(stor_record["verification_status"], "verified")
                self.assertFalse(stor_record["target_reached"])
                self.assertTrue(stor_record["bounded_pressure_applied"])
                self.assertGreater(evidence["partially_applied_conditions_count"], 0)

        # Cleanup should succeed and remove the file
        self.assertEqual(manager.cleanup_records["status"], "verified")
        self.assertTrue(manager.cleanup_records["verified"])

    def test_cleanup_remains_verified_despite_small_free_space_variation(self):
        def mock_reset_runner(args, timeout=15):
            cmd = " ".join(args)
            if "rm -f" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "ls" in cmd:
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="No such file\n")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        # Before cleanup: 3000 MB. After cleanup: 4950 MB (small variance from original 5000 MB)
        with unittest.mock.patch(
            "worker.condition_applicator.get_free_storage_mb", side_effect=[3000, 4950]
        ):
            reset_res = reset_storage_pressure("emulator-5554", run_cmd_fn=mock_reset_runner)

        self.assertEqual(reset_res["status"], "verified")
        self.assertTrue(reset_res["file_removed"])
        self.assertEqual(reset_res["free_storage_mb_before_cleanup"], 3000)
        self.assertEqual(reset_res["free_storage_mb_after_cleanup"], 4950)

    def test_network_condition_application_delegation(self):
        plan = plan_conditions(PERSONAS["budget-android"], "emulator-5554")
        mock_apply_net = MagicMock(
            return_value={
                "control_plane": {"status": "verified"},
                "network_constraints_applied": True,
                "traffic_path_verified": False,
            }
        )
        mock_reset_net = MagicMock(return_value={"status": "verified"})

        low_power_state = ["1"]
        file_present = [True]
        df_free_kb = [4000000]

        def mock_adb_runner(args, timeout=15):
            cmd = " ".join(args)
            if "settings put global low_power 1" in cmd:
                low_power_state[0] = "1"
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "settings put global low_power 0" in cmd:
                low_power_state[0] = "0"
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "settings get global low_power" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout=f"{low_power_state[0]}\n", stderr="")
            if "rm -f" in cmd:
                file_present[0] = False
                df_free_kb[0] = 4000000
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "ls" in cmd:
                if file_present[0]:
                    return CompletedProcess(args=args, returncode=0, stdout="-rw-r--r--\n", stderr="")
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="No such file\n")
            if "df" in cmd:
                return CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=f"Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-0 5800000 1800000 {df_free_kb[0]} 31% /data\n",
                    stderr="",
                )
            if "dd if=/dev/zero" in cmd:
                df_free_kb[0] = 614400
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "cat /proc/meminfo" in cmd:
                return CompletedProcess(
                    args=args, returncode=0, stdout="MemTotal: 2097152 kB\nMemAvailable: 1048576 kB\n", stderr=""
                )
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        manager = ConditionManager(
            "emulator-5554",
            plan,
            run_cmd_fn=mock_adb_runner,
            apply_network_fn=mock_apply_net,
            reset_network_fn=mock_reset_net,
        )

        with manager:
            evidence = manager.get_evidence()
            self.assertEqual(evidence["persona_id"], "budget-android")
            self.assertFalse(evidence["traffic_path_verified"])
            # Full-persona application must remain false when packet loss is unsupported
            # and RAM is report-only, even though supported network controls were applied.
            self.assertFalse(evidence["constraints_applied"])
            self.assertEqual(evidence["overall_status"], "partially_applied_and_verified")
            mock_apply_net.assert_called_once_with("emulator-5554", 180, 1200, 350, 2.0)

        mock_reset_net.assert_called_once_with("emulator-5554")
        cleanup = manager.cleanup_records
        self.assertEqual(cleanup["status"], "verified")
        self.assertTrue(cleanup["verified"])

    def test_cleanup_occurs_when_block_raises_exception(self):
        plan = plan_conditions(PERSONAS["budget-android"], "emulator-5554")
        mock_apply_net = MagicMock(
            return_value={"control_plane": {"status": "verified"}, "network_constraints_applied": True}
        )
        mock_reset_net = MagicMock(return_value={"status": "verified"})

        def mock_adb_runner(args, timeout=15):
            cmd = " ".join(args)
            if "settings get global low_power" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            if "df" in cmd:
                return CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-0 5800000 1800000 4000000 31% /data\n",
                    stderr="",
                )
            if "dd if=/dev/zero" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if "ls" in cmd:
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="No such file\n")
            if "cat /proc/meminfo" in cmd:
                return CompletedProcess(
                    args=args, returncode=0, stdout="MemTotal: 2097152 kB\nMemAvailable: 1048576 kB\n", stderr=""
                )
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        manager = ConditionManager(
            "emulator-5554",
            plan,
            run_cmd_fn=mock_adb_runner,
            apply_network_fn=mock_apply_net,
            reset_network_fn=mock_reset_net,
        )

        with self.assertRaises(RuntimeError):
            with manager:
                raise RuntimeError("simulated app crash during smoke run")

        # Verify cleanup still ran
        mock_reset_net.assert_called_once()
        self.assertEqual(manager.cleanup_records["status"], "verified")

    def test_cleanup_verification_failure_is_reported(self):
        plan = plan_conditions(PERSONAS["budget-android"], "emulator-5554")
        mock_apply_net = MagicMock(
            return_value={"control_plane": {"status": "verified"}, "network_constraints_applied": True}
        )
        mock_reset_net = MagicMock(return_value={"status": "unverified", "reason": "status mismatch"})

        def mock_adb_runner(args, timeout=15):
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        manager = ConditionManager(
            "emulator-5554",
            plan,
            run_cmd_fn=mock_adb_runner,
            apply_network_fn=mock_apply_net,
            reset_network_fn=mock_reset_net,
        )

        with manager:
            pass

        self.assertEqual(manager.cleanup_records["status"], "partial_or_failed")
        self.assertFalse(manager.cleanup_records["verified"])

    def test_reset_target_safely_standalone(self):
        def mock_runner(args, timeout=15):
            cmd = " ".join(args)
            if "settings get global low_power" in cmd:
                return CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            if "ls" in cmd:
                return CompletedProcess(args=args, returncode=1, stdout="", stderr="No such file\n")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        res = reset_target_safely("emulator-5554", run_cmd_fn=mock_runner)
        self.assertIn("network", res)
        self.assertIn("battery_saver", res)
        self.assertIn("storage", res)
        self.assertEqual(res["battery_saver"]["status"], "verified")
        self.assertEqual(res["storage"]["status"], "verified")

    def test_reset_target_safely_rejects_physical_device(self):
        res = reset_target_safely("R58M123ABC")
        self.assertEqual(res["status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
