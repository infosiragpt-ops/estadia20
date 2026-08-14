from __future__ import annotations

import base64
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


class AdminApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        data_directory = Path(cls.temporary_directory.name) / "data"
        roomies_server.DATA_DIR = data_directory
        roomies_server.DATABASE_PATH = data_directory / "estadia20.sqlite3"
        roomies_server.UPLOADS_DIR = data_directory / "uploads"
        roomies_server.PUBLIC_DIR = Path(cls.temporary_directory.name) / "public"
        roomies_server.OWNER_EMAIL = "carrerajorge874@gmail.com"
        roomies_server._RATE_LIMIT_BUCKETS.clear()
        roomies_server.initialize_database()

        cls.http_server = roomies_server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.server_thread = threading.Thread(target=cls.http_server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.host, cls.port = cls.http_server.server_address

    @classmethod
    def tearDownClass(cls) -> None:
        cls.http_server.shutdown()
        cls.http_server.server_close()
        cls.server_thread.join(timeout=3)
        cls.temporary_directory.cleanup()

    def setUp(self) -> None:
        roomies_server._RATE_LIMIT_BUCKETS.clear()

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        cookie: str = "",
    ):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        body = json.dumps(payload).encode() if payload is not None else None
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw_body = response.read()
        response_payload = json.loads(raw_body) if raw_body else None
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_payload, response_headers

    def register(self, name: str, email: str) -> str:
        status, _, headers = self.request(
            "POST",
            "/api/auth/register",
            {"name": name, "email": email, "password": "clave-segura-123"},
        )
        self.assertEqual(status, 201)
        return headers["Set-Cookie"].split(";", 1)[0]

    def create_listing(self, cookie: str, title: str) -> int:
        status, payload, _ = self.request(
            "POST",
            "/api/listings",
            {
                "category": "Roomies",
                "title": title,
                "location": "Lince, Lima",
                "description": "Habitación de prueba con buena luz.",
                "ownerName": "Prueba",
                "ownerWhatsApp": "51999000111",
                "price": 700,
            },
            cookie=cookie,
        )
        self.assertEqual(status, 201)
        return int(payload["listing"]["id"])

    def promote_to_admin(self, email: str) -> None:
        with roomies_server.connect() as database:
            database.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))

    def test_owner_role_is_synced_on_startup(self) -> None:
        with roomies_server.connect() as database:
            database.execute(
                """
                INSERT INTO users (name, email, password_hash, auth_provider, role)
                VALUES ('Dueño', 'carrerajorge874@gmail.com', '', 'google', 'user'),
                       ('Antiguo', 'antiguo-admin@example.com', '', 'password', 'admin')
                """
            )
        try:
            roomies_server.initialize_database()
            with roomies_server.connect() as database:
                owner_role = database.execute(
                    "SELECT role FROM users WHERE email = 'carrerajorge874@gmail.com'"
                ).fetchone()["role"]
                old_role = database.execute(
                    "SELECT role FROM users WHERE email = 'antiguo-admin@example.com'"
                ).fetchone()["role"]
            self.assertEqual(owner_role, "admin")
            self.assertEqual(old_role, "user")
        finally:
            with roomies_server.connect() as database:
                database.execute(
                    """
                    DELETE FROM users WHERE email IN
                      ('carrerajorge874@gmail.com', 'antiguo-admin@example.com')
                    """
                )

    def test_admin_endpoints_require_admin_role(self) -> None:
        status, payload, _ = self.request("GET", "/api/admin/overview")
        self.assertEqual(status, 401)
        self.assertEqual(payload["code"], "unauthorized")

        cookie = self.register("Usuaria", "usuaria@example.com")
        status, payload, _ = self.request("GET", "/api/admin/overview", cookie=cookie)
        self.assertEqual(status, 403)
        self.assertEqual(payload["code"], "forbidden")

    def test_admin_can_see_overview_listings_users_and_inquiries(self) -> None:
        admin_cookie = self.register("Admin", "admin-panel@example.com")
        self.promote_to_admin("admin-panel@example.com")
        listing_id = self.create_listing(admin_cookie, "Cuarto para overview")
        status, _, _ = self.request(
            "POST", "/api/inquiries", {"listingId": listing_id, "channel": "whatsapp"}
        )
        self.assertEqual(status, 201)

        status, payload, _ = self.request("GET", "/api/admin/overview", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(payload["stats"]["listings"], 1)
        self.assertGreaterEqual(payload["stats"]["users"], 1)
        self.assertGreaterEqual(payload["stats"]["inquiries"], 1)
        self.assertIn("byCategory", payload["stats"])
        self.assertTrue(payload["recentListings"])

        status, payload, _ = self.request(
            "GET", "/api/admin/listings?pageSize=5", cookie=admin_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["listings"])
        self.assertIn("ownerEmail", payload["listings"][0])
        self.assertIn("inquiries", payload["listings"][0])
        self.assertIn("createdAt", payload["listings"][0])

        status, payload, _ = self.request("GET", "/api/admin/users", cookie=admin_cookie)
        self.assertEqual(status, 200)
        emails = [user["email"] for user in payload["users"]]
        self.assertIn("admin-panel@example.com", emails)
        admin_row = next(
            user for user in payload["users"] if user["email"] == "admin-panel@example.com"
        )
        self.assertIsNotNone(admin_row["lastLoginAt"])
        self.assertEqual(admin_row["lastLoginProvider"], "password")
        self.assertGreaterEqual(admin_row["listingsByCategory"].get("Roomies", 0), 1)

        status, payload, _ = self.request("GET", "/api/admin/inquiries", cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertTrue(payload["recent"])
        self.assertTrue(payload["byListing"])

    def test_admin_activity_feed_shows_logins_and_new_listings(self) -> None:
        status, payload, _ = self.request("GET", "/api/admin/activity")
        self.assertEqual(status, 401)

        visitor_cookie = self.register("Visitante", "visitante-actividad@example.com")
        status, payload, _ = self.request(
            "GET", "/api/admin/activity", cookie=visitor_cookie
        )
        self.assertEqual(status, 403)

        publisher_cookie = self.register("Publicadora", "publicadora-actividad@example.com")
        listing_id = self.create_listing(publisher_cookie, "Cuarto para actividad")

        admin_cookie = self.register("Admin Actividad", "admin-actividad@example.com")
        self.promote_to_admin("admin-actividad@example.com")

        status, payload, _ = self.request("GET", "/api/admin/activity", cookie=admin_cookie)
        self.assertEqual(status, 200)
        events = payload["events"]
        self.assertTrue(events)

        logins = [event for event in events if event["type"] == "login"]
        login_emails = [event["email"] for event in logins]
        self.assertIn("publicadora-actividad@example.com", login_emails)
        publisher_login = next(
            event for event in logins
            if event["email"] == "publicadora-actividad@example.com"
        )
        self.assertEqual(publisher_login["provider"], "password")
        self.assertEqual(publisher_login["name"], "Publicadora")
        self.assertIn("createdAt", publisher_login)

        listings = [event for event in events if event["type"] == "listing"]
        published = next(
            event for event in listings if event["listingId"] == listing_id
        )
        self.assertEqual(published["email"], "publicadora-actividad@example.com")
        self.assertEqual(published["category"], "Roomies")
        self.assertEqual(published["title"], "Cuarto para actividad")

        timestamps = [str(event["createdAt"]) for event in events]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_owner_can_edit_and_delete_only_their_listing(self) -> None:
        owner_cookie = self.register("Dueña", "duena@example.com")
        stranger_cookie = self.register("Otra", "otra@example.com")
        listing_id = self.create_listing(owner_cookie, "Cuarto editable")

        status, payload, _ = self.request(
            "PATCH",
            f"/api/listings/{listing_id}",
            {"title": "Cuarto renovado", "price": 850},
            cookie=stranger_cookie,
        )
        self.assertEqual(status, 403)

        status, payload, _ = self.request(
            "PATCH",
            f"/api/listings/{listing_id}",
            {"title": "Cuarto renovado", "price": 850, "badge": "Destacado"},
            cookie=owner_cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["listing"]["title"], "Cuarto renovado")
        self.assertEqual(payload["listing"]["price"], 850)
        self.assertIsNone(payload["listing"]["badge"])  # badge es solo para admin

        status, payload, _ = self.request(
            "DELETE", f"/api/listings/{listing_id}", cookie=stranger_cookie
        )
        self.assertEqual(status, 403)

        status, payload, _ = self.request(
            "DELETE", f"/api/listings/{listing_id}", cookie=owner_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["deleted"])

        status, _, _ = self.request(
            "DELETE", f"/api/listings/{listing_id}", cookie=owner_cookie
        )
        self.assertEqual(status, 404)

    def test_admin_can_edit_badge_and_delete_any_listing(self) -> None:
        owner_cookie = self.register("Publicador", "publicador@example.com")
        admin_cookie = self.register("Moderadora", "moderadora@example.com")
        self.promote_to_admin("moderadora@example.com")
        listing_id = self.create_listing(owner_cookie, "Cuarto moderado")

        status, _, _ = self.request(
            "POST", "/api/favorites", {"listingId": listing_id}, cookie=owner_cookie
        )
        self.assertEqual(status, 200)

        status, payload, _ = self.request(
            "PATCH",
            f"/api/listings/{listing_id}",
            {"badge": "Verificado"},
            cookie=admin_cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["listing"]["badge"], "Verificado")

        status, payload, _ = self.request(
            "DELETE", f"/api/listings/{listing_id}", cookie=admin_cookie
        )
        self.assertEqual(status, 200)
        with roomies_server.connect() as database:
            orphan_favorites = database.execute(
                "SELECT COUNT(*) FROM favorites WHERE listing_id = ?", (listing_id,)
            ).fetchone()[0]
        self.assertEqual(orphan_favorites, 0)

    def test_owner_email_cannot_be_registered_with_password(self) -> None:
        status, payload, _ = self.request(
            "POST",
            "/api/auth/register",
            {
                "name": "Impostor",
                "email": "carrerajorge874@gmail.com",
                "password": "clave-impostora-1",
            },
        )
        self.assertEqual(status, 409)
        self.assertIn("Google", payload["error"])

    def test_startup_never_promotes_password_accounts(self) -> None:
        with roomies_server.connect() as database:
            database.execute(
                """
                INSERT INTO users (name, email, password_hash, auth_provider, role)
                VALUES ('Impostora', 'carrerajorge874@gmail.com',
                        'pbkdf2_sha256$310000$x$y', 'password', 'user')
                """
            )
        try:
            roomies_server.initialize_database()
            with roomies_server.connect() as database:
                role = database.execute(
                    "SELECT role FROM users WHERE email = 'carrerajorge874@gmail.com'"
                ).fetchone()["role"]
            self.assertEqual(role, "user")
        finally:
            with roomies_server.connect() as database:
                database.execute(
                    "DELETE FROM users WHERE email = 'carrerajorge874@gmail.com'"
                )

    def test_google_link_keeps_previous_password(self) -> None:
        """Vincular Google no borra la contraseña: la cuenta conserva sus dos
        formas de entrar (Google y correo con contraseña)."""
        cookie = self.register("Previa", "reclamada@example.com")
        self.assertTrue(cookie)
        original_verifier = roomies_server.verify_google_credential
        roomies_server.verify_google_credential = lambda credential: {
            "sub": "google-claimed-1",
            "email": "reclamada@example.com",
            "email_verified": True,
            "name": "Reclamada",
            "picture": "",
        }
        try:
            status, payload, _ = self.request(
                "POST", "/api/auth/google", {"credential": "token"}
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["user"]["authProvider"], "google")
        finally:
            roomies_server.verify_google_credential = original_verifier

        status, payload, _ = self.request(
            "POST",
            "/api/auth/login",
            {"email": "reclamada@example.com", "password": "clave-segura-123"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["email"], "reclamada@example.com")

    def test_upload_accepts_multipart_image_and_serves_it_back(self) -> None:
        cookie = self.register("Fotógrafa", "fotografa@example.com")
        # PNG real de 1×1 para que el redimensionado con Pillow (si está
        # instalada) pueda decodificarlo; sin Pillow se guarda tal cual.
        png_content = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
            "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        boundary = "----estadia20boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="foto.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode() + png_content + f"\r\n--{boundary}--\r\n".encode()

        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request(
            "POST",
            "/api/uploads",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
                "Cookie": cookie,
            },
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        self.assertEqual(response.status, 201, payload)
        self.assertTrue(payload["url"].startswith("/api/uploads/"))

        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request("GET", payload["url"])
        served = connection.getresponse()
        served_bytes = served.read()
        connection.close()
        self.assertEqual(served.status, 200)
        self.assertTrue(served_bytes)
        # Con Pillow instalada la foto se re-guarda como JPEG; sin Pillow se
        # conserva el PNG original.
        self.assertTrue(
            served_bytes.startswith(b"\xff\xd8\xff") or served_bytes == png_content
        )

    def test_my_listings_returns_own_listings_with_counts(self) -> None:
        cookie = self.register("Anunciante", "anunciante@example.com")
        listing_id = self.create_listing(cookie, "Cuarto propio")
        status, _, _ = self.request(
            "POST", "/api/inquiries", {"listingId": listing_id, "channel": "whatsapp"}
        )
        self.assertEqual(status, 201)

        status, payload, _ = self.request("GET", "/api/my/listings", cookie=cookie)
        self.assertEqual(status, 200)
        ids = [listing["id"] for listing in payload["listings"]]
        self.assertIn(listing_id, ids)
        mine = next(listing for listing in payload["listings"] if listing["id"] == listing_id)
        self.assertGreaterEqual(mine["inquiries"], 1)
        self.assertIn("createdAt", mine)

        status, payload, _ = self.request("GET", "/api/my/listings")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
