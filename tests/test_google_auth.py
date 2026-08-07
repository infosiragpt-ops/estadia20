from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from vps import server as roomies_server


class QuietHandler(roomies_server.Roomies20Handler):
    def log_message(self, format_string: str, *args: object) -> None:
        return


class GoogleAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        data_directory = Path(cls.temporary_directory.name) / "data"
        roomies_server.DATA_DIR = data_directory
        roomies_server.DATABASE_PATH = data_directory / "roomies20.sqlite3"
        roomies_server.UPLOADS_DIR = data_directory / "uploads"
        roomies_server.PUBLIC_DIR = Path(cls.temporary_directory.name) / "public"
        roomies_server.GOOGLE_VENDOR_DIR = roomies_server.PUBLIC_DIR / ".server_vendor"
        roomies_server.GOOGLE_CLIENT_ID = "test-client.apps.googleusercontent.com"
        roomies_server.OWNER_EMAIL = "infosiragpt@gmail.com"
        roomies_server.initialize_database()

        cls.original_verifier = roomies_server.verify_google_credential
        cls.http_server = roomies_server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.server_thread = threading.Thread(target=cls.http_server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.host, cls.port = cls.http_server.server_address

    @classmethod
    def tearDownClass(cls) -> None:
        roomies_server.verify_google_credential = cls.original_verifier
        cls.http_server.shutdown()
        cls.http_server.server_close()
        cls.server_thread.join(timeout=3)
        cls.temporary_directory.cleanup()

    def request(self, method: str, path: str, payload: dict | None = None, cookie: str = ""):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if cookie:
            headers["Cookie"] = cookie
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = json.loads(response.read())
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_body, response_headers

    def test_google_owner_gets_admin_session_and_is_reused(self) -> None:
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-owner-123",
            "email": "infosiragpt@gmail.com",
            "email_verified": True,
            "name": "Jorge Carrera",
            "picture": "https://example.com/avatar.jpg",
        }

        status, payload, headers = self.request(
            "POST", "/api/auth/google", {"credential": "signed-google-token"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["email"], "infosiragpt@gmail.com")
        self.assertEqual(payload["user"]["role"], "admin")
        self.assertEqual(payload["user"]["authProvider"], "google")

        session_cookie = headers["Set-Cookie"].split(";", 1)[0]
        me_status, me_payload, _ = self.request("GET", "/api/auth/me", cookie=session_cookie)
        self.assertEqual(me_status, 200)
        self.assertEqual(me_payload["user"]["role"], "admin")

        second_status, _, _ = self.request(
            "POST", "/api/auth/google", {"credential": "signed-google-token"}
        )
        self.assertEqual(second_status, 200)
        with roomies_server.connect() as database:
            account_count = database.execute(
                "SELECT COUNT(*) FROM users WHERE google_sub = ?", ("google-owner-123",)
            ).fetchone()[0]
        self.assertEqual(account_count, 1)

    def test_google_config_is_public_and_invalid_token_is_rejected(self) -> None:
        status, payload, _ = self.request("GET", "/api/auth/config")
        self.assertEqual(status, 200)
        self.assertTrue(payload["googleEnabled"])
        self.assertEqual(payload["googleClientId"], roomies_server.GOOGLE_CLIENT_ID)

        def reject(_: str):
            raise ValueError("invalid")

        roomies_server.verify_google_credential = reject
        invalid_status, invalid_payload, _ = self.request(
            "POST", "/api/auth/google", {"credential": "invalid-token"}
        )
        self.assertEqual(invalid_status, 401)
        self.assertIn("validar", invalid_payload["error"])


if __name__ == "__main__":
    unittest.main()
