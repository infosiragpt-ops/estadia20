"""Pruebas del alcance mundial de Llaves365: GET /api/geo ubica al visitante
por su IP (X-Real-IP, sin claves de pago, respaldo Perú/Lima), el WhatsApp
acepta números internacionales E.164, cada anuncio guarda país/ciudad/moneda
ISO (sin conversión) y la lista ordena por «más solicitados» y «se alquilan
más rápido» subiendo primero lo de la zona del visitante (near/nearCountry).
"""

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


class WorldwideApiTests(unittest.TestCase):
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
        cls.original_fetch_geo = roomies_server.fetch_geo_for_ip

    @classmethod
    def tearDownClass(cls) -> None:
        roomies_server.fetch_geo_for_ip = cls.original_fetch_geo
        cls.http_server.shutdown()
        cls.http_server.server_close()
        cls.server_thread.join(timeout=3)
        cls.temporary_directory.cleanup()

    def setUp(self) -> None:
        roomies_server._RATE_LIMIT_BUCKETS.clear()
        roomies_server._GEO_CACHE.clear()
        roomies_server.fetch_geo_for_ip = self.original_fetch_geo

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        cookie: str = "",
        headers: dict[str, str] | None = None,
    ):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        body = json.dumps(payload).encode() if payload is not None else None
        request_headers: dict[str, str] = dict(headers or {})
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if cookie:
            request_headers["Cookie"] = cookie
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw_body = response.read()
        response_payload = json.loads(raw_body) if raw_body else None
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_payload, response_headers

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
            "gallery": ["https://images.unsplash.com/photo-1505693416388-ac5ce068fe85"],
        }
        payload.update(overrides)
        status, response, _ = self.request("POST", "/api/listings", payload, cookie=cookie)
        self.assertEqual(status, 201, response)
        return response["listing"]

    # --- GET /api/geo: ubicación por IP sin claves ---

    def test_geo_defaults_to_peru_for_private_ip(self) -> None:
        # La conexión llega de 127.0.0.1 y sin X-Real-IP: respaldo Perú/Lima
        # sin consultar ningún servicio externo.
        def fail_lookup(ip: str):  # pragma: no cover - no debe llamarse
            raise AssertionError("una IP privada nunca se consulta afuera")

        roomies_server.fetch_geo_for_ip = fail_lookup
        status, payload, headers = self.request("GET", "/api/geo")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {"country": "PE", "city": "Lima", "currency": "PEN", "source": "fallback"},
        )
        self.assertIn("private", headers.get("Cache-Control", ""))

    def test_geo_resolves_public_ip_and_caches_the_result(self) -> None:
        calls: list[str] = []

        def fake_lookup(ip: str):
            calls.append(ip)
            return ("ES", "Madrid")

        roomies_server.fetch_geo_for_ip = fake_lookup
        status, payload, _ = self.request(
            "GET", "/api/geo", headers={"X-Real-IP": "8.8.8.8"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {"country": "ES", "city": "Madrid", "currency": "EUR", "source": "lookup"},
        )
        # La segunda consulta de la misma IP sale del caché del servidor.
        status, payload, _ = self.request(
            "GET", "/api/geo", headers={"X-Real-IP": "8.8.8.8"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["source"], "cache")
        self.assertEqual(payload["country"], "ES")
        self.assertEqual(calls, ["8.8.8.8"])

    def test_geo_falls_back_when_the_lookup_fails(self) -> None:
        def broken_lookup(ip: str):
            raise OSError("proveedor caído")

        roomies_server.fetch_geo_for_ip = broken_lookup
        status, payload, _ = self.request(
            "GET", "/api/geo", headers={"X-Real-IP": "1.2.3.4"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["country"], "PE")
        self.assertEqual(payload["city"], "Lima")
        self.assertEqual(payload["source"], "fallback")
        # El fallo no se cachea: al recuperarse el servicio, se vuelve a ubicar.
        roomies_server.fetch_geo_for_ip = lambda ip: ("CL", "Santiago")
        status, payload, _ = self.request(
            "GET", "/api/geo", headers={"X-Real-IP": "1.2.3.4"}
        )
        self.assertEqual(payload["country"], "CL")
        self.assertEqual(payload["currency"], "CLP")

    # --- WhatsApp mundial en formato E.164 ---

    def test_publish_accepts_international_whatsapp_with_plus_prefix(self) -> None:
        cookie = self.register("Mundial", "mundial-wa@example.com")
        listing = self.create_listing(
            cookie, "Cuarto en Madrid", ownerWhatsApp="+34 600 111 222"
        )
        self.assertEqual(listing["ownerWhatsApp"], "34600111222")

        # Los celulares peruanos siguen normalizándose con el prefijo 51.
        listing = self.create_listing(
            cookie, "Cuarto en Lima", ownerWhatsApp="987 654 321"
        )
        self.assertEqual(listing["ownerWhatsApp"], "51987654321")

    def test_publish_rejects_invalid_international_whatsapp(self) -> None:
        cookie = self.register("Validadora Mundial", "validadora-mundial@example.com")
        # Sin el prefijo + se mantiene la regla peruana; con + debe ser E.164.
        for invalid in ("34600111222", "+0034600111222", "+123", "+1234567890123456"):
            status, payload, _ = self.request(
                "POST",
                "/api/listings",
                {
                    "category": "Roomies",
                    "title": "Cuarto inválido",
                    "location": "Madrid",
                    "description": "Prueba",
                    "ownerName": "Prueba",
                    "ownerWhatsApp": invalid,
                    "price": 500,
                },
                cookie=cookie,
            )
            self.assertEqual(status, 400, invalid)
            self.assertIn("prefijo +", payload["error"])

    # --- País, ciudad y moneda ISO del anuncio (sin conversión) ---

    def test_publish_stores_country_city_and_local_currency(self) -> None:
        cookie = self.register("Publica Mundial", "publica-mundial@example.com")
        listing = self.create_listing(
            cookie,
            "Habitación en Chamberí",
            location="Chamberí, Madrid",
            country="ES",
            city="Madrid",
            ownerWhatsApp="+34600111333",
        )
        self.assertEqual(listing["country"], "ES")
        self.assertEqual(listing["city"], "Madrid")
        # Sin moneda explícita se sugiere la local del país elegido.
        self.assertEqual(listing["currency"], "EUR")

        # La moneda explícita (ISO 4217) se respeta tal cual, sin conversión.
        listing = self.create_listing(
            cookie,
            "Habitación en Miami",
            location="Brickell, Miami",
            country="US",
            city="Miami",
            currency="USD",
            price=900,
            ownerWhatsApp="+1 202 555 0123",
        )
        self.assertEqual(listing["currency"], "USD")
        self.assertEqual(listing["price"], 900)

        # Sin país ni moneda, el anuncio queda peruano en soles.
        listing = self.create_listing(cookie, "Habitación sin país")
        self.assertEqual(listing["country"], "PE")
        self.assertEqual(listing["currency"], "PEN")

    def test_publish_rejects_invalid_country_or_currency(self) -> None:
        cookie = self.register("Rechazos", "rechazos-mundial@example.com")
        base = {
            "category": "Roomies",
            "title": "Cuarto inválido",
            "location": "Lima",
            "description": "Prueba",
            "ownerName": "Prueba",
            "ownerWhatsApp": "51999000111",
            "price": 500,
        }
        status, payload, _ = self.request(
            "POST", "/api/listings", {**base, "country": "XX"}, cookie=cookie
        )
        self.assertEqual(status, 400)
        self.assertIn("país", payload["error"])
        status, payload, _ = self.request(
            "POST", "/api/listings", {**base, "currency": "SOL"}, cookie=cookie
        )
        self.assertEqual(status, 400)
        self.assertIn("moneda", payload["error"])

    def test_owner_can_update_city_and_currency(self) -> None:
        cookie = self.register("Editora Mundial", "editora-mundial@example.com")
        listing = self.create_listing(cookie, "Cuarto editable mundial")
        status, payload, _ = self.request(
            "PATCH",
            f"/api/listings/{listing['id']}",
            {"city": "Cusco", "currency": "USD", "country": "PE"},
            cookie=cookie,
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["listing"]["city"], "Cusco")
        self.assertEqual(payload["listing"]["currency"], "USD")

    # --- Órdenes «más solicitados» y «se alquilan más rápido» ---

    def test_sort_demanded_ranks_by_inquiries_and_favorites(self) -> None:
        admin_cookie = self.register("Admin Demanda", "admin-demanda@example.com")
        self.promote_to_admin("admin-demanda@example.com")
        admin_cookie = self.register_login("admin-demanda@example.com")
        popular = self.create_listing(admin_cookie, "Demandado popular")
        quiet = self.create_listing(admin_cookie, "Demandado tranquilo")

        # popular: 1 consulta + 2 favoritos (3 señales); quiet: 1 favorito.
        self.request("POST", "/api/inquiries", {"listingId": popular["id"], "channel": "whatsapp"})
        self.request("POST", "/api/favorites", {"listingId": popular["id"]})
        self.request("POST", "/api/favorites", {"listingId": popular["id"]})
        self.request("POST", "/api/favorites", {"listingId": quiet["id"]})

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&sort=demanded&pageSize=24"
        )
        self.assertEqual(status, 200)
        titles = [listing["title"] for listing in payload["listings"]]
        self.assertLess(titles.index("Demandado popular"), titles.index("Demandado tranquilo"))
        self.assertEqual(payload["meta"]["sort"], "demanded")

    def test_sort_fastest_ranks_by_inquiry_velocity(self) -> None:
        admin_cookie = self.register("Admin Rapidez", "admin-rapidez@example.com")
        self.promote_to_admin("admin-rapidez@example.com")
        admin_cookie = self.register_login("admin-rapidez@example.com")
        fast = self.create_listing(admin_cookie, "Se alquila rapidísimo")
        slow = self.create_listing(admin_cookie, "Se alquila con calma")

        # fast: 2 consultas recién publicadas (mayor velocidad de contacto);
        # slow: solo favoritos, que no cuentan para la velocidad.
        self.request("POST", "/api/inquiries", {"listingId": fast["id"], "channel": "whatsapp"})
        self.request("POST", "/api/inquiries", {"listingId": fast["id"], "channel": "whatsapp"})
        self.request("POST", "/api/favorites", {"listingId": slow["id"]})

        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&sort=fastest&pageSize=24"
        )
        self.assertEqual(status, 200)
        titles = [listing["title"] for listing in payload["listings"]]
        self.assertLess(
            titles.index("Se alquila rapidísimo"), titles.index("Se alquila con calma")
        )

    def register_login(self, email: str, password: str = "clave-segura-123") -> str:
        status, _, headers = self.request(
            "POST", "/api/auth/login", {"email": email, "password": password}
        )
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";", 1)[0]

    # --- Relevancia por zona: primero lo del lugar del visitante ---

    def test_near_ranks_local_listings_first_without_filtering(self) -> None:
        admin_cookie = self.register("Admin Zona", "admin-zona@example.com")
        self.promote_to_admin("admin-zona@example.com")
        admin_cookie = self.register_login("admin-zona@example.com")
        self.create_listing(
            admin_cookie,
            "Habitación en Malasaña",
            location="Malasaña, Madrid",
            country="ES",
            city="Madrid",
            currency="EUR",
            ownerWhatsApp="+34600222333",
        )

        status, payload, _ = self.request(
            "GET",
            "/api/listings?category=Roomies&near=Madrid&nearCountry=ES&pageSize=24",
        )
        self.assertEqual(status, 200)
        listings = payload["listings"]
        self.assertEqual(listings[0]["title"], "Habitación en Malasaña")
        # No filtra: los anuncios de otras zonas siguen después.
        self.assertGreater(len(listings), 1)
        self.assertEqual(payload["meta"]["near"], "Madrid")
        self.assertEqual(payload["meta"]["nearCountry"], "ES")
        self.assertGreaterEqual(payload["meta"]["nearMatches"], 1)

        # La misma búsqueda sin `near` no altera el orden normal.
        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&pageSize=24"
        )
        self.assertEqual(status, 200)
        self.assertNotIn("nearMatches", payload["meta"])

    def test_near_country_must_be_a_valid_iso_code(self) -> None:
        status, payload, _ = self.request(
            "GET", "/api/listings?category=Roomies&nearCountry=XX"
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "invalid_filters")

    def test_public_listings_expose_country_city_and_currency(self) -> None:
        status, payload, _ = self.request("GET", "/api/listings?category=Depas")
        self.assertEqual(status, 200)
        for listing in payload["listings"]:
            self.assertIn(listing["country"], roomies_server.COUNTRY_CODES)
            self.assertIn(listing["currency"], roomies_server.CURRENCY_CODES)
            self.assertIn("city", listing)


if __name__ == "__main__":
    unittest.main()
