from __future__ import annotations

import html
import http.client
import json
import re
import tempfile
import threading
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

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
        roomies_server.OWNER_EMAIL = "carrerajorge874@gmail.com"
        cls.original_oauth_hosts = roomies_server.OAUTH_REDIRECT_HOSTS
        roomies_server.OAUTH_REDIRECT_HOSTS = frozenset({"127.0.0.1"})
        roomies_server.initialize_database()

        cls.original_verifier = roomies_server.verify_google_credential
        cls.http_server = roomies_server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.server_thread = threading.Thread(target=cls.http_server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.host, cls.port = cls.http_server.server_address

    @classmethod
    def tearDownClass(cls) -> None:
        roomies_server.verify_google_credential = cls.original_verifier
        roomies_server.OAUTH_REDIRECT_HOSTS = cls.original_oauth_hosts
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

    def request_raw(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        """Solicitud sin JSON: devuelve estado, encabezados (lista) y cuerpo."""
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        raw_body = response.read()
        header_pairs = response.getheaders()
        connection.close()
        return response.status, header_pairs, raw_body

    @staticmethod
    def set_cookies(header_pairs) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for name, value in header_pairs:
            if name.lower() != "set-cookie":
                continue
            parsed = SimpleCookie(value)
            for cookie_name, morsel in parsed.items():
                cookies[cookie_name] = morsel.value
        return cookies

    @staticmethod
    def cookie_header(header_pairs, cookie_name: str) -> str:
        for name, value in header_pairs:
            if name.lower() == "set-cookie" and value.startswith(f"{cookie_name}="):
                return value
        return ""

    @staticmethod
    def cookie_headers(header_pairs, cookie_name: str) -> list[str]:
        return [
            value
            for name, value in header_pairs
            if name.lower() == "set-cookie" and value.startswith(f"{cookie_name}=")
        ]

    def assert_host_only_session_flags(self, header: str, *, same_site: str) -> None:
        lowered = header.lower()
        self.assertIn("httponly", lowered)
        self.assertIn("secure", lowered)
        self.assertIn("path=/", lowered)
        self.assertIn(f"samesite={same_site.lower()}", lowered)
        self.assertRegex(header, rf"Max-Age={roomies_server.SESSION_TTL_SECONDS}")
        self.assertNotIn("domain=", lowered)

    def google_authorize_url(self, header_pairs, body: bytes) -> str:
        refresh = ""
        for name, value in header_pairs:
            if name.lower() == "refresh" and value.startswith("0;url="):
                refresh = value.split("url=", 1)[1]
                break
        self.assertTrue(
            refresh.startswith(f"{roomies_server.GOOGLE_OAUTH_AUTHORIZE}?")
        )
        match = re.search(br'http-equiv="refresh" content="0;url=([^"]+)"', body)
        self.assertIsNotNone(match)
        self.assertEqual(html.unescape(match.group(1).decode()), refresh)
        return refresh

    def start_oauth_flow(self) -> tuple[str, str, str]:
        """Inicia /api/auth/google/start (JSON, como el botón) y devuelve
        (state, nonce, cookie)."""
        status, header_pairs, body = self.request_raw(
            "GET",
            "/api/auth/google/start",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        location = payload["authorizeUrl"]
        self.assertTrue(
            location.startswith(f"{roomies_server.GOOGLE_OAUTH_AUTHORIZE}?")
        )
        parameters = parse_qs(urlparse(location).query)
        cookie_value = self.set_cookies(header_pairs)["estadia20_oauth"]
        state, nonce = cookie_value.split(".", 1)
        self.assertEqual(parameters["state"], [state])
        self.assertEqual(parameters["nonce"], [nonce])
        return state, nonce, f"estadia20_oauth={cookie_value}"

    def post_oauth_callback(self, fields: dict[str, str], cookie: str = ""):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if cookie:
            headers["Cookie"] = cookie
        return self.request_raw(
            "POST",
            "/api/auth/google/callback",
            body=urlencode(fields).encode(),
            headers=headers,
        )

    def test_google_owner_gets_admin_session_and_is_reused(self) -> None:
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-owner-123",
            "email": "carrerajorge874@gmail.com",
            "email_verified": True,
            "name": "Jorge Carrera",
            "picture": "https://example.com/avatar.jpg",
        }

        status, payload, headers = self.request(
            "POST", "/api/auth/google", {"credential": "signed-google-token"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["email"], "carrerajorge874@gmail.com")
        self.assertEqual(payload["user"]["role"], "admin")
        self.assertEqual(payload["user"]["authProvider"], "google")

        session_cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertTrue(session_cookie.startswith("estadia20_session="))
        self.assert_host_only_session_flags(headers["Set-Cookie"], same_site="Lax")
        me_status, me_payload, _ = self.request("GET", "/api/auth/me", cookie=session_cookie)
        self.assertEqual(me_status, 200)
        self.assertEqual(me_payload["user"]["role"], "admin")
        self.assertEqual(me_payload["user"]["name"], "Jorge Carrera")

        second_status, _, _ = self.request(
            "POST", "/api/auth/google", {"credential": "signed-google-token"}
        )
        self.assertEqual(second_status, 200)
        with roomies_server.connect() as database:
            account_count = database.execute(
                "SELECT COUNT(*) FROM users WHERE google_sub = ?", ("google-owner-123",)
            ).fetchone()[0]
        self.assertEqual(account_count, 1)

    def test_google_login_records_last_login_and_activity(self) -> None:
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-activity-9",
            "email": "actividad@example.com",
            "email_verified": True,
            "name": "Cuenta Actividad",
            "picture": "",
        }
        status, _, _ = self.request(
            "POST", "/api/auth/google", {"credential": "signed-google-token"}
        )
        self.assertEqual(status, 200)
        with roomies_server.connect() as database:
            user = database.execute(
                """
                SELECT id, last_login_at, last_login_provider
                FROM users WHERE email = 'actividad@example.com'
                """
            ).fetchone()
            self.assertIsNotNone(user["last_login_at"])
            self.assertEqual(user["last_login_provider"], "google")
            events = database.execute(
                "SELECT provider FROM login_events WHERE user_id = ?", (user["id"],)
            ).fetchall()
        self.assertEqual([event["provider"] for event in events], ["google"])

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

    def test_google_start_redirects_with_expected_parameters(self) -> None:
        status, header_pairs, body = self.request_raw("GET", "/api/auth/google/start")
        self.assertEqual(status, 200)
        location = self.google_authorize_url(header_pairs, body)
        parameters = parse_qs(urlparse(location).query)
        self.assertEqual(parameters["client_id"], [roomies_server.GOOGLE_CLIENT_ID])
        self.assertEqual(
            parameters["redirect_uri"],
            ["https://127.0.0.1/api/auth/google/callback"],
        )
        self.assertEqual(parameters["response_type"], ["id_token"])
        self.assertEqual(parameters["response_mode"], ["form_post"])
        self.assertEqual(parameters["scope"], ["openid email profile"])
        self.assertNotIn("prompt", parameters)
        self.assertTrue(parameters["state"][0])
        self.assertTrue(parameters["nonce"][0])
        oauth_header = self.cookie_header(header_pairs, "estadia20_oauth")
        oauth_cookie = self.set_cookies(header_pairs)["estadia20_oauth"]
        self.assertRegex(oauth_cookie, r"^[A-Za-z0-9_-]{16,64}\.[A-Za-z0-9_-]{16,64}$")
        self.assertIn("SameSite=None", oauth_header)
        self.assertIn("HttpOnly", oauth_header)
        self.assertIn("Secure", oauth_header)
        self.assertIn("Path=/", oauth_header)

    def test_google_start_json_sets_oauth_cookie_without_bounce(self) -> None:
        status, header_pairs, body = self.request_raw(
            "GET",
            "/api/auth/google/start",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        parameters = parse_qs(urlparse(payload["authorizeUrl"]).query)
        self.assertEqual(parameters["client_id"], [roomies_server.GOOGLE_CLIENT_ID])
        self.assertNotIn("prompt", parameters)
        self.assertFalse(any(name.lower() == "refresh" for name, _ in header_pairs))
        self.assertFalse(any(name.lower() == "location" for name, _ in header_pairs))
        oauth_header = self.cookie_header(header_pairs, "estadia20_oauth")
        self.assertIn("SameSite=None", oauth_header)
        self.assertIn("HttpOnly", oauth_header)
        self.assertIn("Secure", oauth_header)
        cookie_value = self.set_cookies(header_pairs)["estadia20_oauth"]
        state, nonce = cookie_value.split(".", 1)
        self.assertEqual(parameters["state"], [state])
        self.assertEqual(parameters["nonce"], [nonce])

    def test_google_start_ignores_unknown_hosts_for_redirect_uri(self) -> None:
        status, header_pairs, body = self.request_raw(
            "GET",
            "/api/auth/google/start",
            headers={"Host": "atacante.example", "Accept": "application/json"},
        )
        self.assertEqual(status, 200)
        parameters = parse_qs(urlparse(json.loads(body)["authorizeUrl"]).query)
        self.assertEqual(
            parameters["redirect_uri"],
            [f"https://{roomies_server.OAUTH_DEFAULT_HOST}/api/auth/google/callback"],
        )

    def test_google_callback_grants_admin_session_and_redirects_home(self) -> None:
        state, nonce, cookie = self.start_oauth_flow()
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-owner-callback",
            "email": "carrerajorge874@gmail.com",
            "email_verified": True,
            "name": "Jorge Carrera",
            "picture": "https://example.com/avatar.jpg",
            "nonce": nonce,
        }
        status, header_pairs, body = self.post_oauth_callback(
            {"id_token": "signed-google-token", "state": state}, cookie=cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(dict(header_pairs)["Refresh"], "0;url=/?auth=google-ok")
        self.assertIn(b'url=/?auth=google-ok', body)
        cookies = self.set_cookies(header_pairs)
        session_token = cookies.get("estadia20_session", "")
        self.assertTrue(session_token)
        self.assertEqual(cookies.get("estadia20_oauth"), "")
        self.assert_host_only_session_flags(
            self.cookie_header(header_pairs, "estadia20_session"),
            same_site="None",
        )

        me_status, me_payload, _ = self.request(
            "GET", "/api/auth/me", cookie=f"estadia20_session={session_token}"
        )
        self.assertEqual(me_status, 200)
        self.assertEqual(me_payload["user"]["email"], "carrerajorge874@gmail.com")
        self.assertEqual(me_payload["user"]["role"], "admin")
        self.assertEqual(me_payload["user"]["authProvider"], "google")
        reload_status, reload_payload, _ = self.request(
            "GET", "/api/auth/me", cookie=f"estadia20_session={session_token}"
        )
        self.assertEqual(reload_status, 200)
        self.assertEqual(reload_payload["user"]["email"], "carrerajorge874@gmail.com")

    def test_google_callback_rejects_state_mismatch(self) -> None:
        _, nonce, cookie = self.start_oauth_flow()
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-callback-state",
            "email": "estado@example.com",
            "email_verified": True,
            "name": "Estado Incorrecto",
            "picture": "",
            "nonce": nonce,
        }
        status, header_pairs, _ = self.post_oauth_callback(
            {"id_token": "signed-google-token", "state": "estado-falsificado"},
            cookie=cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(dict(header_pairs)["Refresh"], "0;url=/?auth=google-error")
        self.assertNotIn("estadia20_session", self.set_cookies(header_pairs))

    def test_google_callback_rejects_nonce_mismatch_and_missing_cookie(self) -> None:
        state, _, cookie = self.start_oauth_flow()
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-callback-nonce",
            "email": "nonce@example.com",
            "email_verified": True,
            "name": "Nonce Incorrecto",
            "picture": "",
            "nonce": "otro-nonce",
        }
        status, header_pairs, _ = self.post_oauth_callback(
            {"id_token": "signed-google-token", "state": state}, cookie=cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(dict(header_pairs)["Refresh"], "0;url=/?auth=google-error")
        self.assertNotIn("estadia20_session", self.set_cookies(header_pairs))

        no_cookie_status, no_cookie_headers, _ = self.post_oauth_callback(
            {"id_token": "signed-google-token", "state": state}
        )
        self.assertEqual(no_cookie_status, 200)
        self.assertEqual(dict(no_cookie_headers)["Refresh"], "0;url=/?auth=google-error")
        self.assertNotIn("estadia20_session", self.set_cookies(no_cookie_headers))

    def test_google_callback_get_redirects_home_without_session(self) -> None:
        status, header_pairs, _ = self.request_raw("GET", "/api/auth/google/callback")
        self.assertEqual(status, 302)
        self.assertEqual(dict(header_pairs)["Location"], "/")
        self.assertNotIn("estadia20_session", self.set_cookies(header_pairs))

    def test_logout_clears_site_session_without_touching_google(self) -> None:
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-logout-keep-idp",
            "email": "luis-sesion@example.com",
            "email_verified": True,
            "name": "Luis",
            "picture": "",
        }
        status, payload, headers = self.request(
            "POST", "/api/auth/google", {"credential": "signed-google-token"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["name"], "Luis")
        session_cookie = headers["Set-Cookie"].split(";", 1)[0]

        logout_status, logout_headers, logout_body = self.request_raw(
            "POST",
            "/api/auth/logout",
            body=b"{}",
            headers={"Content-Type": "application/json", "Cookie": session_cookie},
        )
        self.assertEqual(logout_status, 200)
        logout_payload = json.loads(logout_body)
        self.assertEqual(logout_payload, {"loggedOut": True})
        location = next(
            (value for name, value in logout_headers if name.lower() == "location"),
            "",
        )
        self.assertEqual(location, "")
        self.assertNotIn("revoke", logout_body.decode().lower())
        self.assertNotIn("accounts.google.com", logout_body.decode().lower())
        self.assertNotIn("disableAutoSelect", logout_body.decode())

        cleared = self.cookie_headers(logout_headers, "estadia20_session")
        self.assertGreaterEqual(len(cleared), 2)
        self.assertTrue(any("samesite=lax" in header.lower() for header in cleared))
        self.assertTrue(any("samesite=none" in header.lower() for header in cleared))
        self.assertTrue(all("max-age=0" in header.lower() for header in cleared))

        me_status, me_payload, _ = self.request(
            "GET", "/api/auth/me", cookie=session_cookie
        )
        self.assertEqual(me_status, 200)
        self.assertIsNone(me_payload["user"])

    def test_oauth_start_never_forces_google_reauth(self) -> None:
        source = Path(roomies_server.__file__).read_text(encoding="utf-8")
        self.assertNotRegex(source, r"""["']prompt["']\s*:\s*["'](select_account|consent|login)["']""")
        self.assertNotIn("oauth2/revoke", source)
        self.assertNotIn("accounts.google.com/Logout", source)
        self.assertIn("def send_auth_bridge", source)
        self.assertIn('session_same_site="None"', source)


if __name__ == "__main__":
    unittest.main()
