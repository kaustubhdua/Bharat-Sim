#!/usr/bin/env python3
"""Small W3C WebDriver journey against the known-good BharatSim fixture app."""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:4723"


def request(method: str, path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if isinstance(result, dict) and isinstance(result.get("value"), dict) and result["value"].get("error"):
        raise RuntimeError(f"WebDriver error: {result['value']}")
    return result


def wait_for_server() -> None:
    deadline = time.monotonic() + 90
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            request("GET", "/status", timeout=3)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Appium server did not become ready: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    wait_for_server()
    created = request("POST", "/session", {
        "capabilities": {
            "alwaysMatch": {
                "platformName": "Android",
                "appium:automationName": "UiAutomator2",
                "appium:deviceName": "emulator-5554",
                "appium:appPackage": "org.bharatsim.smokeapp",
                "appium:appActivity": ".MainActivity",
                "appium:noReset": True,
                "appium:newCommandTimeout": 60,
            },
            "firstMatch": [{}],
        }
    }, timeout=120)
    value = created.get("value", {})
    session_id = created.get("sessionId") or value.get("sessionId")
    if not session_id:
        raise RuntimeError(f"Appium did not return a session id: {created}")
    base = f"/session/{session_id}"
    try:
        title = request("POST", base + "/element", {
            "using": "-android uiautomator",
            "value": 'new UiSelector().text("BharatSim Android smoke test")',
        })
        title_id = title.get("value", {}).get("element-6066-11e4-a52e-4f735466cecf")
        if not title_id:
            raise RuntimeError(f"Fixture title was not found: {title}")
        action = request("POST", base + "/element", {
            "using": "-android uiautomator",
            "value": 'new UiSelector().text("Run primary action")',
        })
        action_id = action.get("value", {}).get("element-6066-11e4-a52e-4f735466cecf")
        if not action_id:
            raise RuntimeError(f"Primary action button was not found: {action}")
        request("POST", base + f"/element/{action_id}/click", {})
        status = request("POST", base + "/element", {
            "using": "-android uiautomator",
            "value": 'new UiSelector().text("Primary action completed")',
        })
        status_id = status.get("value", {}).get("element-6066-11e4-a52e-4f735466cecf")
        if not status_id:
            raise RuntimeError(f"Primary action state assertion failed: {status}")
        screenshot = request("GET", base + "/screenshot")
        image_data = screenshot.get("value")
        if not isinstance(image_data, str) or not image_data:
            raise RuntimeError("Appium screenshot response was empty")
        screenshot_path = args.artifacts / "appium-primary-action.png"
        screenshot_path.write_bytes(base64.b64decode(image_data, validate=True))
        report = {
            "status": "passed",
            "session_id": session_id,
            "package_name": "org.bharatsim.smokeapp",
            "assertions": [
                "fixture title is visible",
                "primary action button is visible",
                "click changes status to Primary action completed",
            ],
            "screenshot": str(screenshot_path),
        }
        (args.artifacts / "appium-journey.report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        try:
            request("DELETE", base, timeout=15)
        except Exception as exc:
            print(f"warning: could not close Appium session cleanly: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
