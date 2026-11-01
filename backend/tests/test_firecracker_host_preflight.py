from __future__ import annotations

import os
import sys
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.firecracker_host_preflight import inspect_host


class FirecrackerHostPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.proc = self.root / "proc"
        self.sys = self.root / "sys"
        self.dev = self.root / "dev"
        (self.proc).mkdir()
        (self.sys / "fs/cgroup").mkdir(parents=True)
        self.dev.mkdir()
        (self.proc / "swaps").write_text("Filename Type Size Used Priority\n")
        (self.sys / "fs/cgroup/cgroup.controllers").write_text("cpuset cpu io memory pids\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.fc = self.bin / "firecracker"
        self.jailer = self.bin / "jailer"
        self.fc.write_text("#!/bin/sh\n")
        self.jailer.write_text("#!/bin/sh\n")
        self.fc.chmod(0o755)
        self.jailer.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="Firecracker v1.17.0", stderr="")

    def inspect(self, **overrides):
        values = dict(
            proc_root=self.proc, sys_root=self.sys, dev_root=self.dev,
            firecracker=str(self.fc), jailer=str(self.jailer),
            machine="x86_64", uid=0, runner=self.runner, which=lambda _: None,
        )
        values.update(overrides)
        return {item["name"]: item for item in inspect_host(**values)}

    def test_reports_missing_kvm_and_missing_cgroup_controllers(self):
        (self.sys / "fs/cgroup/cgroup.controllers").write_text("cpu memory\n")
        checks = self.inspect()
        self.assertFalse(checks["kvm_device"]["ok"])
        self.assertFalse(checks["cgroup_v2"]["ok"])

    def test_blocks_active_swap_and_wrong_architecture(self):
        (self.proc / "swaps").write_text("Filename Type Size Used Priority\n/swapfile file 100 1 -2\n")
        checks = self.inspect(machine="aarch64")
        self.assertFalse(checks["swap_disabled"]["ok"])
        self.assertFalse(checks["architecture"]["ok"])

    def test_requires_matching_firecracker_and_jailer_versions(self):
        def mismatched(args, **kwargs):
            version = "v1.17.0" if args[0] == str(self.fc) else "v1.16.0"
            return subprocess.CompletedProcess(args, 0, stdout=version, stderr="")
        checks = self.inspect(runner=mismatched)
        self.assertFalse(checks["matching_release"]["ok"])

    def test_requires_root_owned_non_writable_jailer_directory(self):
        self.bin.chmod(0o777)
        with patch("scripts.firecracker_host_preflight.os.stat") as mocked:
            mocked.return_value = type("Stat", (), {"st_uid": 1000, "st_mode": stat.S_IFDIR | 0o755})()
            checks = self.inspect()
        self.assertFalse(checks["trusted_jailer_directory"]["ok"])

    def test_reports_non_root_operator(self):
        checks = self.inspect(uid=1000)
        self.assertFalse(checks["operator_identity"]["ok"])


if __name__ == "__main__":
    unittest.main()
