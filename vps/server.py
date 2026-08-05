#!/usr/bin/env python3
"""Small production API for the estadia20 VPS deployment."""

from __future__ import annotations

import argparse
import base64
import binascii
import cgi
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import date
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


DATA_DIR = Path(os.environ.get("ESTADIA20_DATA_DIR", "/var/lib/estadia20"))
DATABASE_PATH = DATA_DIR / "estadia20.sqlite3"
UPLOADS_DIR = DATA_DIR / "uploads"
PUBLIC_DIR = Path(os.environ.get("ESTADIA20_PUBLIC_DIR", "/opt/estadia20/public"))
VISITOR_COOKIE = "depitass_visitor"
SESSION_COOKIE = "estadia20_session"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
PASSWORD_ITERATIONS = 310_000
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
CATEGORIES = {"Roomies", "Depas", "Airbnb", "Transporte"}
IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE COLLATE NOCASE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              token_hash TEXT NOT NULL UNIQUE,
              expires_at INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
              ON sessions (expires_at);
            CREATE TABLE IF NOT EXISTS listings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              category TEXT NOT NULL,
              title TEXT NOT NULL,
              location TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              image TEXT NOT NULL DEFAULT '',
              gallery TEXT NOT NULL DEFAULT '[]',
              price INTEGER NOT NULL,
              price_label TEXT NOT NULL,
              rating REAL NOT NULL DEFAULT 5,
              reviews INTEGER NOT NULL DEFAULT 0,
              meta TEXT NOT NULL DEFAULT '',
              badge TEXT,
              owner_name TEXT NOT NULL,
              owner_whatsapp TEXT NOT NULL,
              service TEXT,
              user_id INTEGER REFERENCES users(id),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_listings_category_created_at
              ON listings (category, created_at);
            CREATE TABLE IF NOT EXISTS favorites (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              visitor_id TEXT NOT NULL,
              listing_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_visitor_listing
              ON favorites (visitor_id, listing_id);
            CREATE TABLE IF NOT EXISTS inquiries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              visitor_id TEXT NOT NULL,
              listing_id INTEGER NOT NULL,
              channel TEXT NOT NULL DEFAULT 'whatsapp',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_inquiries_listing_created_at
              ON inquiries (listing_id, created_at);
            """
        )
        listing_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(listings)")
        }
        if "user_id" not in listing_columns:
            database.execute(
                "ALTER TABLE listings ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS, dklen=32
    )
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"
        + base64.urlsafe_b64encode(salt).decode()
        + "$"
        + base64.urlsafe_b64encode(digest).decode()
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_value, salt_value, digest_value = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_value)
        if iterations < 100_000 or iterations > 1_000_000:
            return False
        salt = base64.urlsafe_b64decode(salt_value.encode())
        expected = base64.urlsafe_b64decode(digest_value.encode())
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations, dklen=32
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


def listing_dict(row: sqlite3.Row) -> dict[str, object]:
    try:
        gallery = json.loads(row["gallery"])
    except (json.JSONDecodeError, TypeError):
        gallery = []
    return {
        "id": row["id"],
        "category": row["category"],
        "title": row["title"],
        "location": row["location"],
        "description": row["description"],
        "image": row["image"],
        "gallery": gallery,
        "price": row["price"],
        "priceLabel": row["price_label"],
        "rating": row["rating"],
        "reviews": row["reviews"],
        "meta": row["meta"],
        "badge": row["badge"],
        "ownerName": row["owner_name"],
        "ownerWhatsApp": row["owner_whatsapp"],
        "service": row["service"],
    }


class Estadia20Handler(BaseHTTPRequestHandler):
    server_version = "Estadia20/1.0"

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"{self.address_string()} - {format_string % args}", flush=True)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def send_json(
        self,
        payload: dict[str, object],
        status: HTTPStatus = HTTPStatus.OK,
        visitor_id: str | None = None,
        session_token: str | None = None,
        clear_session: bool = False,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if visitor_id:
            self.send_header(
                "Set-Cookie",
                f"{VISITOR_COOKIE}={visitor_id}; Path=/; Max-Age=31536000; "
                "HttpOnly; SameSite=Lax; Secure",
            )
        if session_token:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={session_token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; "
                "HttpOnly; SameSite=Lax; Secure",
            )
        if clear_session:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax; Secure",
            )
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, object]:
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            raise ValueError("El contenido debe ser JSON")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 128 * 1024:
            raise ValueError("Cuerpo inválido")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("JSON inválido")
        return payload

    def visitor(self) -> tuple[str, bool]:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        existing = cookies.get(VISITOR_COOKIE)
        if existing and re.fullmatch(r"[A-Za-z0-9-]{20,80}", existing.value):
            return existing.value, False
        return str(uuid.uuid4()), True

    def authenticated_user(self) -> sqlite3.Row | None:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        cookie = cookies.get(SESSION_COOKIE)
        if not cookie or not re.fullmatch(r"[A-Za-z0-9_-]{32,100}", cookie.value):
            return None
        token_hash = hashlib.sha256(cookie.value.encode()).hexdigest()
        now = int(time.time())
        with connect() as database:
            row = database.execute(
                """
                SELECT users.id, users.name, users.email
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        return row

    def require_user(self) -> sqlite3.Row | None:
        user = self.authenticated_user()
        if user is None:
            self.send_json(
                {"error": "Inicia sesión para publicar un anuncio."},
                HTTPStatus.UNAUTHORIZED,
            )
        return user

    def create_session(self, database: sqlite3.Connection, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        database.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        database.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (
                user_id,
                hashlib.sha256(token.encode()).hexdigest(),
                now + SESSION_TTL_SECONDS,
            ),
        )
        return token

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "database": DATABASE_PATH.exists()})
            return
        if parsed.path == "/api/listings":
            category = parse_qs(parsed.query).get("category", [None])[0]
            query = "SELECT * FROM listings"
            values: tuple[object, ...] = ()
            if category in CATEGORIES:
                query += " WHERE category = ?"
                values = (category,)
            query += " ORDER BY created_at DESC, id DESC LIMIT 48"
            with connect() as database:
                rows = database.execute(query, values).fetchall()
            self.send_json({"listings": [listing_dict(row) for row in rows], "source": "database"})
            return
        if parsed.path == "/api/auth/me":
            user = self.authenticated_user()
            self.send_json(
                {
                    "user": (
                        {"id": user["id"], "name": user["name"], "email": user["email"]}
                        if user is not None
                        else None
                    )
                }
            )
            return
        if parsed.path == "/api/favorites":
            visitor_id, is_new = self.visitor()
            with connect() as database:
                rows = database.execute(
                    "SELECT listing_id FROM favorites WHERE visitor_id = ? ORDER BY created_at",
                    (visitor_id,),
                ).fetchall()
            self.send_json(
                {"favorites": [row["listing_id"] for row in rows]},
                visitor_id=visitor_id if is_new else None,
            )
            return
        if parsed.path.startswith("/api/uploads/"):
            self.serve_upload(parsed.path)
            return
        if parsed.path.startswith("/api/"):
            self.send_json({"error": "Ruta no encontrada."}, HTTPStatus.NOT_FOUND)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/auth/register":
                self.register_user()
            elif parsed.path == "/api/auth/login":
                self.login_user()
            elif parsed.path == "/api/auth/logout":
                self.logout_user()
            elif parsed.path == "/api/listings":
                self.create_listing()
            elif parsed.path == "/api/favorites":
                self.save_favorite()
            elif parsed.path == "/api/inquiries":
                self.create_inquiry()
            elif parsed.path == "/api/uploads":
                self.create_upload()
            else:
                self.send_json({"error": "Ruta no encontrada."}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "La solicitud no es válida."}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # keep API failures private but logged
            print(f"API error: {error!r}", flush=True)
            self.send_json({"error": "No se pudo completar la operación."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_DELETE(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/favorites":
            self.send_json({"error": "Ruta no encontrada."}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            listing_id = int(payload.get("listingId", 0))
            if listing_id <= 0:
                raise ValueError("ID inválido")
            visitor_id, is_new = self.visitor()
            with connect() as database:
                database.execute(
                    "DELETE FROM favorites WHERE visitor_id = ? AND listing_id = ?",
                    (visitor_id, listing_id),
                )
            self.send_json(
                {"saved": False}, visitor_id=visitor_id if is_new else None
            )
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Publicación inválida."}, HTTPStatus.BAD_REQUEST)

    def register_user(self) -> None:
        payload = self.read_json()
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if (
            len(name) < 2
            or len(name) > 80
            or len(email) > 160
            or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
            or len(password) < 8
            or len(password) > 128
        ):
            self.send_json(
                {"error": "Usa un nombre válido, un correo real y una clave de al menos 8 caracteres."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            with connect() as database:
                cursor = database.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, hash_password(password)),
                )
                user_id = int(cursor.lastrowid)
                token = self.create_session(database, user_id)
        except sqlite3.IntegrityError:
            self.send_json(
                {"error": "Ya existe una cuenta con ese correo."},
                HTTPStatus.CONFLICT,
            )
            return
        self.send_json(
            {"user": {"id": user_id, "name": name, "email": email}},
            HTTPStatus.CREATED,
            session_token=token,
        )

    def login_user(self) -> None:
        payload = self.read_json()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        with connect() as database:
            user = database.execute(
                "SELECT id, name, email, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if user is None or not verify_password(password, user["password_hash"]):
                self.send_json(
                    {"error": "Correo o contraseña incorrectos."},
                    HTTPStatus.UNAUTHORIZED,
                )
                return
            token = self.create_session(database, int(user["id"]))
        self.send_json(
            {"user": {"id": user["id"], "name": user["name"], "email": user["email"]}},
            session_token=token,
        )

    def logout_user(self) -> None:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        cookie = cookies.get(SESSION_COOKIE)
        if cookie and re.fullmatch(r"[A-Za-z0-9_-]{32,100}", cookie.value):
            token_hash = hashlib.sha256(cookie.value.encode()).hexdigest()
            with connect() as database:
                database.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        self.send_json({"loggedOut": True}, clear_session=True)

    def create_listing(self) -> None:
        user = self.require_user()
        if user is None:
            return
        payload = self.read_json()
        category = str(payload.get("category", ""))
        title = str(payload.get("title", "")).strip()
        location = str(payload.get("location", "")).strip()
        description = str(payload.get("description", "")).strip()
        owner_name = str(payload.get("ownerName", "")).strip()
        owner_whatsapp = re.sub(r"\D", "", str(payload.get("ownerWhatsApp", "")))
        image = str(payload.get("image", "")).strip() or (
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c"
        )
        price = int(float(payload.get("price", 0)))
        if (
            category not in CATEGORIES
            or not all((title, location, description, owner_name))
            or len(owner_whatsapp) < 8
            or price <= 0
        ):
            self.send_json({"error": "Completa todos los campos obligatorios."}, HTTPStatus.BAD_REQUEST)
            return
        if not (
            image.startswith("/api/uploads/")
            or image.startswith("https://images.unsplash.com/")
        ):
            self.send_json({"error": "La fotografía no es válida."}, HTTPStatus.BAD_REQUEST)
            return
        with connect() as database:
            cursor = database.execute(
                """
                INSERT INTO listings
                  (category, title, location, description, image, gallery, price,
                   price_label, rating, reviews, meta, owner_name, owner_whatsapp, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 5, 0, ?, ?, ?, ?)
                """,
                (
                    category,
                    title,
                    location,
                    description,
                    image,
                    json.dumps([image]),
                    price,
                    str(payload.get("priceLabel", "")).strip() or "por servicio",
                    "Publicación nueva · Contacto directo",
                    owner_name,
                    owner_whatsapp,
                    user["id"],
                ),
            )
            row = database.execute(
                "SELECT * FROM listings WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        self.send_json({"listing": listing_dict(row)}, HTTPStatus.CREATED)

    def save_favorite(self) -> None:
        payload = self.read_json()
        listing_id = int(payload.get("listingId", 0))
        if listing_id <= 0:
            self.send_json({"error": "Publicación inválida."}, HTTPStatus.BAD_REQUEST)
            return
        visitor_id, is_new = self.visitor()
        with connect() as database:
            database.execute(
                "INSERT OR IGNORE INTO favorites (visitor_id, listing_id) VALUES (?, ?)",
                (visitor_id, listing_id),
            )
        self.send_json({"saved": True}, visitor_id=visitor_id if is_new else None)

    def create_inquiry(self) -> None:
        payload = self.read_json()
        listing_id = int(payload.get("listingId", 0))
        if listing_id <= 0:
            self.send_json({"error": "Publicación inválida."}, HTTPStatus.BAD_REQUEST)
            return
        visitor_id, is_new = self.visitor()
        channel = "whatsapp" if payload.get("channel") == "whatsapp" else "direct"
        with connect() as database:
            database.execute(
                "INSERT INTO inquiries (visitor_id, listing_id, channel) VALUES (?, ?, ?)",
                (visitor_id, listing_id, channel),
            )
        self.send_json(
            {"recorded": True},
            HTTPStatus.CREATED,
            visitor_id=visitor_id if is_new else None,
        )

    def create_upload(self) -> None:
        if self.require_user() is None:
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES + 128 * 1024:
            self.send_json({"error": "La imagen debe pesar menos de 8 MB."}, HTTPStatus.BAD_REQUEST)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_json({"error": "Selecciona una fotografía."}, HTTPStatus.BAD_REQUEST)
            return
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
        )
        field = form["file"] if "file" in form else None
        if field is None or not getattr(field, "file", None):
            self.send_json({"error": "Selecciona una fotografía."}, HTTPStatus.BAD_REQUEST)
            return
        mime_type = field.type or ""
        extension = IMAGE_TYPES.get(mime_type)
        if not extension:
            self.send_json({"error": "El archivo debe ser una imagen."}, HTTPStatus.BAD_REQUEST)
            return
        content = field.file.read(MAX_UPLOAD_BYTES + 1)
        if not content or len(content) > MAX_UPLOAD_BYTES:
            self.send_json({"error": "La imagen debe pesar menos de 8 MB."}, HTTPStatus.BAD_REQUEST)
            return
        folder = date.today().isoformat()
        destination = UPLOADS_DIR / folder
        destination.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4()}.{extension}"
        (destination / filename).write_bytes(content)
        self.send_json(
            {"url": f"/api/uploads/{folder}/{filename}"}, HTTPStatus.CREATED
        )

    def serve_upload(self, request_path: str) -> None:
        relative = unquote(request_path.removeprefix("/api/uploads/")).strip("/")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}/[A-Za-z0-9-]+\.(jpg|png|webp|gif)", relative):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = (UPLOADS_DIR / relative).resolve()
        if UPLOADS_DIR.resolve() not in file_path.parents or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.serve_file(file_path, "public, max-age=31536000, immutable")

    def serve_static(self, request_path: str) -> None:
        relative = unquote(request_path).lstrip("/") or "index.html"
        file_path = (PUBLIC_DIR / relative).resolve()
        if PUBLIC_DIR.resolve() not in file_path.parents or not file_path.is_file():
            file_path = PUBLIC_DIR / "index.html"
        self.serve_file(file_path, "public, max-age=31536000" if "." in relative else "no-cache")

    def serve_file(self, file_path: Path, cache_control: str) -> None:
        try:
            body = file_path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3011)
    arguments = parser.parse_args()
    initialize_database()
    server = ThreadingHTTPServer((arguments.host, arguments.port), Estadia20Handler)
    print(f"Estadia20 API listening on {arguments.host}:{arguments.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
