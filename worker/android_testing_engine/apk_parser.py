"""
APK Parser module for extracting package name and launchable activity.
Uses a multi-tier resolution strategy:
1. aapt / aapt2 command (if available on system/Android SDK)
2. Pure-Python Android Binary XML (AXML) parser (zero external dependencies)
3. Heuristic string extraction fallback
"""

import os
import re
import shutil
import struct
import subprocess
import zipfile
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict


@dataclass
class APKMetadata:
    package_name: Optional[str] = None
    launch_activity: Optional[str] = None
    version_code: Optional[str] = None
    version_name: Optional[str] = None
    app_label: Optional[str] = None


class BinaryXmlParser:
    """
    Lightweight, self-contained pure-Python Android Binary XML (AXML) parser.
    Extracts package name and launchable activity without external tools.
    """
    CHUNK_STRING_POOL = 0x001C0001
    CHUNK_XML_START_TAG = 0x00100102
    CHUNK_XML_END_TAG = 0x00100103

    def __init__(self, data: bytes):
        self.data = data
        self.cursor = 0
        self.strings: List[str] = []

    def parse(self) -> APKMetadata:
        metadata = APKMetadata()
        if len(self.data) < 8:
            return metadata

        try:
            magic, file_size = struct.unpack_from("<II", self.data, 0)
            if magic != 0x00080003:  # RES_XML_TYPE
                return metadata
            
            self.cursor = 8
            current_activity = None
            is_main_action = False
            is_launcher_category = False

            while self.cursor < len(self.data):
                if self.cursor + 8 > len(self.data):
                    break
                chunk_type, chunk_size = struct.unpack_from("<II", self.data, self.cursor)
                if chunk_size <= 0 or self.cursor + chunk_size > len(self.data):
                    break

                if chunk_type == self.CHUNK_STRING_POOL:
                    self._parse_string_pool(self.cursor)
                elif chunk_type == self.CHUNK_XML_START_TAG:
                    tag_name, attrs = self._parse_start_element(self.cursor)
                    if tag_name == "manifest":
                        if "package" in attrs:
                            metadata.package_name = attrs["package"]
                        if "versionCode" in attrs:
                            metadata.version_code = attrs["versionCode"]
                        if "versionName" in attrs:
                            metadata.version_name = attrs["versionName"]
                    elif tag_name in ("activity", "activity-alias"):
                        current_activity = attrs.get("name")
                        is_main_action = False
                        is_launcher_category = False
                    elif tag_name == "action":
                        if attrs.get("name") == "android.intent.action.MAIN":
                            is_main_action = True
                    elif tag_name == "category":
                        if attrs.get("name") == "android.intent.category.LAUNCHER":
                            is_launcher_category = True
                        
                    if is_main_action and is_launcher_category and current_activity:
                        if not metadata.launch_activity:
                            metadata.launch_activity = self._normalize_activity(
                                current_activity, metadata.package_name
                            )

                elif chunk_type == self.CHUNK_XML_END_TAG:
                    end_tag_name = self._parse_end_element(self.cursor)
                    if end_tag_name in ("activity", "activity-alias"):
                        current_activity = None
                        is_main_action = False
                        is_launcher_category = False

                self.cursor += chunk_size

        except Exception:
            # Fallback will handle edge cases
            pass

        return metadata

    def _normalize_activity(self, activity: str, package: Optional[str]) -> str:
        if activity.startswith(".") and package:
            return f"{package}{activity}"
        elif "." not in activity and package:
            return f"{package}.{activity}"
        return activity

    def _parse_string_pool(self, offset: int):
        try:
            (chunk_type, chunk_size, string_count, style_count,
             flags, strings_start, styles_start) = struct.unpack_from("<IIIIIII", self.data, offset)
            
            is_utf8 = bool(flags & (1 << 8))
            offsets_start = offset + 28
            pool_start = offset + strings_start

            offsets = []
            for i in range(string_count):
                str_off, = struct.unpack_from("<I", self.data, offsets_start + i * 4)
                offsets.append(str_off)

            self.strings = []
            for off in offsets:
                str_pos = pool_start + off
                if str_pos >= len(self.data):
                    self.strings.append("")
                    continue
                if is_utf8:
                    # UTF-8 encoded string pool
                    # Length header: 1-2 bytes char count, 1-2 bytes byte count
                    u8_len, skip = self._read_varint(str_pos)
                    str_pos += skip
                    b_len, skip = self._read_varint(str_pos)
                    str_pos += skip
                    s_bytes = self.data[str_pos:str_pos + b_len]
                    self.strings.append(s_bytes.decode("utf-8", errors="replace"))
                else:
                    # UTF-16LE encoded string pool
                    u16_len, = struct.unpack_from("<H", self.data, str_pos)
                    str_pos += 2
                    if u16_len & 0x8000:
                        u16_len = ((u16_len & 0x7FFF) << 16) | struct.unpack_from("<H", self.data, str_pos)[0]
                        str_pos += 2
                    byte_len = u16_len * 2
                    s_bytes = self.data[str_pos:str_pos + byte_len]
                    self.strings.append(s_bytes.decode("utf-16le", errors="replace"))
        except Exception:
            pass

    def _read_varint(self, pos: int) -> Tuple[int, int]:
        if pos >= len(self.data):
            return 0, 0
        val = self.data[pos]
        if val & 0x80:
            if pos + 1 < len(self.data):
                val2 = self.data[pos + 1]
                return ((val & 0x7F) << 8) | val2, 2
            return val & 0x7F, 1
        return val, 1

    def _parse_start_element(self, offset: int) -> Tuple[str, Dict[str, str]]:
        attrs = {}
        tag_name = ""
        try:
            (chunk_type, chunk_size, line_number, comment_idx,
             ns_idx, name_idx, attr_start, attr_size, attr_count,
             id_index, class_index, style_index) = struct.unpack_from("<IIIIIIHHHHHH", self.data, offset)

            tag_name = self._get_string(name_idx)
            attr_offset = offset + attr_start

            for i in range(attr_count):
                curr_off = attr_offset + i * attr_size
                if curr_off + 20 > len(self.data):
                    break
                (a_ns_idx, a_name_idx, a_val_str_idx,
                 a_type, a_data) = struct.unpack_from("<IIIIi", self.data, curr_off)

                a_name = self._get_string(a_name_idx)
                a_val = self._get_string(a_val_str_idx)
                if not a_val and a_type != 3:  # Not a string, could be boolean or int
                    a_val = str(a_data)
                attrs[a_name] = a_val
        except Exception:
            pass
        return tag_name, attrs

    def _parse_end_element(self, offset: int) -> str:
        try:
            chunk_type, chunk_size, line, comment, ns_idx, name_idx = struct.unpack_from(
                "<IIIIII", self.data, offset
            )
            return self._get_string(name_idx)
        except Exception:
            return ""

    def _get_string(self, idx: int) -> str:
        if 0 <= idx < len(self.strings):
            return self.strings[idx]
        return ""


