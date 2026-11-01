import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ANDROID_SOURCE = (
    REPOSITORY_ROOT
    / "smoke-android"
    / "app"
    / "src"
    / "main"
    / "java"
    / "org"
    / "bharatsim"
    / "smokeapp"
    / "MainActivity.java"
)


class AndroidConnectSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ANDROID_SOURCE.read_text(encoding="utf-8")

    def test_http_connect_request_uses_real_crlf_escapes(self):
        self.assertIn(r'HTTP/1.1\r\n', self.source)
        self.assertIn(r'Host: " + host + ":" + port + "\r\n', self.source)
        self.assertIn(r'Proxy-Connection: Keep-Alive\r\n\r\n', self.source)
        self.assertNotIn(r'HTTP/1.1\\r\\n', self.source)

    def test_http_connect_uses_plain_socket_not_java_http_proxy_socket(self):
        self.assertIn("try (Socket raw = new Socket())", self.source)
        self.assertIn("raw.connect(", self.source)
        self.assertNotIn("new Socket(httpProxy)", self.source)
        self.assertNotIn("Proxy.Type.HTTP", self.source)


if __name__ == "__main__":
    unittest.main()
