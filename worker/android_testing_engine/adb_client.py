"""
ADB Client module for managing Android Debug Bridge interactions.
Handles device discovery, APK installation, app launching, logcat capture,
and environment validation on Windows and Unix systems.
"""

import os
import re
import shutil
import subprocess
import time
from typing import List, Optional, Tuple, Dict, Any
from .models import DeviceInfo


class ADBError(Exception):
    """Custom exception for ADB-related failures."""
    pass


class ADBClient:
    """
    High-level, resilient wrapper around ADB CLI commands.
    """

    def __init__(self, adb_path: Optional[str] = None):
        self.adb_bin = self._resolve_adb_path(adb_path)

    @classmethod
    def _resolve_adb_path(cls, explicit_path: Optional[str] = None) -> Optional[str]:
        """Finds adb executable in explicit path, PATH, or standard Android SDK directories."""
        if explicit_path and os.path.isfile(explicit_path):
            return os.path.abspath(explicit_path)

        # Check PATH
        which_adb = shutil.which("adb")
        if which_adb:
            return which_adb

        # Check environment variables
        sdk_candidates = [
            os.environ.get("ANDROID_HOME"),
            os.environ.get("ANDROID_SDK_ROOT"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"),
            os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Android", "Sdk"),
            r"C:\Program Files\Android\Android Studio\platform-tools",
            r"C:\Android\platform-tools"
        ]

        exe_name = "adb.exe" if os.name == "nt" else "adb"
        for sdk_dir in sdk_candidates:
            if not sdk_dir:
                continue
            candidate = os.path.join(sdk_dir, "platform-tools", exe_name)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)
            # Or if pointing directly to platform-tools
            direct_candidate = os.path.join(sdk_dir, exe_name)
            if os.path.isfile(direct_candidate):
                return os.path.abspath(direct_candidate)

        return None

    def is_adb_available(self) -> Tuple[bool, str]:
        """Checks if ADB binary is installed and executable."""
        if not self.adb_bin or not os.path.isfile(self.adb_bin):
            return (
                False,
                "ADB is not installed or not found in system PATH. "
                "Please install Android Platform Tools and add 'adb' to your PATH."
            )
        try:
            res = self._run_adb(["version"], timeout=5)
            if res.returncode == 0:
                first_line = res.stdout.splitlines()[0] if res.stdout else "ADB Available"
                return True, first_line.strip()
            return False, f"ADB check failed with exit code {res.returncode}: {res.stderr}"
        except Exception as e:
            return False, f"Failed to execute ADB at '{self.adb_bin}': {str(e)}"

    def _run_adb(
        self,
        args: List[str],
        device_id: Optional[str] = None,
        timeout: int = 60,
        check: bool = False
    ) -> subprocess.CompletedProcess:
        """Executes an ADB command safely using subprocess."""
        if not self.adb_bin:
            raise ADBError("ADB executable not found. Cannot run command.")

        cmd = [self.adb_bin]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(args)

        try:
            # On Windows, suppress shell window popup
            kwargs: Dict[str, Any] = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "timeout": timeout
            }
            if os.name == "nt":
                # Create no window flag
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

            proc = subprocess.run(cmd, check=check, **kwargs)
            return proc
        except subprocess.TimeoutExpired as e:
            raise ADBError(f"ADB command '{' '.join(args)}' timed out after {timeout}s.") from e
        except Exception as e:
            raise ADBError(f"ADB execution failed: {str(e)}") from e

    def get_connected_devices(self) -> List[DeviceInfo]:
        """
        Lists connected Android devices and emulators.
        Filters out offline or unauthorized devices from the ready pool.
        """
        res = self._run_adb(["devices", "-l"], timeout=10)
        devices: List[DeviceInfo] = []

        lines = res.stdout.splitlines()
        for line in lines[1:]:  # skip 'List of devices attached'
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            device_id = parts[0]
            status = parts[1] if len(parts) > 1 else "unknown"

            if status != "device":
                # Unauthorized, offline, etc.
                continue

            # Parse key-values like model:Pixel_6 product:oriole transport_id:1
            model = "Unknown"
            device_prop = "Unknown"
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1].replace("_", " ")
                elif part.startswith("device:"):
                    device_prop = part.split(":", 1)[1]

            is_emu = device_id.startswith("emulator-") or "sdk_gphone" in model.lower()

            # Retrieve Android OS version and brand
            android_ver, api_lvl, brand = self._query_device_props(device_id)

            devices.append(DeviceInfo(
                device_id=device_id,
                model=model,
                manufacturer=brand,
                brand=brand,
                android_version=android_ver,
                api_level=api_lvl,
                is_emulator=is_emu
            ))

        return devices

    def _query_device_props(self, device_id: str) -> Tuple[str, str, str]:
        """Queries getprop for Android version, API level, and brand."""
        android_ver = "Unknown"
        api_lvl = "Unknown"
        brand = "Unknown"
        try:
            res_ver = self._run_adb(["shell", "getprop", "ro.build.version.release"], device_id=device_id, timeout=5)
            if res_ver.returncode == 0 and res_ver.stdout.strip():
                android_ver = res_ver.stdout.strip()

            res_sdk = self._run_adb(["shell", "getprop", "ro.build.version.sdk"], device_id=device_id, timeout=5)
            if res_sdk.returncode == 0 and res_sdk.stdout.strip():
                api_lvl = res_sdk.stdout.strip()

            res_brand = self._run_adb(["shell", "getprop", "ro.product.brand"], device_id=device_id, timeout=5)
            if res_brand.returncode == 0 and res_brand.stdout.strip():
                brand = res_brand.stdout.strip().capitalize()
        except Exception:
            pass

        return android_ver, api_lvl, brand

    def get_installed_packages(self, device_id: Optional[str] = None, third_party_only: bool = True) -> List[str]:
        """Returns list of installed packages on the device."""
        args = ["shell", "pm", "list", "packages"]
        if third_party_only:
            args.append("-3")
        res = self._run_adb(args, device_id=device_id, timeout=10)
        packages = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.split(":", 1)[1].strip())
        return packages

    def install_apk(
        self,
        apk_path: str,
        device_id: Optional[str] = None,
        reinstall: bool = True,
        grant_runtime_permissions: bool = True,
        timeout: int = 180
    ) -> Tuple[bool, str]:
        """
        Installs an APK file to the device.
        Returns (success: bool, message: str)
        """
        if not os.path.isfile(apk_path):
            return False, f"APK file not found: {apk_path}"

        args = ["install"]
        if reinstall:
            args.append("-r")
        if grant_runtime_permissions:
            args.append("-g")
        args.append(os.path.abspath(apk_path))

        try:
            res = self._run_adb(args, device_id=device_id, timeout=timeout)
            combined_output = f"{res.stdout}\n{res.stderr}".strip()

            if "Success" in combined_output:
                return True, "Installation successful"

            # Parse standard Android install failures
            fail_match = re.search(r"INSTALL_FAILED_[A-Z0-9_]+", combined_output)
            if fail_match:
                fail_code = fail_match.group(0)
                return False, f"Installation failed with code {fail_code}: {combined_output}"

            if res.returncode != 0:
                return False, f"Installation failed: {combined_output or f'Exit code {res.returncode}'}"

            return True, "Installation finished"
        except ADBError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error during APK install: {str(e)}"

    def resolve_launchable_activity(self, package_name: str, device_id: Optional[str] = None) -> Optional[str]:
        """Tries resolving the main launcher activity from package manager on the device."""
        try:
            # cmd package resolve-activity --brief <package>
            res = self._run_adb(
                ["shell", "cmd", "package", "resolve-activity", "--brief", package_name],
                device_id=device_id,
                timeout=5
            )
            for line in res.stdout.splitlines():
                line = line.strip()
                if "/" in line and not line.startswith("priority="):
                    # e.g. com.example.app/.MainActivity
                    return line
        except Exception:
            pass
        return None

    def launch_app(
        self,
        package_name: str,
        activity_name: Optional[str] = None,
        device_id: Optional[str] = None,
        timeout: int = 25
    ) -> Tuple[bool, Optional[str], str]:
        """
        Launches the application using ADB am start or monkey fallback.
        Returns (success: bool, launched_activity: Optional[str], message: str)
        """
        # Strategy A: If activity_name is provided, use am start
        if activity_name:
            component = (
                activity_name
                if "/" in activity_name
                else f"{package_name}/{activity_name}"
            )
            try:
                res = self._run_adb(
                    ["shell", "am", "start", "-W", "-n", component],
                    device_id=device_id,
                    timeout=timeout
                )
                output = f"{res.stdout}\n{res.stderr}"
                if "Status: ok" in output or "Complete" in output or res.returncode == 0:
                    if "Error:" not in output:
                        return True, component, f"Launched successfully: {component}"
                # If am start failed with Error, we might attempt monkey fallback
                err_line = [l.strip() for l in output.splitlines() if "Error:" in l or "Exception" in l]
                err_msg = err_line[0] if err_line else output.strip()
            except Exception as e:
                err_msg = str(e)
        else:
            # Try to resolve activity on device first
            resolved = self.resolve_launchable_activity(package_name, device_id=device_id)
            if resolved:
                return self.launch_app(package_name, activity_name=resolved, device_id=device_id, timeout=timeout)
            err_msg = "No launchable activity provided or resolved"

        # Strategy B: Fallback to Android monkey tool (standard way to launch default activity)
        try:
            res_monkey = self._run_adb(
                ["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
                device_id=device_id,
                timeout=timeout
            )
            out_monkey = res_monkey.stdout
            if "Events injected: 1" in out_monkey:
                return True, activity_name or "DEFAULT_LAUNCHER", "Launched successfully via monkey"
            if "No activities found to run" in out_monkey:
                return False, None, f"Launch failed: No launchable activity found in package '{package_name}'"
        except Exception as e:
            err_msg += f" | Monkey fallback error: {str(e)}"

        return False, None, f"Application launch failed: {err_msg}"

    def force_stop(self, package_name: str, device_id: Optional[str] = None):
        """Force stops the application."""
        try:
            self._run_adb(["shell", "am", "force-stop", package_name], device_id=device_id, timeout=5)
        except Exception:
            pass

    def clear_logcat(self, device_id: Optional[str] = None):
        """Clears the logcat buffer."""
        try:
            self._run_adb(["logcat", "-c"], device_id=device_id, timeout=5)
        except Exception:
            pass

    def dump_logcat(self, device_id: Optional[str] = None, timeout: int = 15) -> str:
        """Dumps the current logcat buffer as string."""
        try:
            res = self._run_adb(["logcat", "-d", "-v", "time"], device_id=device_id, timeout=timeout)
            return res.stdout
        except Exception as e:
            return f"Failed to dump logcat: {str(e)}"

    def start_logcat_stream(
        self,
        output_file_path: str,
        device_id: Optional[str] = None
    ) -> Optional[subprocess.Popen]:
        """
        Starts background logcat capture to a dedicated output file.
        Returns Popen handle so it can be terminated when test finishes.
        """
        if not self.adb_bin:
            return None

        cmd = [self.adb_bin]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(["logcat", "-v", "time"])

        os.makedirs(os.path.dirname(os.path.abspath(output_file_path)), exist_ok=True)
        try:
            log_f = open(output_file_path, "w", encoding="utf-8", errors="replace")
            kwargs: Dict[str, Any] = {
                "stdout": log_f,
                "stderr": subprocess.STDOUT,
                "text": True,
            }
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

            proc = subprocess.Popen(cmd, **kwargs)
            return proc
        except Exception:
            return None
