"""Unit tests for CrashDetector."""

from android_testing_engine.crash_detector import CrashDetector


SAMPLE_FATAL_LOGCAT = """
10-31 12:00:00.100  1000  1000 D AppStart: Launching main activity
10-31 12:00:01.200  1500  1500 E AndroidRuntime: FATAL EXCEPTION: main
10-31 12:00:01.200  1500  1500 E AndroidRuntime: Process: com.cheapapp.demo, PID: 1500
10-31 12:00:01.200  1500  1500 E AndroidRuntime: java.lang.NullPointerException: Attempt to invoke virtual method 'void android.widget.TextView.setText(java.lang.CharSequence)' on a null object reference
10-31 12:00:01.200  1500  1500 E AndroidRuntime: 	at com.cheapapp.demo.MainActivity.onCreate(MainActivity.java:32)
10-31 12:00:01.200  1500  1500 E AndroidRuntime: 	at android.app.Activity.performCreate(Activity.java:8000)
10-31 12:00:01.205  1000  1200 I ActivityManager: Process com.cheapapp.demo (pid 1500) has died
"""

SAMPLE_WARNINGS_ONLY = """
10-31 12:00:00.100  1000  1000 W ResourceType: Failure getting entry for 0x7f0b0021
10-31 12:00:00.110  1000  1000 W AudioTrack: AudioTrack::set: sampleRate 44100
10-31 12:00:00.120  1000  1000 W Choreographer: Skipped 30 frames! The application may be doing too much work on its main thread.
10-31 12:00:00.130  1000  1000 I System.out: User tapped button
"""

SAMPLE_NATIVE_CRASH = """
10-31 12:00:05.500  2000  2000 F libc    : Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0 in tid 2000
10-31 12:00:05.600  2100  2100 I crash_dump32: obtaining output fd from tombstoned, type: kDebuggerdNativeBacktrace
10-31 12:00:05.610  2100  2100 I crash_dump32: performing dump of process 2000
10-31 12:00:05.620  2100  2100 I DEBUG   : *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
10-31 12:00:05.620  2100  2100 I DEBUG   : pid: 2000, tid: 2000, name: com.native.app  >>> com.native.app <<<
10-31 12:00:05.620  2100  2100 I DEBUG   : signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
10-31 12:00:05.621  2100  2100 I DEBUG   :     #00 pc 0001a23b  /data/app/libnative.so
"""

SAMPLE_ANR_LOGCAT = """
10-31 12:00:10.000  1000  1100 E ActivityManager: ANR in com.slow.cheapapp (com.slow.cheapapp/.MainActivity)
10-31 12:00:10.000  1000  1100 E ActivityManager: PID: 3000
10-31 12:00:10.000  1000  1100 E ActivityManager: Reason: Input dispatching timed out (Application does not have a focused window)
10-31 12:00:10.000  1000  1100 E ActivityManager: Load: 5.12 / 4.88 / 3.20
10-31 12:00:10.000  1000  1100 E ActivityManager: CPU usage from 0ms to 5420ms later:
"""


def test_detect_fatal_exception():
    detector = CrashDetector(target_package="com.cheapapp.demo")
    crash_detected, crashes, error_logs = detector.analyze_log_content(SAMPLE_FATAL_LOGCAT)

    assert crash_detected is True
    assert len(crashes) >= 1

    fatal_crash = crashes[0]
    assert fatal_crash.crash_type == "FATAL_EXCEPTION"
    assert "NullPointerException" in fatal_crash.reason
    assert fatal_crash.process_name == "com.cheapapp.demo"
    assert fatal_crash.pid == "1500"
    assert any("MainActivity.onCreate" in line for line in fatal_crash.stack_trace)


def test_ordinary_warnings_not_classified_as_crashes():
    detector = CrashDetector(target_package="com.cheapapp.demo")
    crash_detected, crashes, error_logs = detector.analyze_log_content(SAMPLE_WARNINGS_ONLY)

    assert crash_detected is False
    assert len(crashes) == 0


def test_detect_native_crash():
    detector = CrashDetector(target_package="com.native.app")
    crash_detected, crashes, error_logs = detector.analyze_log_content(SAMPLE_NATIVE_CRASH)

    assert crash_detected is True
    assert len(crashes) >= 1
    assert "NATIVE_CRASH" in crashes[0].crash_type
    assert crashes[0].process_name == "com.native.app"


def test_detect_anr():
    detector = CrashDetector(target_package="com.slow.cheapapp")
    crash_detected, crashes, error_logs = detector.analyze_log_content(SAMPLE_ANR_LOGCAT)

    assert crash_detected is True
    assert len(crashes) >= 1
    assert crashes[0].crash_type == "ANR"
    assert "Input dispatching timed out" in crashes[0].reason


def test_target_package_isolation():
    """Crash in an unrelated app should not trigger crash if target package is set."""
    detector = CrashDetector(target_package="com.my.specialapp")
    crash_detected, crashes, error_logs = detector.analyze_log_content(SAMPLE_FATAL_LOGCAT)

    # SAMPLE_FATAL_LOGCAT is com.cheapapp.demo, so for com.my.specialapp it should NOT match
    assert crash_detected is False
    assert len(crashes) == 0
