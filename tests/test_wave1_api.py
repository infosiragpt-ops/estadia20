"""Pruebas de la primera ola de pulido de Llaves365: WhatsApp enmascarado,
ciclo de vida del anuncio, consultas con mensaje, reportes, recuperación de
contraseña, sitemap/robots, HEIC y validación del WhatsApp peruano."""

from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from vps import server as roomies_server

try:
    from PIL import Image
except ImportError:  # pragma: no cover - entorno sin Pillow
    Image = None

try:
    import pillow_heif
except ImportError:  # pragma: no cover - entorno sin pillow-heif
    pillow_heif = None

# PNG real de 1×1 (blanco) para subir fotos sin depender de Pillow.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
BOUNDARY = "----wave1boundary"


def multipart_body(files: list[tuple[str, bytes, str]]) -> tuple[bytes, str]:
    parts = []
    for index, (field_name, content, mime) in enumerate(files):
        parts.append(
            (
                f"--{BOUNDARY}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="foto-{index}"\r\n'
                f"Content-Type: {mime}\r\n\r\n"
            ).encode()
            + content
            + b"\r\n"
        )
    body = b"".join(parts) + f"--{BOUNDARY}--\r\n".encode()
    return body, f"multipart/form-data; boundary={BOUNDARY}"


class QuietHandler(roomies_server.Roomies20Handler):
    def log_message(self, format_string: str, *args: object) -> None:
        return


