import unittest
import urllib.request

from worker.agent import NoRedirectHandler, WorkerError, resolve_api_url


class WorkerRedirectSecurityTests(unittest.TestCase):
    def test_credential_bearing_requests_are_not_redirected(self):
        handler = NoRedirectHandler()
        request = urllib.request.Request("https://bharatsim.example/internal/worker/claim")
        redirected = handler.redirect_request(
            request, None, 302, "Found", {"Location": "https://attacker.example/steal"}, 
            "https://attacker.example/steal",
        )
        self.assertIsNone(redirected)


class WorkerApiUrlSecurityTests(unittest.TestCase):
    def test_accepts_internal_relative_worker_paths(self):
        self.assertEqual(
            resolve_api_url("https://api.example/base", "/internal/worker/claim"),
            "https://api.example/internal/worker/claim",
        )

    def test_rejects_absolute_external_urls(self):
        for path in (
            "https://attacker.example/internal/worker/claim",
            "//attacker.example/internal/worker/claim",
            "http://api.example/internal/worker/claim",
            "https://user:pass@api.example/internal/worker/claim",
        ):
            with self.subTest(path=path), self.assertRaises(WorkerError):
                resolve_api_url("https://api.example", path)

    def test_rejects_non_worker_routes_and_fragments(self):
        for path in ("/api/v1/runs", "/internal/admin/secrets", "/internal/worker/claim#fragment"):
            with self.subTest(path=path), self.assertRaises(WorkerError):
                resolve_api_url("https://api.example", path)


if __name__ == "__main__":
    unittest.main()
