"""Pruebas del flujo de publicación: subida múltiple de fotos con
redimensionado profesional y formularios por categoría."""

from __future__ import annotations

import base64
import http.client
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path

from vps import server as roomies_server

try:
    from PIL import Image
except ImportError:  # pragma: no cover - entorno sin Pillow
    Image = None

# PNG real de 1×1 (blanco) para pruebas que no dependen de Pillow.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
BOUNDARY = "----publishboundary"


def multipart_body(files: list[tuple[str, bytes]]) -> tuple[bytes, str]:
    parts = []
    for index, (field_name, content) in enumerate(files):
        parts.append(
            (
                f"--{BOUNDARY}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="foto-{index}.png"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode()
            + content
            + b"\r\n"
        )
    body = b"".join(parts) + f"--{BOUNDARY}--\r\n".encode()
    return body, f"multipart/form-data; boundary={BOUNDARY}"


def generated_png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 40, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


class QuietHandler(roomies_server.Roomies20Handler):
    def log_message(self, format_string: str, *args: object) -> None:
        return


class PublishApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        data_directory = Path(cls.temporary_directory.name) / "data"
        roomies_server.DATA_DIR = data_directory
        roomies_server.DATABASE_PATH = data_directory / "estadia20.sqlite3"
        roomies_server.UPLOADS_DIR = data_directory / "uploads"
        roomies_server.PUBLIC_DIR = Path(cls.temporary_directory.name) / "public"
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

    def register(self, name: str, email: str) -> str:
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
        response.read()
        cookie = response.getheader("Set-Cookie", "").split(";", 1)[0]
        connection.close()
        self.assertEqual(response.status, 201)
        return cookie

    def upload(self, files: list[tuple[str, bytes]], cookie: str):
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

    def fetch_bytes(self, path: str) -> bytes:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request("GET", path)
        response = connection.getresponse()
        content = response.read()
        connection.close()
        self.assertEqual(response.status, 200)
        return content

    def base_listing(self, category: str) -> dict:
        return {
            "category": category,
            "title": "Anuncio de prueba",
            "location": "Miraflores, Lima",
            "description": "Descripción de prueba con detalles suficientes.",
            "ownerName": "Prueba",
            "ownerWhatsApp": "51999000111",
            "price": 500,
        }

    def test_one_request_uploads_several_photos_in_order(self) -> None:
        cookie = self.register("Multifoto", "multifoto@example.com")
        status, payload = self.upload(
            [("files", TINY_PNG), ("files", TINY_PNG), ("files", TINY_PNG)], cookie
        )
        self.assertEqual(status, 201, payload)
        self.assertEqual(len(payload["urls"]), 3)
        self.assertEqual(payload["url"], payload["urls"][0])
        for url in payload["urls"]:
            self.assertTrue(url.startswith("/api/uploads/"))
        # El campo `file` de una sola foto sigue funcionando.
        status, payload = self.upload([("file", TINY_PNG)], cookie)
        self.assertEqual(status, 201, payload)
        self.assertEqual(len(payload["urls"]), 1)

    def test_upload_rejects_sixteen_photos(self) -> None:
        cookie = self.register("Excedida", "excedida@example.com")
        status, payload = self.upload([("files", TINY_PNG)] * 16, cookie)
        self.assertEqual(status, 400)
        self.assertIn("15", payload["error"])

    @unittest.skipUnless(Image is not None, "Pillow no está instalada")
    def test_upload_resizes_large_photo_to_professional_jpeg(self) -> None:
        cookie = self.register("Fotógrafo", "fotografo-resize@example.com")
        status, payload = self.upload([("files", generated_png(3200, 1400))], cookie)
        self.assertEqual(status, 201, payload)
        url = payload["urls"][0]
        self.assertTrue(url.endswith(".jpg"))
        served = self.fetch_bytes(url)
        self.assertTrue(served.startswith(b"\xff\xd8\xff"))
        with Image.open(io.BytesIO(served)) as resized:
            self.assertLessEqual(resized.width, 1600)
            self.assertLessEqual(resized.height, 1200)
            self.assertEqual((resized.width, resized.height), (1600, 700))
        self.assertLess(len(served), len(generated_png(3200, 1400)) * 2)

    @unittest.skipUnless(Image is not None, "Pillow no está instalada")
    def test_upload_never_upscales_small_photos(self) -> None:
        cookie = self.register("Miniatura", "miniatura@example.com")
        status, payload = self.upload([("files", generated_png(20, 10))], cookie)
        self.assertEqual(status, 201, payload)
        served = self.fetch_bytes(payload["urls"][0])
        with Image.open(io.BytesIO(served)) as resized:
            self.assertEqual((resized.width, resized.height), (20, 10))

    def test_listing_saves_gallery_with_first_photo_as_cover(self) -> None:
        cookie = self.register("Galerista", "galerista@example.com")
        status, payload = self.upload(
            [("files", TINY_PNG), ("files", TINY_PNG)], cookie
        )
        self.assertEqual(status, 201, payload)
        urls = payload["urls"]
        listing_payload = self.base_listing("Roomies")
        listing_payload["gallery"] = urls
        status, payload = self.request("POST", "/api/listings", listing_payload, cookie=cookie)
        self.assertEqual(status, 201, payload)
        self.assertEqual(payload["listing"]["gallery"], urls)
        self.assertEqual(payload["listing"]["image"], urls[0])

    def test_listing_rejects_more_than_fifteen_photos(self) -> None:
        cookie = self.register("Coleccionista", "coleccionista@example.com")
        listing_payload = self.base_listing("Roomies")
        listing_payload["gallery"] = [
            f"https://images.unsplash.com/photo-{index}" for index in range(16)
        ]
        status, payload = self.request("POST", "/api/listings", listing_payload, cookie=cookie)
        self.assertEqual(status, 400)
        self.assertIn("15", payload["error"])

    def test_roomies_details_are_sanitized_and_build_meta(self) -> None:
        cookie = self.register("Roomie", "roomie-detalles@example.com")
        listing_payload = self.base_listing("Roomies")
        listing_payload["priceLabel"] = "por hora"  # el servidor lo ignora
        listing_payload["details"] = {
            "bathroom": "Jacuzzi",  # inválido → Compartido
            "bed": "king size",  # inválido → 1 plaza
            "furnished": 1,
            "servicesIncluded": "",
            "hack": "<script>",
        }
        status, payload = self.request("POST", "/api/listings", listing_payload, cookie=cookie)
        self.assertEqual(status, 201, payload)
        listing = payload["listing"]
        self.assertEqual(
            listing["details"],
            {
                "bathroom": "Compartido",
                "bed": "1 plaza",
                "furnished": True,
                "servicesIncluded": False,
            },
        )
        self.assertEqual(listing["meta"], "1 cama · 1 baño compartido · Amoblado")
        self.assertEqual(listing["priceLabel"], "por mes")

    def test_stay_details_are_bounded_and_build_meta(self) -> None:
        cookie = self.register("Anfitriona", "anfitriona-detalles@example.com")
        listing_payload = self.base_listing("Airbnb")
        listing_payload["details"] = {
            "guests": 99,  # se limita a 16
            "bedrooms": 2,
            "beds": 3,
            "bathrooms": 1,
            "amenities": ["Wifi", "Jacuzzi", "Piscina"],  # Jacuzzi se descarta
        }
        status, payload = self.request("POST", "/api/listings", listing_payload, cookie=cookie)
        self.assertEqual(status, 201, payload)
        listing = payload["listing"]
        self.assertEqual(listing["details"]["guests"], 16)
        self.assertEqual(listing["details"]["amenities"], ["Wifi", "Piscina"])
        self.assertEqual(listing["meta"], "16 huéspedes · 2 habitaciones · Wifi")
        self.assertEqual(listing["priceLabel"], "por noche")

    def test_transport_details_build_meta(self) -> None:
        cookie = self.register("Transportista", "transportista-detalles@example.com")
        listing_payload = self.base_listing("Transporte")
        listing_payload["service"] = "Mudanza"
        listing_payload["details"] = {
            "vehicle": "  Camión 3 t  ",
            "capacity": "12 m³",
            "coverage": "Lima y Callao",
            "extra": "ignorado",
        }
        status, payload = self.request("POST", "/api/listings", listing_payload, cookie=cookie)
        self.assertEqual(status, 201, payload)
        listing = payload["listing"]
        self.assertEqual(
            listing["details"],
            {"vehicle": "Camión 3 t", "capacity": "12 m³", "coverage": "Lima y Callao"},
        )
        self.assertEqual(listing["meta"], "Camión 3 t · 12 m³ · Lima y Callao")
        self.assertEqual(listing["priceLabel"], "por servicio")

    def test_depa_details_build_meta_from_rooms_and_area(self) -> None:
        cookie = self.register("Inmobiliaria", "inmobiliaria-detalles@example.com")
        listing_payload = self.base_listing("Depas")
        listing_payload["details"] = {
            "address": "Av. Larco 1000",
            "units": 12,
            "areaTotal": "53 a 60 m² tot.",
            "areaCovered": "50 a 58 m² techada",
            "bedroomsMin": 1,
            "bedroomsMax": 2,
            "bathroomsMin": 1,
            "bathroomsMax": 1,
            "features": ["Balcón", "Jacuzzi"],  # Jacuzzi se descarta
        }
        status, payload = self.request("POST", "/api/listings", listing_payload, cookie=cookie)
        self.assertEqual(status, 201, payload)
        listing = payload["listing"]
        self.assertEqual(listing["meta"], "1 a 2 dormitorios · 1 baño · 53 a 60 m² tot.")
        self.assertEqual(listing["details"]["features"], ["Balcón"])
        self.assertEqual(listing["priceLabel"], "por mes")


if __name__ == "__main__":
    unittest.main()