class Wave1ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        data_directory = Path(cls.temporary_directory.name) / "data"
        roomies_server.DATA_DIR = data_directory
        roomies_server.DATABASE_PATH = data_directory / "estadia20.sqlite3"
        roomies_server.UPLOADS_DIR = data_directory / "uploads"
        roomies_server.PUBLIC_DIR = Path(cls.temporary_directory.name) / "public"
        roomies_server.OWNER_EMAIL = "carrerajorge874@gmail.com"
        roomies_server.SEED_DEMO_DATA = True
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

    def request_raw(self, method: str, path: str):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request(method, path)
        response = connection.getresponse()
        raw_body = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, raw_body, response_headers

    def register(self, name: str, email: str, password: str = "clave-segura-123") -> str:
        status, _, headers = self.request(
            "POST",
            "/api/auth/register",
            {"name": name, "email": email, "password": password},
        )
        self.assertEqual(status, 201)
        return headers["Set-Cookie"].split(";", 1)[0]

    def promote_to_admin(self, email: str) -> None:
        with roomies_server.connect() as database:
            database.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))

    def create_listing(self, cookie: str, title: str, **overrides) -> dict:
        payload = {
            "category": "Roomies",
            "title": title,
            "location": "Lince, Lima",
            "description": "Habitación de prueba con buena luz.",
            "ownerName": "Prueba",
            "ownerWhatsApp": "51999000111",
            "price": 700,
        }
        payload.update(overrides)
        status, response, _ = self.request("POST", "/api/listings", payload, cookie=cookie)
        self.assertEqual(status, 201, response)
        return response["listing"]

    def upload(self, files: list[tuple[str, bytes, str]], cookie: str):
        body, content_type = multipart_body(files)
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        connection.request(
            "POST",
            "/api/uploads",
            body=body,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
                "Cookie": cookie,
            },
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    # --- WhatsApp enmascarado y revelado con consulta ---

    def test_public_listings_mask_owner_whatsapp(self) -> None:
        status, payload, _ = self.request("GET", "/api/listings?category=Roomies")
        self.assertEqual(status, 200)
        self.assertTrue(payload["listings"])
        for listing in payload["listings"]:
            self.assertTrue(listing["ownerWhatsAppMasked"], listing["title"])
            self.assertIn("•", listing["ownerWhatsApp"])
            self.assertNotRegex(listing["ownerWhatsApp"], r"^\d{11}$")

        detail_status, detail_payload, _ = self.request(
            "GET", f"/api/listings/{payload['listings'][0]['id']}"
        )
        self.assertEqual(detail_status, 200)
        self.assertTrue(detail_payload["listing"]["ownerWhatsAppMasked"])
        self.assertIn("•", detail_payload["listing"]["ownerWhatsApp"])

    def test_inquiry_reveals_whatsapp_and_stores_message(self) -> None:
        owner_cookie = self.register("Reveladora", "reveladora@example.com")
        self.promote_to_admin("reveladora@example.com")
        listing = self.create_listing(owner_cookie, "Cuarto con contacto")
        self.assertEqual(listing["status"], "published")

        status, payload, _ = self.request(
            "POST",
            "/api/inquiries",
            {
                "listingId": listing["id"],
                "channel": "whatsapp",
                "message": "¿Sigue disponible?",
                "checkIn": "2026-09-01",
                "checkOut": "2026-09-05",
                "guests": 2,
            },
        )
        self.assertEqual(status, 201, payload)
        self.assertEqual(payload["whatsapp"], "51999000111")

        # El dueño ve la consulta completa (antes GET /api/inquiries era 404).
        status, payload, _ = self.request("GET", "/api/inquiries", cookie=owner_cookie)
        self.assertEqual(status, 200)
        inquiry = next(
            row for row in payload["inquiries"] if row["listingId"] == listing["id"]
        )
        self.assertEqual(inquiry["message"], "¿Sigue disponible?")
        self.assertEqual(inquiry["checkIn"], "2026-09-01")
        self.assertEqual(inquiry["checkOut"], "2026-09-05")
        self.assertEqual(inquiry["guests"], 2)

        # Sin sesión no hay lista de consultas.
        status, _, _ = self.request("GET", "/api/inquiries")
        self.assertEqual(status, 401)

    def test_inquiry_never_reveals_demo_numbers(self) -> None:
        status, payload, _ = self.request("GET", "/api/listings?category=Roomies")
        demo = next(listing for listing in payload["listings"] if listing["isDemo"])
        status, payload, _ = self.request(
            "POST", "/api/inquiries", {"listingId": demo["id"], "channel": "whatsapp"}
        )
        self.assertEqual(status, 201)
        self.assertIsNone(payload["whatsapp"])

    # --- Ciclo de vida del anuncio ---

    def test_new_listings_start_pending_and_hidden_until_approved(self) -> None:
        cookie = self.register("Pendiente", "pendiente@example.com")
        listing = self.create_listing(cookie, "Cuarto pendiente de revisión")
        self.assertEqual(listing["status"], "pending")

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&pageSize=48"
        )
        self.assertEqual(status, 200)
        self.assertNotIn(listing["id"], [row["id"] for row in payload["listings"]])

        # El enlace compartido tampoco lo muestra a un visitante anónimo.
        status, _, _ = self.request("GET", f"/api/listings/{listing['id']}")
        self.assertEqual(status, 404)

        # El dueño sí lo ve (y con su número completo).
        status, payload, _ = self.request(
            "GET", f"/api/listings/{listing['id']}", cookie=cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["listing"]["ownerWhatsApp"], "51999000111")

        # El dueño no puede aprobarse el anuncio; el administrador sí.
        status, payload, _ = self.request(
            "PATCH", f"/api/listings/{listing['id']}", {"status": "published"}, cookie=cookie
        )
        self.assertEqual(status, 403)

        admin_cookie = self.register("Aprobadora", "aprobadora@example.com")
        self.promote_to_admin("aprobadora@example.com")
        status, payload, _ = self.request(
            "PATCH",
            f"/api/listings/{listing['id']}",
            {"status": "published"},
            cookie=admin_cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["listing"]["status"], "published")

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&pageSize=48"
        )
        self.assertIn(listing["id"], [row["id"] for row in payload["listings"]])

    def test_owner_can_pause_resume_and_mark_rented(self) -> None:
        cookie = self.register("Pausadora", "pausadora@example.com")
        self.promote_to_admin("pausadora@example.com")
        listing = self.create_listing(cookie, "Cuarto pausable")

        for next_status in ("paused", "published", "rented", "published"):
            status, payload, _ = self.request(
                "PATCH",
                f"/api/listings/{listing['id']}",
                {"status": next_status},
                cookie=cookie,
            )
            self.assertEqual(status, 200, payload)
            self.assertEqual(payload["listing"]["status"], next_status)

        status, payload, _ = self.request(
            "PATCH", f"/api/listings/{listing['id']}", {"status": "paused"}, cookie=cookie
        )
        self.assertEqual(status, 200)
        public_status, public_payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&pageSize=48"
        )
        self.assertEqual(public_status, 200)
        self.assertNotIn(
            listing["id"], [row["id"] for row in public_payload["listings"]]
        )

    def test_admin_can_filter_demo_and_real_listings(self) -> None:
        admin_cookie = self.register("Filtradora", "filtradora@example.com")
        self.promote_to_admin("filtradora@example.com")
        self.create_listing(admin_cookie, "Cuarto real para filtro")

        status, payload, _ = self.request(
            "GET", "/api/admin/listings?origin=demo&pageSize=50", cookie=admin_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["listings"])
        self.assertTrue(all(row["isDemo"] for row in payload["listings"]))

        status, payload, _ = self.request(
            "GET", "/api/admin/listings?origin=real&pageSize=50", cookie=admin_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["listings"])
        self.assertTrue(all(not row["isDemo"] for row in payload["listings"]))

    # --- Validación del WhatsApp peruano ---

    def test_publish_validates_peruvian_whatsapp(self) -> None:
        cookie = self.register("Validadora", "validadora@example.com")
        for invalid in ("12345678", "51812345678", "5199900011", "999"):
            status, payload, _ = self.request(
                "POST",
                "/api/listings",
                {
                    "category": "Roomies",
                    "title": "Cuarto inválido",
                    "location": "Lima",
                    "description": "Prueba",
                    "ownerName": "Prueba",
                    "ownerWhatsApp": invalid,
                    "price": 500,
                },
                cookie=cookie,
            )
            self.assertEqual(status, 400, invalid)
            self.assertIn("peruano", payload["error"])

        # Un celular de 9 dígitos se normaliza con el prefijo 51.
        listing = self.create_listing(
            cookie, "Cuarto normalizado", ownerWhatsApp="987 654 321"
        )
        self.assertEqual(listing["ownerWhatsApp"], "51987654321")

    # --- Fotos: propiedad, HEIC y limpieza al borrar ---

    def test_uploads_are_tied_to_the_uploader(self) -> None:
        owner_cookie = self.register("Dueña Fotos", "duena-fotos@example.com")
        thief_cookie = self.register("Ajena", "ajena-fotos@example.com")
        status, payload = self.upload([("files", TINY_PNG, "image/png")], owner_cookie)
        self.assertEqual(status, 201, payload)
        stolen_url = payload["urls"][0]

        status, payload, _ = self.request(
            "POST",
            "/api/listings",
            {
                "category": "Roomies",
                "title": "Cuarto con foto ajena",
                "location": "Lima",
                "description": "Prueba",
                "ownerName": "Prueba",
                "ownerWhatsApp": "51999000111",
                "price": 500,
                "gallery": [stolen_url],
            },
            cookie=thief_cookie,
        )
        self.assertEqual(status, 400)
        self.assertIn("no pertenece", payload["error"])

    def test_deleting_a_listing_removes_upload_files(self) -> None:
        cookie = self.register("Limpiadora", "limpiadora@example.com")
        status, payload = self.upload([("files", TINY_PNG, "image/png")], cookie)
        self.assertEqual(status, 201, payload)
        url = payload["urls"][0]
        file_path = roomies_server.upload_file_path(url)
        self.assertIsNotNone(file_path)
        self.assertTrue(file_path.is_file())

        listing = self.create_listing(cookie, "Cuarto con fotos", gallery=[url])
        status, payload, _ = self.request(
            "DELETE", f"/api/listings/{listing['id']}", cookie=cookie
        )
        self.assertEqual(status, 200)
        self.assertFalse(file_path.exists())

    @unittest.skipUnless(
        Image is not None and pillow_heif is not None, "pillow-heif no está instalada"
    )
    def test_heic_uploads_are_converted_to_jpeg(self) -> None:
        pillow_heif.register_heif_opener()
        buffer = io.BytesIO()
        Image.new("RGB", (64, 48), (180, 40, 90)).save(buffer, format="HEIF")
        heic_bytes = buffer.getvalue()
        self.assertEqual(
            roomies_server.image_extension_from_content(heic_bytes), "heic"
        )

        cookie = self.register("iPhonera", "iphonera@example.com")
        status, payload = self.upload([("files", heic_bytes, "image/heic")], cookie)
        self.assertEqual(status, 201, payload)
        self.assertTrue(payload["urls"][0].endswith(".jpg"))

    def test_broken_heic_fails_with_clear_spanish_message(self) -> None:
        cookie = self.register("Heicrota", "heic-rota@example.com")
        fake_heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64
        status, payload = self.upload([("files", fake_heic, "image/heic")], cookie)
        self.assertEqual(status, 400)
        self.assertIn("HEIC", payload["error"])
        self.assertIn("iPhone", payload["error"])

    # --- Reportes ---

    def test_reports_are_stored_and_visible_for_admin(self) -> None:
        admin_cookie = self.register("Moderadora R", "moderadora-reportes@example.com")
        self.promote_to_admin("moderadora-reportes@example.com")
        listing = self.create_listing(admin_cookie, "Cuarto reportable")

        status, payload, _ = self.request(
            "POST",
            "/api/reports",
            {"listingId": listing["id"], "reason": "numero_falso", "comment": "No contesta"},
        )
        self.assertEqual(status, 201, payload)
        self.assertTrue(payload["reported"])

        status, payload, _ = self.request(
            "POST", "/api/reports", {"listingId": listing["id"], "reason": "inventado"}
        )
        self.assertEqual(status, 400)

        status, payload, _ = self.request(
            "GET", "/api/admin/reports", cookie=admin_cookie
        )
        self.assertEqual(status, 200)
        report = next(
            row for row in payload["recent"] if row["listingId"] == listing["id"]
        )
        self.assertEqual(report["reason"], "numero_falso")
        self.assertEqual(report["comment"], "No contesta")

        status, _, _ = self.request("GET", "/api/admin/reports")
        self.assertEqual(status, 401)

    # --- Recuperar contraseña y sesiones ---

    def test_password_reset_flow_with_hashed_token(self) -> None:
        self.register("Olvidadiza", "olvidadiza@example.com")
        status, payload, _ = self.request(
            "POST", "/api/auth/password/forgot", {"email": "olvidadiza@example.com"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["requested"])
        # La respuesta nunca incluye el token (no se filtra en producción).
        self.assertNotIn("token", json.dumps(payload))

        # El mismo mensaje neutro para un correo inexistente.
        status, other, _ = self.request(
            "POST", "/api/auth/password/forgot", {"email": "no-existe@example.com"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(other["message"], payload["message"])

        with roomies_server.connect() as database:
            stored = database.execute(
                """
                SELECT password_resets.token_hash FROM password_resets
                JOIN users ON users.id = password_resets.user_id
                WHERE users.email = 'olvidadiza@example.com'
                """
            ).fetchone()
        self.assertIsNotNone(stored)

        # El token se guarda con hash; para la prueba se inserta uno conocido.
        known_token = "token-de-prueba-abcdefghijklmnopqrstuv"
        with roomies_server.connect() as database:
            user_id = database.execute(
                "SELECT id FROM users WHERE email = 'olvidadiza@example.com'"
            ).fetchone()["id"]
            database.execute(
                """
                INSERT INTO password_resets (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    hashlib.sha256(known_token.encode()).hexdigest(),
                    int(time.time()) + 600,
                ),
            )

        status, payload, _ = self.request(
            "POST",
            "/api/auth/password/reset",
            {"token": known_token, "password": "nueva-clave-456"},
        )
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["reset"])

        # La clave nueva funciona y el token no se puede reutilizar.
        status, _, _ = self.request(
            "POST",
            "/api/auth/login",
            {"email": "olvidadiza@example.com", "password": "nueva-clave-456"},
        )
        self.assertEqual(status, 200)
        status, _, _ = self.request(
            "POST",
            "/api/auth/password/reset",
            {"token": known_token, "password": "otra-clave-789"},
        )
        self.assertEqual(status, 400)

    def test_logout_all_devices_removes_every_session(self) -> None:
        first_cookie = self.register("Multisesión", "multisesion@example.com")
        status, _, headers = self.request(
            "POST",
            "/api/auth/login",
            {"email": "multisesion@example.com", "password": "clave-segura-123"},
        )
        self.assertEqual(status, 200)
        second_cookie = headers["Set-Cookie"].split(";", 1)[0]

        status, payload, _ = self.request(
            "POST", "/api/auth/logout-all", cookie=second_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["allDevices"])

        for cookie in (first_cookie, second_cookie):
            status, payload, _ = self.request("GET", "/api/auth/me", cookie=cookie)
            self.assertEqual(status, 200)
            self.assertIsNone(payload["user"])

    def test_login_events_record_ip_and_user_agent(self) -> None:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request(
            "POST",
            "/api/auth/register",
            body=json.dumps(
                {
                    "name": "Rastreada",
                    "email": "rastreada@example.com",
                    "password": "clave-segura-123",
                }
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "PruebaNavegador/1.0",
            },
        )
        response = connection.getresponse()
        response.read()
        connection.close()
        self.assertEqual(response.status, 201)
        with roomies_server.connect() as database:
            event = database.execute(
                """
                SELECT login_events.ip, login_events.user_agent
                FROM login_events JOIN users ON users.id = login_events.user_id
                WHERE users.email = 'rastreada@example.com'
                ORDER BY login_events.id DESC LIMIT 1
                """
            ).fetchone()
        self.assertEqual(event["user_agent"], "PruebaNavegador/1.0")
        self.assertTrue(event["ip"])

    # --- Filtros de búsqueda ---

    def test_roomies_filters_use_structured_details(self) -> None:
        cookie = self.register("Filtro Roomies", "filtro-roomies@example.com")
        self.promote_to_admin("filtro-roomies@example.com")
        private = self.create_listing(
            cookie,
            "Cuarto con baño privado",
            details={"bathroom": "Privado", "bed": "2 plazas", "furnished": True, "servicesIncluded": True},
        )
        shared = self.create_listing(
            cookie,
            "Cuarto con baño compartido",
            details={"bathroom": "Compartido", "bed": "1 plaza", "furnished": False, "servicesIncluded": False},
        )

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&bathroom=Privado&pageSize=48"
        )
        self.assertEqual(status, 200)
        ids = [row["id"] for row in payload["listings"]]
        self.assertIn(private["id"], ids)
        self.assertNotIn(shared["id"], ids)

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&servicesIncluded=1&pageSize=48"
        )
        self.assertEqual(status, 200)
        ids = [row["id"] for row in payload["listings"]]
        self.assertIn(private["id"], ids)
        self.assertNotIn(shared["id"], ids)

    def test_stay_filters_apply_guests_and_amenities(self) -> None:
        cookie = self.register("Filtro Estadías", "filtro-estadias@example.com")
        self.promote_to_admin("filtro-estadias@example.com")
        big = self.create_listing(
            cookie,
            "Casa amplia con piscina",
            category="Airbnb",
            details={"guests": 8, "bedrooms": 3, "beds": 4, "bathrooms": 2, "amenities": ["Wifi", "Piscina"]},
        )
        small = self.create_listing(
            cookie,
            "Mini estudio céntrico",
            category="Airbnb",
            details={"guests": 2, "bedrooms": 1, "beds": 1, "bathrooms": 1, "amenities": ["Cocina"]},
        )

        status, payload, _ = self.request(
            "GET",
            "/api/listings?category=Estad%C3%ADas&guests=4"
            "&checkIn=2026-10-01&checkOut=2026-10-04&pageSize=48",
        )
        self.assertEqual(status, 200, payload)
        ids = [row["id"] for row in payload["listings"]]
        self.assertIn(big["id"], ids)
        self.assertNotIn(small["id"], ids)
        # Los anuncios sin capacidad registrada (demos) no se ocultan.
        self.assertTrue(any(row["isDemo"] for row in payload["listings"]))

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Airbnb&amenities=Piscina&pageSize=48"
        )
        self.assertEqual(status, 200)
        ids = [row["id"] for row in payload["listings"]]
        self.assertIn(big["id"], ids)
        self.assertNotIn(small["id"], ids)

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Airbnb&checkIn=2026-10-04&checkOut=2026-10-01"
        )
        self.assertEqual(status, 400)

    # --- SEO, salud y usuarios del panel ---

    def test_sitemap_and_robots_are_not_spa_html(self) -> None:
        status, body, headers = self.request_raw("GET", "/sitemap.xml")
        self.assertEqual(status, 200)
        self.assertIn("application/xml", headers["Content-Type"])
        self.assertIn(b"<urlset", body)
        self.assertIn(b"https://llaves365.com/", body)
        self.assertIn(b"?category=", body)
        self.assertIn(b"?listing=", body)
        self.assertNotIn(b"<html", body)

        status, body, headers = self.request_raw("GET", "/robots.txt")
        self.assertEqual(status, 200)
        self.assertIn("text/plain", headers["Content-Type"])
        self.assertIn(b"Sitemap: https://llaves365.com/sitemap.xml", body)
        self.assertNotIn(b"<html", body)

    def test_pending_listings_are_not_in_the_sitemap(self) -> None:
        cookie = self.register("Sitemap Pendiente", "sitemap-pendiente@example.com")
        listing = self.create_listing(cookie, "Cuarto fuera del sitemap")
        status, body, _ = self.request_raw("GET", "/sitemap.xml")
        self.assertEqual(status, 200)
        self.assertNotIn(f"?listing={listing['id']}<".encode(), body)

    def test_health_reports_uploads_and_version(self) -> None:
        status, payload, _ = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["database"])
        self.assertIn("uploads", payload)
        self.assertIn("uploadsFreeBytes", payload)
        self.assertIn("version", payload)

    def test_admin_users_supports_search_and_pagination(self) -> None:
        admin_cookie = self.register("Buscadora", "buscadora-usuarios@example.com")
        self.promote_to_admin("buscadora-usuarios@example.com")
        for index in range(3):
            self.register(f"Paginada {index}", f"paginada-{index}@example.com")

        status, payload, _ = self.request(
            "GET", "/api/admin/users?pageSize=2&page=1", cookie=admin_cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["users"]), 2)
        self.assertGreaterEqual(payload["meta"]["totalPages"], 2)
        self.assertTrue(payload["meta"]["hasMore"])

        status, payload, _ = self.request(
            "GET", "/api/admin/users?q=buscadora", cookie=admin_cookie
        )
        self.assertEqual(status, 200)
        emails = [user["email"] for user in payload["users"]]
        self.assertEqual(emails, ["buscadora-usuarios@example.com"])


if __name__ == "__main__":
    unittest.main()
