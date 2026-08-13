from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

from vps import server as roomies_server


class QuietHandler(roomies_server.Roomies20Handler):
    def log_message(self, format_string: str, *args: object) -> None:
        return


class MarketplaceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        data_directory = Path(cls.temporary_directory.name) / "data"
        roomies_server.DATA_DIR = data_directory
        roomies_server.DATABASE_PATH = data_directory / "roomies20.sqlite3"
        roomies_server.UPLOADS_DIR = data_directory / "uploads"
        roomies_server.PUBLIC_DIR = Path(cls.temporary_directory.name) / "public"
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

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
    ):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        body = json.dumps(payload).encode() if payload is not None else None
        request_headers = dict(headers or {})
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw_body = response.read()
        response_payload = json.loads(raw_body) if raw_body else None
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_payload, response_headers

    def first_listing_id(self, category: str = "Roomies") -> int:
        status, payload, _ = self.request("GET", f"/api/listings?category={category}")
        self.assertEqual(status, 200)
        return int(payload["listings"][0]["id"])

    def test_search_is_fuzzy_filtered_sorted_and_paginated(self) -> None:
        query = urlencode(
            {
                "category": "Roomies",
                "q": "abitacion hasta S/ 800",
                "sort": "price_asc",
                "pageSize": 2,
            }
        )
        status, payload, headers = self.request("GET", f"/api/listings?{query}")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(payload["meta"]["categoryTotal"], 4)
        self.assertLessEqual(len(payload["listings"]), 2)
        self.assertTrue(all(listing["price"] <= 800 for listing in payload["listings"]))
        self.assertEqual(payload["meta"]["sort"], "price_asc")
        self.assertIn("ETag", headers)
        self.assertIn("stale-while-revalidate", headers["Cache-Control"])

    def test_depa_features_and_price_ranges_are_server_side(self) -> None:
        query = urlencode(
            {
                "category": "Depas",
                "features": "Balcón,Ascensor",
                "minPrice": 2500,
                "maxPrice": 3300,
                "bedrooms": 2,
            }
        )
        status, payload, _ = self.request("GET", f"/api/listings?{query}")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(payload["meta"]["total"], 1)
        for listing in payload["listings"]:
            self.assertGreaterEqual(listing["price"], 2500)
            self.assertLessEqual(listing["price"], 3300)
            self.assertIn("Balcón", listing["details"]["features"])
            self.assertIn("Ascensor", listing["details"]["features"])

    def test_listing_etag_supports_conditional_requests(self) -> None:
        path = "/api/listings?category=Airbnb&pageSize=2"
        first_status, _, first_headers = self.request("GET", path)
        self.assertEqual(first_status, 200)
        second_status, second_payload, second_headers = self.request(
            "GET", path, headers={"If-None-Match": first_headers["ETag"]}
        )
        self.assertEqual(second_status, 304)
        self.assertIsNone(second_payload)
        self.assertEqual(second_headers["ETag"], first_headers["ETag"])

    def test_favorites_and_inquiries_require_a_real_listing(self) -> None:
        listing_id = self.first_listing_id()
        saved_status, saved_payload, _ = self.request(
            "POST", "/api/favorites", {"listingId": listing_id}
        )
        self.assertEqual(saved_status, 200)
        self.assertTrue(saved_payload["saved"])

        missing_status, missing_payload, _ = self.request(
            "POST", "/api/favorites", {"listingId": 999_999}
        )
        self.assertEqual(missing_status, 404)
        self.assertEqual(missing_payload["code"], "listing_not_found")

        inquiry_status, inquiry_payload, _ = self.request(
            "POST", "/api/inquiries", {"listingId": 999_999, "channel": "whatsapp"}
        )
        self.assertEqual(inquiry_status, 404)
        self.assertEqual(inquiry_payload["code"], "listing_not_found")

    def test_rate_limits_return_retry_after_and_request_id(self) -> None:
        listing_id = self.first_listing_id("Transporte")
        rule_key = ("POST", "/api/inquiries")
        original_rule = roomies_server.RATE_LIMIT_RULES[rule_key]
        roomies_server.RATE_LIMIT_RULES[rule_key] = (2, 60)
        roomies_server._RATE_LIMIT_BUCKETS.clear()
        try:
            for _ in range(2):
                status, _, headers = self.request(
                    "POST", "/api/inquiries", {"listingId": listing_id, "channel": "whatsapp"}
                )
                self.assertEqual(status, 201)
                self.assertIn("X-Request-ID", headers)
            limited_status, limited_payload, limited_headers = self.request(
                "POST", "/api/inquiries", {"listingId": listing_id, "channel": "whatsapp"}
            )
            self.assertEqual(limited_status, 429)
            self.assertEqual(limited_payload["code"], "rate_limited")
            self.assertGreaterEqual(int(limited_headers["Retry-After"]), 1)
        finally:
            roomies_server.RATE_LIMIT_RULES[rule_key] = original_rule
            roomies_server._RATE_LIMIT_BUCKETS.clear()

    def test_upload_detection_uses_file_signatures(self) -> None:
        self.assertEqual(roomies_server.image_extension_from_content(b"\xff\xd8\xff\xe0data"), "jpg")
        self.assertEqual(roomies_server.image_extension_from_content(b"\x89PNG\r\n\x1a\ndata"), "png")
        self.assertEqual(roomies_server.image_extension_from_content(b"RIFF0000WEBPdata"), "webp")
        self.assertIsNone(roomies_server.image_extension_from_content(b"<script>alert(1)</script>"))


if __name__ == "__main__":
    unittest.main()
