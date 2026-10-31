"""
Crash Detection module for Android logcat analysis.
Accurately detects fatal crashes, unhandled exceptions, native SIGSEGV/SIGABRT signals,
and ANRs (Application Not Responding) without false positives on ordinary warnings.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from .models import CrashDetail


class CrashDetector:
    """
    Parses and analyzes Android logcat output to detect crashes and fatal exceptions.
    """

    # Patterns indicating unhandled fatal Java exceptions
    FATAL_HEADER_RE = re.compile(
        r"(?:FATAL EXCEPTION:\s*(?P<thread>.+)|AndroidRuntime:\s*FATAL EXCEPTION:\s*(?P<thread2>.+))",
        re.IGNORECASE
    )
    PROCESS_LINE_RE = re.compile(
        r"Process:\s*(?P<process>[a-zA-Z0-9_\.]+)(?:,\s*PID:\s*(?P<pid>\d+))?",
        re.IGNORECASE
    )
    EXCEPTION_RE = re.compile(
        r"(?P<exc_class>[a-zA-Z0-9_\.]+(?:Exception|Error))(?::\s*(?P<msg>.*))?"
    )
    
    # Native crash patterns
    NATIVE_CRASH_RE = re.compile(
        r"Fatal signal\s+(?P<signal>\d+)\s*\((?P<signame>[A-Z0-9_]+)\).*?(?:in tid\s+(?P<tid>\d+)|pid\s+(?P<pid>\d+))?",
        re.IGNORECASE
    )
    NATIVE_PKG_RE = re.compile(
        r">>>\s*(?P<process>[a-zA-Z0-9_\.]+)\s*<<<"
    )

    # ANR patterns
    ANR_HEADER_RE = re.compile(
        r"ANR in\s+(?P<process>[a-zA-Z0-9_\.]+)(?:\s*\((?P<component>[^)]+)\))?",
        re.IGNORECASE
    )
    ANR_REASON_RE = re.compile(
        r"Reason:\s*(?P<reason>.+)",
        re.IGNORECASE
    )

    # Process death patterns
    PROCESS_DIED_RE = re.compile(
        r"(?:Process\s+(?P<process>[a-zA-Z0-9_\.]+)\s*\(pid\s*(?P<pid>\d+)\)\s*has died|Killing\s+\d+:(?P<process2>[a-zA-Z0-9_\.]+)/.*?\(adj\s+\d+\))",
        re.IGNORECASE
    )

    # Logcat line timestamp parser: e.g. "10-31 12:34:56.789"
    LOGCAT_TIMESTAMP_RE = re.compile(
        r"^(?P<time>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})"
    )

    def __init__(self, target_package: Optional[str] = None):
        self.target_package = target_package

    def analyze_log_content(self, log_content: str) -> Tuple[bool, List[CrashDetail], List[str]]:
        """
        Analyzes full log content (string) or logcat dump.
        Returns:
            (crash_detected, list_of_crash_details, relevant_error_logs)
        """
        lines = log_content.splitlines()
        return self.analyze_log_lines(lines)

    def analyze_log_lines(self, lines: List[str]) -> Tuple[bool, List[CrashDetail], List[str]]:
        crashes: List[CrashDetail] = []
        error_logs: List[str] = []

        total_lines = len(lines)
        i = 0

        while i < total_lines:
            line = lines[i]
            timestamp = self._extract_timestamp(line)

            # Collect relevant error-level logs (excluding false positives)
            if self._is_relevant_error_log(line):
                error_logs.append(line.strip())

            # 1. Check for Java FATAL EXCEPTION / AndroidRuntime crash
            fatal_match = self.FATAL_HEADER_RE.search(line)
            if fatal_match:
                crash, next_idx = self._parse_fatal_exception_block(lines, i)
                if crash and self._matches_target(crash.process_name):
                    crashes.append(crash)
                i = next_idx
                continue

            # 2. Check for Native Crash (SIGSEGV / SIGABRT)
            native_match = self.NATIVE_CRASH_RE.search(line)
            if native_match:
                crash, next_idx = self._parse_native_crash_block(lines, i, native_match)
                if crash and self._matches_target(crash.process_name):
                    crashes.append(crash)
                i = next_idx
                continue

            # 3. Check for ANR (Application Not Responding)
            anr_match = self.ANR_HEADER_RE.search(line)
            if anr_match:
                crash, next_idx = self._parse_anr_block(lines, i, anr_match)
                if crash and self._matches_target(crash.process_name):
                    crashes.append(crash)
                i = next_idx
                continue

            # 4. Check for sudden process death of target package
            if self.target_package:
                death_match = self.PROCESS_DIED_RE.search(line)
                if death_match:
                    pkg = death_match.group("process") or death_match.group("process2")
                    if pkg and self._matches_target(pkg):
                        pid = death_match.group("pid") if "pid" in death_match.groupdict() else None
                        crashes.append(CrashDetail(
                            crash_type="PROCESS_DIED",
                            reason=f"Target process died unexpectedly: {line.strip()}",
                            timestamp=timestamp or "UNKNOWN",
                            pid=pid,
                            process_name=pkg,
                            stack_trace=[line.strip()]
                        ))

            i += 1

        crash_detected = len(crashes) > 0
        # Keep error_logs bounded to a reasonable size (last 100 relevant errors)
        if len(error_logs) > 100:
            error_logs = error_logs[-100:]

        return crash_detected, crashes, error_logs

    def _matches_target(self, process_name: Optional[str]) -> bool:
        """Checks if process matches target package. If no target specified, match any non-system app."""
        if not process_name:
            return True
        if self.target_package:
            return (self.target_package in process_name) or (process_name in self.target_package)
        
        # When target package is unknown, ignore obvious Android system deamons
        ignored_system_daemons = [
            "system_server", "surfaceflinger", "logd", "netd", "vold",
            "com.android.systemui", "audioserver", "cameraserver"
        ]
        return not any(daemon in process_name for daemon in ignored_system_daemons)

    def _extract_timestamp(self, line: str) -> Optional[str]:
        m = self.LOGCAT_TIMESTAMP_RE.match(line)
        return m.group("time") if m else None

    def _is_relevant_error_log(self, line: str) -> bool:
        """Identifies notable error logs without classifying simple warnings."""
        if not line:
            return False
        # False-positive filters: typical benign warnings in Android logcat
        benign_tokens = [
            "W/ResourceType", "W/AudioTrack", "W/OpenGLRenderer",
            "W/Choreographer", "W/Gralloc4", "I/", "D/", "V/"
        ]
        if any(token in line for token in benign_tokens):
            return False

        error_tokens = [
            " E AndroidRuntime", " E/AndroidRuntime", "FATAL EXCEPTION",
            "Fatal signal", "ANR in", "DEBUG   : pid: "
        ]
        if any(token in line for token in error_tokens):
            return True

        if self.target_package and self.target_package in line:
            if " E/" in line or " E " in line:
                return True

        return False

    def _parse_fatal_exception_block(self, lines: List[str], start_idx: int) -> Tuple[Optional[CrashDetail], int]:
        """Extracts process, exception class, reason, and stack trace from AndroidRuntime fatal block."""
        header_line = lines[start_idx]
        timestamp = self._extract_timestamp(header_line) or "UNKNOWN"
        process_name = None
        pid = None
        reason = ""
        stack_trace = [header_line.strip()]
        
        idx = start_idx + 1
        limit = min(len(lines), start_idx + 50)  # parse up to 50 lines of stack trace

        while idx < limit:
            curr = lines[idx]
            
            # Check for Process: ... PID: ...
            proc_match = self.PROCESS_LINE_RE.search(curr)
            if proc_match:
                process_name = proc_match.group("process")
                pid = proc_match.group("pid")
                stack_trace.append(curr.strip())
                idx += 1
                continue

            # Look for Exception class and message line
            if not reason and ("Exception" in curr or "Error" in curr):
                reason = curr.strip()
                stack_trace.append(curr.strip())
                idx += 1
                continue

            # Check if this line is part of stack trace (starts with \tat or Caused by or contains backtrace)
            stripped = curr.strip()
            if stripped.startswith("at ") or "\tat " in curr or stripped.startswith("Caused by:") or stripped.startswith("..."):
                stack_trace.append(stripped)
                idx += 1
            elif "AndroidRuntime" in curr:
                stack_trace.append(stripped)
                idx += 1
            else:
                # End of stack trace block reached
                break

        if not reason:
            reason = f"Fatal exception occurred in {process_name or 'application'}"

        crash = CrashDetail(
            crash_type="FATAL_EXCEPTION",
            reason=reason,
            timestamp=timestamp,
            pid=pid,
            process_name=process_name,
            stack_trace=stack_trace
        )
        return crash, idx

    NATIVE_PID_PKG_RE = re.compile(
        r"pid:\s*(?P<pid>\d+).*?>>>\s*(?P<process>[a-zA-Z0-9_\.]+)\s*<<<",
        re.IGNORECASE
    )

    def _parse_native_crash_block(self, lines: List[str], start_idx: int, match: re.Match) -> Tuple[Optional[CrashDetail], int]:
        """Parses native SIGSEGV / SIGABRT / tombstone crash output."""
        header_line = lines[start_idx]
        timestamp = self._extract_timestamp(header_line) or "UNKNOWN"
        signame = match.group("signame") or "NATIVE_SIGNAL"
        pid = match.group("pid") or match.group("tid")
        process_name = None
        stack_trace = [header_line.strip()]

        idx = start_idx + 1
        limit = min(len(lines), start_idx + 50)
        consecutive_non_native = 0

        while idx < limit:
            curr = lines[idx]
            stripped = curr.strip()

            # Check for >>> package_name <<< or pid: ... >>> ... <<<
            pid_pkg_m = self.NATIVE_PID_PKG_RE.search(curr)
            if pid_pkg_m:
                process_name = pid_pkg_m.group("process")
                if not pid:
                    pid = pid_pkg_m.group("pid")

            pkg_m = self.NATIVE_PKG_RE.search(curr)
            if pkg_m and not process_name:
                process_name = pkg_m.group("process")

            # Native crash lines include DEBUG, crash_dump, tombstone, backtrace, libc fatal
            is_native_line = any(token in curr for token in (
                "DEBUG", "crash_dump", "tombstoned", "backtrace", "#00 pc",
                "Fatal signal", "signal ", "pid: ", "fault addr", "Abort message"
            ))

            if is_native_line:
                stack_trace.append(stripped)
                consecutive_non_native = 0
                idx += 1
            else:
                consecutive_non_native += 1
                if consecutive_non_native > 2:
                    break
                idx += 1

        crash = CrashDetail(
            crash_type=f"NATIVE_CRASH_{signame}",
            reason=f"Native crash: Signal {signame} ({header_line.strip()})",
            timestamp=timestamp,
            pid=pid,
            process_name=process_name,
            stack_trace=stack_trace
        )
        return crash, idx

    def _parse_anr_block(self, lines: List[str], start_idx: int, match: re.Match) -> Tuple[Optional[CrashDetail], int]:
        """Parses ANR report block."""
        header_line = lines[start_idx]
        timestamp = self._extract_timestamp(header_line) or "UNKNOWN"
        process_name = match.group("process")
        reason = f"ANR in {process_name}"
        stack_trace = [header_line.strip()]

        idx = start_idx + 1
        limit = min(len(lines), start_idx + 25)

        while idx < limit:
            curr = lines[idx]
            stripped = curr.strip()
            r_m = self.ANR_REASON_RE.search(curr)
            if r_m:
                reason = f"ANR: {r_m.group('reason')}"
            if "ActivityManager" in curr or "ANR" in curr or "Load:" in curr or "CPU usage" in curr:
                stack_trace.append(stripped)
                idx += 1
            else:
                break

        crash = CrashDetail(
            crash_type="ANR",
            reason=reason,
            timestamp=timestamp,
            process_name=process_name,
            stack_trace=stack_trace
        )
        return crash, idx