def _parse_via_aapt(apk_path: str) -> Optional[APKMetadata]:
    """Tries parsing APK via aapt or aapt2 command."""
    aapt_cmd = shutil.which("aapt") or shutil.which("aapt2")
    if not aapt_cmd:
        # Check standard Android SDK locations
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if android_home:
            build_tools = os.path.join(android_home, "build-tools")
            if os.path.isdir(build_tools):
                for folder in sorted(os.listdir(build_tools), reverse=True):
                    candidate = os.path.join(build_tools, folder, "aapt.exe" if os.name == "nt" else "aapt")
                    if os.path.isfile(candidate):
                        aapt_cmd = candidate
                        break

    if not aapt_cmd:
        return None

    try:
        proc = subprocess.run(
            [aapt_cmd, "dump", "badging", apk_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if proc.returncode != 0 or not proc.stdout:
            return None

        metadata = APKMetadata()
        out = proc.stdout
        
        # package: name='com.example.app' versionCode='1' versionName='1.0'
        pkg_match = re.search(r"package:\s+name='([^']+)'", out)
        if pkg_match:
            metadata.package_name = pkg_match.group(1)
            
        vc_match = re.search(r"versionCode='([^']+)'", out)
        if vc_match:
            metadata.version_code = vc_match.group(1)
            
        vn_match = re.search(r"versionName='([^']+)'", out)
        if vn_match:
            metadata.version_name = vn_match.group(1)

        # launchable-activity: name='com.example.app.MainActivity'
        act_match = re.search(r"launchable-activity:\s+name='([^']+)'", out)
        if act_match:
            metadata.launch_activity = act_match.group(1)

        # application-label:'App'
        label_match = re.search(r"application-label:'([^']+)'", out)
        if label_match:
            metadata.app_label = label_match.group(1)

        if metadata.package_name:
            return metadata
    except Exception:
        pass
    return None


def _fallback_string_heuristic(apk_path: str) -> APKMetadata:
    """Fallback heuristic scanner for package name in AndroidManifest.xml strings."""
    metadata = APKMetadata()
    try:
        with zipfile.ZipFile(apk_path, "r") as z:
            if "AndroidManifest.xml" in z.namelist():
                content = z.read("AndroidManifest.xml")
                # Look for ASCII / UTF-8 strings resembling package names
                potential_packages = re.findall(rb"[a-zA-Z][a-zA-Z0-9_]+(?:\.[a-zA-Z][a-zA-Z0-9_]+){2,}", content)
                for candidate_b in potential_packages:
                    candidate = candidate_b.decode("ascii", errors="ignore")
                    if not candidate.startswith("android.") and not candidate.startswith("com.android."):
                        metadata.package_name = candidate
                        break
    except Exception:
        pass
    return metadata


def parse_apk(apk_path: str) -> APKMetadata:
    """
    Extracts metadata (package name, launchable activity, version) from APK.
    Guaranteed to return an APKMetadata instance.
    """
    if not os.path.isfile(apk_path):
        raise FileNotFoundError(f"APK file not found at: {apk_path}")

    # 1. Try aapt if available
    metadata = _parse_via_aapt(apk_path)
    if metadata and metadata.package_name and metadata.launch_activity:
        return metadata

    # 2. Try pure-Python AXML parser
    try:
        with zipfile.ZipFile(apk_path, "r") as z:
            if "AndroidManifest.xml" in z.namelist():
                raw_xml = z.read("AndroidManifest.xml")
                parser = BinaryXmlParser(raw_xml)
                axml_meta = parser.parse()
                if axml_meta.package_name:
                    if metadata:
                        # Combine any info from aapt
                        if not axml_meta.launch_activity:
                            axml_meta.launch_activity = metadata.launch_activity
                    return axml_meta
    except Exception:
        pass

    # 3. If aapt gave partial result, return it
    if metadata and metadata.package_name:
        return metadata

    # 4. Fallback string heuristic
    return _fallback_string_heuristic(apk_path)
