"""Unit tests for APK parser."""

import os
import tempfile
import zipfile
import pytest
from android_testing_engine.apk_parser import parse_apk, BinaryXmlParser


def test_missing_apk_raises():
    with pytest.raises(FileNotFoundError):
        parse_apk("non_existent_file_path_12345.apk")


def test_synthetic_apk_heuristic_fallback():
    """Tests the heuristic string fallback when binary XML is non-standard or compressed."""
    with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tmp:
        apk_path = tmp.name

    try:
        # Create a valid zip with AndroidManifest.xml containing package string
        with zipfile.ZipFile(apk_path, "w") as z:
            dummy_manifest = b"\x00\x00\x08\x00com.example.bharatsim.testapp\x00\x00"
            z.writestr("AndroidManifest.xml", dummy_manifest)

        meta = parse_apk(apk_path)
        assert meta.package_name == "com.example.bharatsim.testapp"
    finally:
        if os.path.exists(apk_path):
            os.remove(apk_path)
