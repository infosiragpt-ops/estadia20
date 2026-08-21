"""Perfil de publicación: nombre, WhatsApp y zona se recuerdan en la cuenta
para no pedirlos otra vez. Los valores vacíos no borran lo guardado."""

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


class PublisherProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        data_directory = Path(cls.temporary_directory.name) / "data"
        roomies_server.DATA_DIR = data_directory
        roomies_server.DATABASE_PATH = data_directory / "estadia20.sqlite3"
        roomies_server.UPLOADS_DIR = data_directory / "uploads"
        roomies_server.PUBLIC_DIR = Path(cls.temporary_directory.name) / "public"
        roomies_server.OWNER_EMAIL = "carrerajorge874@gmail.com"
        roomies_server.SEED_DEMO_DATA = False
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
        connection.close()
        return response.status, response_payload

    def register(self, name: str, email: str) -> tuple[str, dict]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request(
            "POST",
            "/api/auth/register",
            body=json.dumps(
                {"name": name, "email": email, "password": "clave-segura-123"}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        cookie = response.getheader("Set-Cookie", "").split(";", 1)[0]
        connection.close()
        self.assertEqual(response.status, 201, payload)
        return cookie, payload

    def listing_payload(self, **overrides) -> dict:
        payload = {
            "category": "Roomies",
            "title": "Habitación luminosa en Lince",
            "location": "Lince, Lima",
            "description": "Habitación de prueba con buena luz y escritorio.",
            "ownerName": "Gilberto Jara",
            "ownerWhatsApp": "51999888777",
            "price": 650,
        }
        payload.update(overrides)
        return payload

    def publish_listing(self, listing_id: int) -> None:
        with roomies_server.connect() as database:
            database.execute(
                "UPDATE listings SET status = 'published' WHERE id = ?",
                (listing_id,),
            )

    def test_register_returns_empty_publisher_profile(self) -> None:
        cookie, payload = self.register("Ana Nueva", "ana-perfil@example.com")
        user = payload["user"]
        self.assertEqual(user["publisherName"], "")
        self.assertEqual(user["publisherWhatsApp"], "")
        self.assertEqual(user["publisherLocation"], "")

        status, me_payload = self.request("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(me_payload["user"]["publisherName"], "")
        status, alias_payload = self.request("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(alias_payload["user"]["email"], "ana-perfil@example.com")

    def test_publish_stores_name_whatsapp_and_zona_on_user(self) -> None:
        cookie, _ = self.register("Publicador", "perfil-publica@example.com")
        status, payload = self.request(
            "POST", "/api/listings", self.listing_payload(), cookie=cookie
        )
        self.assertEqual(status, 201, payload)
        listing = payload["listing"]
        self.assertEqual(listing["ownerName"], "Gilberto Jara")
        self.assertEqual(listing["ownerWhatsApp"], "51999888777")
        self.assertEqual(listing["location"], "Lince, Lima")

        status, me_payload = self.request("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(status, 200, me_payload)
        user = me_payload["user"]
        self.assertEqual(user["publisherName"], "Gilberto Jara")
        self.assertEqual(user["publisherWhatsApp"], "51999888777")
        self.assertEqual(user["publisherLocation"], "Lince, Lima")
        # El nombre de la cuenta no se pisa: el saludo sigue siendo el de registro.
        self.assertEqual(user["name"], "Publicador")

        # El siguiente GET /api/me (y el formulario de publicar) ven los mismos
        # campos que el cliente usa para rellenar nombre, WhatsApp y zona.
        status, alias_payload = self.request("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        form_defaults = {
            "ownerName": alias_payload["user"]["publisherName"],
            "ownerWhatsApp": alias_payload["user"]["publisherWhatsApp"],
            "location": alias_payload["user"]["publisherLocation"],
        }
        self.assertEqual(
            form_defaults,
            {
                "ownerName": "Gilberto Jara",
                "ownerWhatsApp": "51999888777",
                "location": "Lince, Lima",
            },
        )

    def test_empty_values_do_not_wipe_stored_profile(self) -> None:
        cookie, _ = self.register("Conservadora", "perfil-vacio@example.com")
        status, payload = self.request(
            "POST", "/api/listings", self.listing_payload(), cookie=cookie
        )
        self.assertEqual(status, 201, payload)

        status, patched = self.request(
            "PATCH",
            "/api/auth/me",
            {
                "publisherName": "",
                "publisherWhatsApp": "",
                "publisherLocation": "",
                "ownerName": "   ",
                "location": "",
            },
            cookie=cookie,
        )
        self.assertEqual(status, 200, patched)
        self.assertEqual(patched["user"]["publisherName"], "Gilberto Jara")
        self.assertEqual(patched["user"]["publisherWhatsApp"], "51999888777")
        self.assertEqual(patched["user"]["publisherLocation"], "Lince, Lima")

        status, me_payload = self.request("GET", "/api/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(me_payload["user"]["publisherName"], "Gilberto Jara")
        self.assertEqual(me_payload["user"]["publisherWhatsApp"], "51999888777")
        self.assertEqual(me_payload["user"]["publisherLocation"], "Lince, Lima")

    def test_patch_me_updates_only_non_empty_fields(self) -> None:
        cookie, _ = self.register("Editora", "perfil-parche@example.com")
        status, _ = self.request(
            "POST", "/api/listings", self.listing_payload(), cookie=cookie
        )
        self.assertEqual(status, 201)

        status, patched = self.request(
            "PATCH",
            "/api/me",
            {"publisherLocation": "Miraflores, Lima", "publisherName": ""},
            cookie=cookie,
        )
        self.assertEqual(status, 200, patched)
        self.assertEqual(patched["user"]["publisherName"], "Gilberto Jara")
        self.assertEqual(patched["user"]["publisherWhatsApp"], "51999888777")
        self.assertEqual(patched["user"]["publisherLocation"], "Miraflores, Lima")

        status, patched = self.request(
            "PATCH",
            "/api/auth/me",
            {"ownerWhatsApp": "999888777", "ownerName": "Gilberto J."},
            cookie=cookie,
        )
        self.assertEqual(status, 200, patched)
        self.assertEqual(patched["user"]["publisherName"], "Gilberto J.")
        self.assertEqual(patched["user"]["publisherWhatsApp"], "51999888777")
        self.assertEqual(patched["user"]["publisherLocation"], "Miraflores, Lima")

    def test_patch_me_rejects_invalid_whatsapp_without_wiping(self) -> None:
        cookie, _ = self.register("Validadora", "perfil-whatsapp@example.com")
        status, _ = self.request(
            "POST", "/api/listings", self.listing_payload(), cookie=cookie
        )
        self.assertEqual(status, 201)

        status, payload = self.request(
            "PATCH",
            "/api/auth/me",
            {"publisherWhatsApp": "12345"},
            cookie=cookie,
        )
        self.assertEqual(status, 400, payload)
        status, me_payload = self.request("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(me_payload["user"]["publisherWhatsApp"], "51999888777")

    def test_listing_edit_updates_publisher_profile(self) -> None:
        cookie, _ = self.register("Dueña", "perfil-edita@example.com")
        status, payload = self.request(
            "POST", "/api/listings", self.listing_payload(), cookie=cookie
        )
        self.assertEqual(status, 201, payload)
        listing_id = payload["listing"]["id"]

        status, updated = self.request(
            "PATCH",
            f"/api/listings/{listing_id}",
            {
                "ownerName": "Gilberto Editado",
                "ownerWhatsApp": "51991112233",
                "location": "Barranco, Lima",
            },
            cookie=cookie,
        )
        self.assertEqual(status, 200, updated)
        status, me_payload = self.request("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(me_payload["user"]["publisherName"], "Gilberto Editado")
        self.assertEqual(me_payload["user"]["publisherWhatsApp"], "51991112233")
        self.assertEqual(me_payload["user"]["publisherLocation"], "Barranco, Lima")

    def test_listing_contact_uses_publisher_whatsapp_not_site_admin(self) -> None:
        cookie, _ = self.register("Anfitriona", "contacto-publicador@example.com")
        status, payload = self.request(
            "POST",
            "/api/listings",
            self.listing_payload(ownerWhatsApp="51999888777"),
            cookie=cookie,
        )
        self.assertEqual(status, 201, payload)
        listing_id = payload["listing"]["id"]
        self.publish_listing(listing_id)

        status, inquiry = self.request(
            "POST", "/api/inquiries", {"listingId": listing_id, "channel": "whatsapp"}
        )
        self.assertEqual(status, 201, inquiry)
        self.assertEqual(inquiry["whatsapp"], "51999888777")
        self.assertNotEqual(inquiry["whatsapp"], roomies_server.SITE_CONTACT_WHATSAPP)
        self.assertEqual(inquiry["whatsappUrl"], "https://wa.me/51999888777")
        self.assertNotIn(roomies_server.SITE_CONTACT_WHATSAPP, inquiry["whatsappUrl"])

        status, me_payload = self.request("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(me_payload["user"]["publisherWhatsApp"], inquiry["whatsapp"])

    def test_inquiry_without_valid_host_whatsapp_does_not_use_admin(self) -> None:
        cookie, _ = self.register("SinNumero", "sin-whatsapp@example.com")
        status, payload = self.request(
            "POST", "/api/listings", self.listing_payload(), cookie=cookie
        )
        self.assertEqual(status, 201, payload)
        listing_id = payload["listing"]["id"]
        self.publish_listing(listing_id)
        with roomies_server.connect() as database:
            database.execute(
                "UPDATE listings SET owner_whatsapp = '' WHERE id = ?",
                (listing_id,),
            )
            database.execute(
                "UPDATE users SET publisher_whatsapp = '' WHERE email = ?",
                ("sin-whatsapp@example.com",),
            )

        status, inquiry = self.request(
            "POST", "/api/inquiries", {"listingId": listing_id, "channel": "whatsapp"}
        )
        self.assertEqual(status, 201, inquiry)
        self.assertIsNone(inquiry["whatsapp"])
        self.assertIsNone(inquiry["whatsappUrl"])
        self.assertNotEqual(inquiry.get("whatsapp"), roomies_server.SITE_CONTACT_WHATSAPP)

    def test_inquiry_falls_back_to_saved_publisher_profile_not_admin(self) -> None:
        cookie, payload = self.register("PerfilContacto", "perfil-contacto@example.com")
        status, created = self.request(
            "POST", "/api/listings", self.listing_payload(), cookie=cookie
        )
        self.assertEqual(status, 201, created)
        listing_id = created["listing"]["id"]
        self.publish_listing(listing_id)
        with roomies_server.connect() as database:
            database.execute(
                "UPDATE listings SET owner_whatsapp = 'invalido' WHERE id = ?",
                (listing_id,),
            )
            roomies_server.persist_publisher_profile(
                database,
                payload["user"]["id"],
                whatsapp="51991112233",
            )

        status, inquiry = self.request(
            "POST", "/api/inquiries", {"listingId": listing_id, "channel": "whatsapp"}
        )
        self.assertEqual(status, 201, inquiry)
        self.assertEqual(inquiry["whatsapp"], "51991112233")
        self.assertEqual(inquiry["whatsappUrl"], "https://wa.me/51991112233")
        self.assertNotEqual(inquiry["whatsapp"], roomies_server.SITE_CONTACT_WHATSAPP)

    def test_persist_helper_ignores_empty_strings(self) -> None:
        cookie, payload = self.register("Directa", "perfil-helper@example.com")
        user_id = payload["user"]["id"]
        with roomies_server.connect() as database:
            roomies_server.persist_publisher_profile(
                database,
                user_id,
                name="Gilberto Jara",
                whatsapp="51999888777",
                location="Lince, Lima",
            )
            roomies_server.persist_publisher_profile(
                database,
                user_id,
                name="",
                whatsapp="   ",
                location="",
            )
        status, me_payload = self.request("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(me_payload["user"]["publisherName"], "Gilberto Jara")
        self.assertEqual(me_payload["user"]["publisherWhatsApp"], "51999888777")
        self.assertEqual(me_payload["user"]["publisherLocation"], "Lince, Lima")


if __name__ == "__main__":
    unittest.main()
