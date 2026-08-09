#!/usr/bin/env python3
"""Small production API for the roomies20 VPS deployment."""

from __future__ import annotations

import argparse
import base64
import binascii
import cgi
from collections import defaultdict, deque
import hashlib
import hmac
import json
import math
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import unicodedata
import uuid
from datetime import date
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qs, unquote, urlparse


DATA_DIR = Path(os.environ.get("ESTADIA20_DATA_DIR", "/var/lib/estadia20"))
DATABASE_PATH = DATA_DIR / "estadia20.sqlite3"
UPLOADS_DIR = DATA_DIR / "uploads"
PUBLIC_DIR = Path(os.environ.get("ESTADIA20_PUBLIC_DIR", "/opt/estadia20/public"))
GOOGLE_VENDOR_DIR = PUBLIC_DIR / ".server_vendor"
GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "1076572757032-u0jp02mfhohujaao9qu64jlmja0asn2c.apps.googleusercontent.com",
).strip()
OWNER_EMAIL = os.environ.get(
    "LLAVES365_OWNER_EMAIL",
    os.environ.get("ROOMIES20_OWNER_EMAIL", "infosiragpt@gmail.com"),
).strip().lower()
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
DEPA_FEATURES = {
    "Amoblado",
    "Permite mascotas",
    "Área de lavandería",
    "Balcón",
    "Terraza",
    "Ascensor",
}
LISTING_SORTS = {
    "recommended": "(badge IS NOT NULL) DESC, rating DESC, reviews DESC, created_at DESC, id DESC",
    "newest": "created_at DESC, id DESC",
    "price_asc": "price ASC, rating DESC, id DESC",
    "price_desc": "price DESC, rating DESC, id DESC",
    "rating": "rating DESC, reviews DESC, id DESC",
}
RATE_LIMIT_RULES = {
    ("POST", "/api/auth/register"): (8, 300),
    ("POST", "/api/auth/login"): (12, 300),
    ("POST", "/api/auth/google"): (20, 300),
    ("POST", "/api/listings"): (12, 3600),
    ("POST", "/api/uploads"): (12, 3600),
    ("POST", "/api/favorites"): (60, 60),
    ("DELETE", "/api/favorites"): (60, 60),
    ("POST", "/api/inquiries"): (20, 60),
}
_RATE_LIMIT_BUCKETS: dict[tuple[str, str, str], deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = threading.Lock()
DEPA_SEED_LISTINGS = (
    {
        "title": "Edificios en Miraflores",
        "location": "Miraflores, Lima",
        "description": "Proyecto residencial de entrega inmediata con departamentos de uno y dos dormitorios, áreas comunes y conexión directa con el centro de Miraflores.",
        "image": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c",
        "gallery": [
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c",
            "https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea",
        ],
        "price": 2909,
        "rating": 4.9,
        "reviews": 28,
        "meta": "1 a 2 dormitorios · 1 a 2 baños · 53 a 60 m²",
        "badge": "Entrega inmediata",
        "owner_name": "Valeria",
        "owner_whatsapp": "51999888777",
        "details": {"delivery": "Entrega inmediata", "availability": "Entrega Inmediata", "address": "Av. Ricardo Palma 251, Miraflores, Lima", "units": 280, "areaTotal": "53 a 60 m² tot.", "areaCovered": "53 a 60 m² techada", "bedroomsMin": 1, "bedroomsMax": 2, "bathroomsMin": 1, "bathroomsMax": 2, "features": ["Amoblado", "Permite mascotas", "Área de lavandería", "Balcón", "Terraza", "Ascensor"]},
    },
    {
        "title": "Residencial Parque Surco",
        "location": "Santiago de Surco, Lima",
        "description": "Departamentos contemporáneos con distribución eficiente, espacios sociales y acceso rápido a parques, colegios y comercios.",
        "image": "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3",
        "gallery": [
            "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3",
            "https://images.unsplash.com/photo-1600607687920-4e2a09cf159d",
        ],
        "price": 3100,
        "rating": 5,
        "reviews": 15,
        "meta": "2 a 3 dormitorios · 2 baños · 72 a 96 m²",
        "badge": "Listo para mudarte",
        "owner_name": "Diego",
        "owner_whatsapp": "51991112233",
        "details": {"delivery": "Entrega inmediata", "availability": "Últimas unidades", "address": "Av. Caminos del Inca 1245, Santiago de Surco, Lima", "units": 64, "areaTotal": "72 a 96 m² tot.", "areaCovered": "68 a 90 m² techada", "bedroomsMin": 2, "bedroomsMax": 3, "bathroomsMin": 2, "bathroomsMax": 2, "features": ["Amoblado", "Permite mascotas", "Área de lavandería", "Balcón", "Ascensor"]},
    },
    {
        "title": "Vive frente al parque",
        "location": "San Isidro, Lima",
        "description": "Un edificio residencial de baja densidad con ambientes amplios, iluminación natural y seguridad permanente.",
        "image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c",
        "gallery": ["https://images.unsplash.com/photo-1600585154340-be6161a56a0c"],
        "price": 3600,
        "rating": 4.8,
        "reviews": 11,
        "meta": "3 dormitorios · 2 a 3 baños · 105 a 126 m²",
        "badge": None,
        "owner_name": "Patricia",
        "owner_whatsapp": "51990001122",
        "details": {"delivery": "Disponible ahora", "availability": "Contrato de 12 meses", "address": "Calle Los Laureles 410, San Isidro, Lima", "units": 32, "areaTotal": "105 a 126 m² tot.", "areaCovered": "98 a 118 m² techada", "bedroomsMin": 3, "bedroomsMax": 3, "bathroomsMin": 2, "bathroomsMax": 3, "features": ["Permite mascotas", "Área de lavandería", "Balcón", "Terraza", "Ascensor"]},
    },
    {
        "title": "Departamentos en Pueblo Libre",
        "location": "Pueblo Libre, Lima",
        "description": "Departamentos funcionales con cocina abierta, balcón y contratos desde seis meses en una zona residencial conectada.",
        "image": "https://images.unsplash.com/photo-1600607687920-4e2a09cf159d",
        "gallery": ["https://images.unsplash.com/photo-1600607687920-4e2a09cf159d"],
        "price": 2250,
        "rating": 4.7,
        "reviews": 8,
        "meta": "1 a 2 dormitorios · 1 baño · 46 a 68 m²",
        "badge": None,
        "owner_name": "Renzo",
        "owner_whatsapp": "51988889999",
        "details": {"delivery": "Disponible ahora", "availability": "Contrato desde 6 meses", "address": "Av. Brasil 1850, Pueblo Libre, Lima", "units": 90, "areaTotal": "46 a 68 m² tot.", "areaCovered": "44 a 64 m² techada", "bedroomsMin": 1, "bedroomsMax": 2, "bathroomsMin": 1, "bathroomsMax": 1, "features": ["Permite mascotas", "Área de lavandería", "Balcón", "Ascensor"]},
    },
)
MARKETPLACE_SEED_LISTINGS = (
    {
        "category": "Roomies", "title": "Habitación con luz y calma", "location": "Barranco, Lima",
        "description": "Habitación privada dentro de un depa compartido, con cocina equipada, escritorio y una comunidad tranquila.",
        "image": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85",
        "gallery": ["https://images.unsplash.com/photo-1505693416388-ac5ce068fe85", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267"],
        "price": 780, "price_label": "por mes", "rating": 4.9, "reviews": 18,
        "meta": "1 cama · 1 baño compartido · Amoblado", "badge": "Favorito entre roomies",
        "owner_name": "Carla", "owner_whatsapp": "51999888777", "service": None,
    },
    {
        "category": "Roomies", "title": "Roomie en depa creativo", "location": "Miraflores, Lima",
        "description": "Espacio listo para mudarte, con áreas comunes amplias, buena conexión y compañeros que respetan tus tiempos.",
        "image": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267",
        "gallery": ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267", "https://images.unsplash.com/photo-1497366811353-6870744d04b2"],
        "price": 920, "price_label": "por mes", "rating": 5, "reviews": 12,
        "meta": "1 cama · 1 baño · Incluye servicios", "badge": "Respuesta rápida",
        "owner_name": "Mateo", "owner_whatsapp": "51999111222", "service": None,
    },
    {
        "category": "Roomies", "title": "Cuarto amplio cerca al parque", "location": "San Miguel, Lima",
        "description": "Habitación espaciosa con ventana exterior, clóset y acceso a terraza compartida.",
        "image": "https://images.unsplash.com/photo-1505691938895-1758d7feb511", "gallery": [],
        "price": 650, "price_label": "por mes", "rating": 4.8, "reviews": 9,
        "meta": "1 cama · 1 baño compartido · Sin amoblar", "badge": None,
        "owner_name": "Andrea", "owner_whatsapp": "51988777666", "service": None,
    },
    {
        "category": "Roomies", "title": "Habitación privada con escritorio", "location": "Jesús María, Lima",
        "description": "Ideal para estudiar o trabajar desde casa. Cocina y lavandería compartidas, edificio seguro.",
        "image": "https://images.unsplash.com/photo-1524758631624-e2822e304c36", "gallery": [],
        "price": 720, "price_label": "por mes", "rating": 4.9, "reviews": 21,
        "meta": "1 cama · 1 baño · Escritorio", "badge": None,
        "owner_name": "Luis", "owner_whatsapp": "51987654321", "service": None,
    },
    {
        "category": "Airbnb", "title": "Departamento con diseño en Barranco", "location": "Barranco, Lima",
        "description": "Departamento con interiores cálidos, detalles locales y todo lo necesario para una escapada con personalidad.",
        "image": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c", "gallery": [],
        "price": 240, "price_label": "por noche", "rating": 4.98, "reviews": 46,
        "meta": "2 huéspedes · 1 habitación · Wifi", "badge": "Favorito entre huéspedes",
        "owner_name": "Sofía", "owner_whatsapp": "51999888777", "service": None,
    },
    {
        "category": "Airbnb", "title": "Suite luminosa cerca al malecón", "location": "Miraflores, Lima",
        "description": "Un refugio con balcón, cama king y acceso caminando al malecón y los mejores cafés.",
        "image": "https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea", "gallery": [],
        "price": 380, "price_label": "por noche", "rating": 4.96, "reviews": 32,
        "meta": "2 huéspedes · 1 habitación · Vista al mar", "badge": "Reserva flexible",
        "owner_name": "Camila", "owner_whatsapp": "51992223344", "service": None,
    },
    {
        "category": "Airbnb", "title": "Casa tranquila para desconectar", "location": "Cieneguilla, Lima",
        "description": "Casa rodeada de verde para bajar el ritmo, leer y compartir una estadía diferente.",
        "image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c", "gallery": [],
        "price": 420, "price_label": "por noche", "rating": 4.9, "reviews": 19,
        "meta": "4 huéspedes · 2 habitaciones · Piscina", "badge": None,
        "owner_name": "Nicolás", "owner_whatsapp": "51995556677", "service": None,
    },
    {
        "category": "Airbnb", "title": "Mini depa con diseño local", "location": "Centro de Lima",
        "description": "Un espacio compacto, bonito y funcional para conocer la ciudad desde el corazón.",
        "image": "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3", "gallery": [],
        "price": 190, "price_label": "por noche", "rating": 4.85, "reviews": 27,
        "meta": "2 huéspedes · 1 habitación · Cocina", "badge": None,
        "owner_name": "Mariana", "owner_whatsapp": "51991119911", "service": None,
    },
    {
        "category": "Transporte", "title": "Mudanza segura para tu depa", "location": "Lima Metropolitana",
        "description": "Equipo puntual para mudanzas de hogar, oficina o habitación. Cuidamos cada caja y coordinamos por WhatsApp.",
        "image": "https://images.unsplash.com/photo-1601584115197-04ecc0da31d8", "gallery": [],
        "price": 180, "price_label": "por servicio", "rating": 4.9, "reviews": 36,
        "meta": "Camión 3 t · 12 m³ · 2 ayudantes", "badge": "Más solicitado",
        "owner_name": "Mudanzas Norte", "owner_whatsapp": "51999911111", "service": "Mudanza",
    },
    {
        "category": "Transporte", "title": "Furgón para mudanzas medianas", "location": "Lima y Callao",
        "description": "Furgón cerrado para traslados de hasta 1.5 toneladas, con seguimiento y carga protegida.",
        "image": "https://images.unsplash.com/photo-1586864387967-d02ef85d93e8", "gallery": [],
        "price": 140, "price_label": "por servicio", "rating": 4.8, "reviews": 22,
        "meta": "Furgón 1.5 t · 8 m³ · Carga protegida", "badge": None,
        "owner_name": "Ruta 24", "owner_whatsapp": "51998881122", "service": "Mudanza",
    },
    {
        "category": "Transporte", "title": "SUV premium para corporativo", "location": "Lima Metropolitana",
        "description": "Traslados corporativos en camioneta premium 2026, conductor profesional y vehículo verificado.",
        "image": "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2", "gallery": [],
        "price": 260, "price_label": "por servicio", "rating": 5, "reviews": 17,
        "meta": "SUV premium 2026 · 4 pasajeros · Verificado", "badge": "Vehículo verificado",
        "owner_name": "Elite Drive", "owner_whatsapp": "51997776655", "service": "Corporativo",
    },
    {
        "category": "Transporte", "title": "Camioneta ejecutiva 2025", "location": "Lima · Aeropuerto · Eventos",
        "description": "Servicio premium para reuniones, aeropuerto y eventos. Reserva por horas o por jornada.",
        "image": "https://images.unsplash.com/photo-1551830820-330a71b99659", "gallery": [],
        "price": 310, "price_label": "por servicio", "rating": 4.95, "reviews": 14,
        "meta": "Camioneta 2025 · 6 pasajeros · Verificado", "badge": None,
        "owner_name": "Prime Mobility", "owner_whatsapp": "51996665544", "service": "Corporativo",
    },
)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.create_function("search_normalize", 1, normalize_search_text, deterministic=True)
    connection.create_function("search_matches", 2, search_matches, deterministic=True)
    return connection


def normalize_search_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


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
              details_json TEXT NOT NULL DEFAULT '{}',
              user_id INTEGER REFERENCES users(id),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_listings_category_created_at
              ON listings (category, created_at);
            CREATE INDEX IF NOT EXISTS idx_listings_category_price
              ON listings (category, price);
            CREATE INDEX IF NOT EXISTS idx_listings_category_rating
              ON listings (category, rating DESC, reviews DESC);
            CREATE TABLE IF NOT EXISTS favorites (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              visitor_id TEXT NOT NULL,
              listing_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_visitor_listing
              ON favorites (visitor_id, listing_id);
            CREATE INDEX IF NOT EXISTS idx_favorites_listing
              ON favorites (listing_id);
            CREATE TABLE IF NOT EXISTS inquiries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              visitor_id TEXT NOT NULL,
              listing_id INTEGER NOT NULL,
              channel TEXT NOT NULL DEFAULT 'whatsapp',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_inquiries_listing_created_at
              ON inquiries (listing_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_inquiries_visitor_created_at
              ON inquiries (visitor_id, created_at);
            """
        )
        listing_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(listings)")
        }
        if "user_id" not in listing_columns:
            database.execute(
                "ALTER TABLE listings ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        if "details_json" not in listing_columns:
            database.execute(
                "ALTER TABLE listings ADD COLUMN details_json TEXT NOT NULL DEFAULT '{}'"
            )
        user_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(users)")
        }
        user_migrations = {
            "google_sub": "ALTER TABLE users ADD COLUMN google_sub TEXT",
            "avatar_url": (
                "ALTER TABLE users ADD COLUMN avatar_url TEXT NOT NULL DEFAULT ''"
            ),
            "auth_provider": (
                "ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'password'"
            ),
            "role": "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'",
        }
        for column, migration in user_migrations.items():
            if column not in user_columns:
                database.execute(migration)
        database.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
              ON users (google_sub)
              WHERE google_sub IS NOT NULL
            """
        )
        database.executescript(
            """
            DELETE FROM favorites
              WHERE NOT EXISTS (SELECT 1 FROM listings WHERE listings.id = favorites.listing_id);
            DELETE FROM inquiries
              WHERE NOT EXISTS (SELECT 1 FROM listings WHERE listings.id = inquiries.listing_id);
            CREATE TRIGGER IF NOT EXISTS validate_favorite_listing
              BEFORE INSERT ON favorites
              WHEN NOT EXISTS (SELECT 1 FROM listings WHERE id = NEW.listing_id)
              BEGIN
                SELECT RAISE(ABORT, 'listing_not_found');
              END;
            CREATE TRIGGER IF NOT EXISTS validate_inquiry_listing
              BEFORE INSERT ON inquiries
              WHEN NOT EXISTS (SELECT 1 FROM listings WHERE id = NEW.listing_id)
              BEGIN
                SELECT RAISE(ABORT, 'listing_not_found');
              END;
            """
        )
        depa_count = database.execute(
            "SELECT COUNT(*) FROM listings WHERE category = 'Depas'"
        ).fetchone()[0]
        if depa_count == 0:
            database.executemany(
                """
                INSERT INTO listings
                  (category, title, location, description, image, gallery, price,
                   price_label, rating, reviews, meta, badge, owner_name,
                   owner_whatsapp, details_json)
                VALUES ('Depas', ?, ?, ?, ?, ?, ?, 'por mes', ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        listing["title"],
                        listing["location"],
                        listing["description"],
                        listing["image"],
                        json.dumps(listing["gallery"], ensure_ascii=False),
                        listing["price"],
                        listing["rating"],
                        listing["reviews"],
                        listing["meta"],
                        listing["badge"],
                        listing["owner_name"],
                        listing["owner_whatsapp"],
                        json.dumps(listing["details"], ensure_ascii=False),
                    )
                    for listing in reversed(DEPA_SEED_LISTINGS)
                ],
            )
        for category in ("Roomies", "Airbnb", "Transporte"):
            category_count = database.execute(
                "SELECT COUNT(*) FROM listings WHERE category = ?", (category,)
            ).fetchone()[0]
            if category_count:
                continue
            seeds = [
                listing for listing in MARKETPLACE_SEED_LISTINGS
                if listing["category"] == category
            ]
            database.executemany(
                """
                INSERT INTO listings
                  (category, title, location, description, image, gallery, price,
                   price_label, rating, reviews, meta, badge, owner_name,
                   owner_whatsapp, service, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                [
                    (
                        listing["category"], listing["title"], listing["location"],
                        listing["description"], listing["image"],
                        json.dumps(listing["gallery"], ensure_ascii=False),
                        listing["price"], listing["price_label"], listing["rating"],
                        listing["reviews"], listing["meta"], listing["badge"],
                        listing["owner_name"], listing["owner_whatsapp"],
                        listing["service"],
                    )
                    for listing in reversed(seeds)
                ],
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


def user_dict(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "avatarUrl": row["avatar_url"],
        "authProvider": row["auth_provider"],
        "role": row["role"],
    }


class GoogleTransportResponse:
    """Minimal response adapter used by the Google Auth verifier."""

    def __init__(self, status: int, data: bytes, headers: dict[str, str]):
        self.status = status
        self.data = data
        self.headers = headers


class GoogleTransportRequest:
    """HTTPS transport for google-auth implemented with Python's standard library."""

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | float | None = None,
        **_: object,
    ) -> GoogleTransportResponse:
        request = urllib_request.Request(
            url,
            data=body,
            headers=headers or {},
            method=method,
        )
        try:
            with urllib_request.urlopen(request, timeout=timeout or 10) as response:
                return GoogleTransportResponse(
                    response.status,
                    response.read(),
                    dict(response.headers.items()),
                )
        except urllib_error.HTTPError as error:
            return GoogleTransportResponse(
                error.code,
                error.read(),
                dict(error.headers.items()) if error.headers else {},
            )
        except (urllib_error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError("No se pudo contactar a Google") from error


def verify_google_credential(credential: str) -> dict[str, object]:
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError("Google no está configurado")
    if GOOGLE_VENDOR_DIR.is_dir() and str(GOOGLE_VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(GOOGLE_VENDOR_DIR))
    try:
        from google.auth import exceptions as google_exceptions
        from google.oauth2 import id_token
    except ImportError as error:
        raise RuntimeError("El verificador de Google no está disponible") from error

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            GoogleTransportRequest(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
    except (ValueError, google_exceptions.GoogleAuthError) as error:
        raise ValueError("Credencial de Google inválida") from error
    if claims.get("email_verified") is not True:
        raise ValueError("Google no confirmó el correo")
    return claims


def listing_dict(row: sqlite3.Row) -> dict[str, object]:
    try:
        gallery = json.loads(row["gallery"])
    except (json.JSONDecodeError, TypeError):
        gallery = []
    try:
        details = json.loads(row["details_json"] or "{}")
    except (json.JSONDecodeError, TypeError, IndexError):
        details = {}
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
        "details": details,
    }


def bounded_integer(value: object, minimum: int, maximum: int, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return min(maximum, max(minimum, number))


SEARCH_ALIAS_FAMILIES = (
    ("habitacion", "cuarto", "dormitorio", "roomie", "roommate"),
    ("amoblado", "amueblado", "equipado", "muebles"),
    ("bano", "servicio", "bathroom"),
    ("escritorio", "oficina", "trabajo", "estudio"),
    ("cerca", "cercano", "proximo"),
    ("departamento", "depa", "apartamento"),
    ("transporte", "movilidad", "traslado"),
    ("mudanza", "carga", "camion", "camioneta"),
)
SEARCH_ALIASES = {
    term: family for family in SEARCH_ALIAS_FAMILIES for term in family
}
SEARCH_STOP_WORDS = {
    "busca", "buscar", "busco", "quiero", "necesito", "para", "por", "una",
    "uno", "un", "de", "del", "en", "con", "que", "sea", "soles", "s",
}


def bounded_edit_distance(left: str, right: str, maximum: int = 2) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > maximum:
        return maximum + 1
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, 1):
        current = [left_index]
        row_minimum = left_index
        for right_index, right_character in enumerate(right, 1):
            value = min(
                current[right_index - 1] + 1,
                previous[right_index] + 1,
                previous[right_index - 1] + (left_character != right_character),
            )
            current.append(value)
            row_minimum = min(row_minimum, value)
        if row_minimum > maximum:
            return maximum + 1
        previous = current
    return previous[-1]


def search_matches(value: object, query: object) -> int:
    candidate_tokens = normalize_search_text(value).split()
    query_tokens = normalize_search_text(query).split()
    for query_token in query_tokens:
        alternatives = SEARCH_ALIASES.get(query_token, (query_token,))
        found = False
        for alternative in alternatives:
            for candidate in candidate_tokens:
                if (
                    alternative == candidate
                    or candidate.startswith(alternative)
                    or (len(alternative) >= 4 and alternative in candidate)
                    or (
                        len(alternative) >= 4
                        and bounded_edit_distance(
                            alternative,
                            candidate,
                            2 if len(alternative) >= 7 else 1,
                        ) <= (2 if len(alternative) >= 7 else 1)
                    )
                ):
                    found = True
                    break
            if found:
                break
        if not found:
            return 0
    return 1


def optional_integer(value: str | None, minimum: int, maximum: int) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Número inválido") from error
    if number < minimum or number > maximum:
        raise ValueError("Número fuera de rango")
    return number


def image_extension_from_content(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    return None


def listings_query(parameters: dict[str, list[str]]) -> tuple[list[sqlite3.Row], dict[str, object]]:
    category = parameters.get("category", [""])[0]
    if category and category not in CATEGORIES:
        raise ValueError("Categoría inválida")

    query_text = str(parameters.get("q", [""])[0]).strip()[:120]
    normalized_query = normalize_search_text(query_text)
    minimum_price = optional_integer(parameters.get("minPrice", [None])[0], 0, 10_000_000)
    maximum_price = optional_integer(parameters.get("maxPrice", [None])[0], 0, 10_000_000)
    ceiling_match = re.search(
        r"\b(?:hasta|maximo|max|menos de)\s+(?:s\s*)?(\d{2,7})\b",
        normalized_query,
    )
    if ceiling_match and maximum_price is None:
        maximum_price = int(ceiling_match.group(1))
        normalized_query = normalized_query.replace(ceiling_match.group(0), " ")
    if minimum_price is not None and maximum_price is not None and minimum_price > maximum_price:
        raise ValueError("El precio mínimo no puede superar al máximo")

    bedrooms_value = str(parameters.get("bedrooms", [""])[0]).strip()
    bedrooms = None
    if bedrooms_value:
        bedrooms = 4 if bedrooms_value == "4+" else optional_integer(bedrooms_value, 1, 10)
    service = str(parameters.get("service", [""])[0]).strip()[:40]
    if service and service not in {"Todos", "Mudanza", "Corporativo"}:
        raise ValueError("Servicio inválido")
    requested_features = [
        feature.strip()
        for feature in str(parameters.get("features", [""])[0]).split(",")
        if feature.strip()
    ]
    if any(feature not in DEPA_FEATURES for feature in requested_features):
        raise ValueError("Característica inválida")

    page = optional_integer(parameters.get("page", ["1"])[0], 1, 10_000) or 1
    page_size = optional_integer(parameters.get("pageSize", ["12"])[0], 1, 48) or 12
    sort = str(parameters.get("sort", ["recommended"])[0]).strip()
    if sort not in LISTING_SORTS:
        raise ValueError("Orden inválido")

    clauses: list[str] = []
    values: list[object] = []
    if category:
        clauses.append("category = ?")
        values.append(category)
    if minimum_price is not None:
        clauses.append("price >= ?")
        values.append(minimum_price)
    if maximum_price is not None:
        clauses.append("price <= ?")
        values.append(maximum_price)
    if service and service != "Todos":
        clauses.append("service = ?")
        values.append(service)
    if bedrooms is not None:
        bedroom_expression = (
            "CASE WHEN json_valid(details_json) "
            "THEN CAST(json_extract(details_json, '$.bedroomsMax') AS INTEGER) ELSE 0 END"
        )
        clauses.append(f"{bedroom_expression} >= ?")
        values.append(bedrooms)
        if bedrooms_value != "4+":
            minimum_expression = (
                "CASE WHEN json_valid(details_json) "
                "THEN CAST(json_extract(details_json, '$.bedroomsMin') AS INTEGER) ELSE 0 END"
            )
            clauses.append(f"{minimum_expression} <= ?")
            values.append(bedrooms)
    for feature in requested_features:
        clauses.append("details_json LIKE ?")
        values.append(f'%"{feature}"%')

    searchable_expression = (
        "search_normalize(title || ' ' || location || ' ' || description || ' ' || "
        "meta || ' ' || details_json || ' ' || owner_name)"
    )
    search_tokens = [
        token for token in normalized_query.split() if token not in SEARCH_STOP_WORDS
    ][:6]
    if search_tokens:
        clauses.append(f"search_matches({searchable_expression}, ?) = 1")
        values.append(" ".join(search_tokens))

    where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * page_size
    with connect() as database:
        category_total = database.execute(
            "SELECT COUNT(*) FROM listings" + (" WHERE category = ?" if category else ""),
            (category,) if category else (),
        ).fetchone()[0]
        total = database.execute(
            f"SELECT COUNT(*) FROM listings{where_clause}", values
        ).fetchone()[0]
        rows = database.execute(
            f"SELECT * FROM listings{where_clause} ORDER BY {LISTING_SORTS[sort]} LIMIT ? OFFSET ?",
            [*values, page_size, offset],
        ).fetchall()

    total_pages = max(1, math.ceil(total / page_size))
    return rows, {
        "total": total,
        "categoryTotal": category_total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
        "hasMore": page < total_pages,
        "sort": sort,
    }


def sanitize_depa_details(value: object, location: str) -> dict[str, object]:
    source = value if isinstance(value, dict) else {}
    bedrooms_min = bounded_integer(source.get("bedroomsMin"), 1, 10, 1)
    bedrooms_max = bounded_integer(source.get("bedroomsMax"), bedrooms_min, 10, bedrooms_min)
    bathrooms_min = bounded_integer(source.get("bathroomsMin"), 1, 10, 1)
    bathrooms_max = bounded_integer(source.get("bathroomsMax"), bathrooms_min, 10, bathrooms_min)
    features = source.get("features") if isinstance(source.get("features"), list) else []

    def clean_text(key: str, fallback: str, limit: int = 160) -> str:
        text = str(source.get(key, "")).strip()
        return text[:limit] or fallback

    return {
        "delivery": clean_text("delivery", "Disponible ahora", 60),
        "availability": clean_text("availability", "Alquiler mensual", 80),
        "address": clean_text("address", location),
        "units": bounded_integer(source.get("units"), 1, 10_000, 1),
        "areaTotal": clean_text("areaTotal", "Área por consultar", 80),
        "areaCovered": clean_text("areaCovered", "Área techada por consultar", 80),
        "bedroomsMin": bedrooms_min,
        "bedroomsMax": bedrooms_max,
        "bathroomsMin": bathrooms_min,
        "bathroomsMax": bathrooms_max,
        "features": [feature for feature in features if feature in DEPA_FEATURES],
    }


class Roomies20Handler(BaseHTTPRequestHandler):
    server_version = "roomies20/1.1"

    def handle_one_request(self) -> None:
        self.request_id = uuid.uuid4().hex[:16]
        super().handle_one_request()

    def log_message(self, format_string: str, *args: object) -> None:
        print(
            json.dumps(
                {
                    "requestId": getattr(self, "request_id", "unknown"),
                    "client": self.client_ip(),
                    "message": format_string % args,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    def client_ip(self) -> str:
        # Nginx overwrites X-Real-IP with the actual peer address. Avoid trusting
        # a client-controlled X-Forwarded-For value for abuse controls.
        real_ip = self.headers.get("X-Real-IP", "").strip()
        return real_ip[:64] or self.client_address[0]

    def end_headers(self) -> None:
        self.send_header("X-Request-ID", getattr(self, "request_id", "unknown"))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; "
            "style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; "
            "img-src 'self' data: https://images.unsplash.com https://lh3.googleusercontent.com; "
            "connect-src 'self' https://accounts.google.com; "
            "frame-src https://accounts.google.com; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'self'",
        )
        super().end_headers()

    def send_json(
        self,
        payload: dict[str, object],
        status: HTTPStatus = HTTPStatus.OK,
        visitor_id: str | None = None,
        session_token: str | None = None,
        clear_session: bool = False,
        cache_control: str = "no-store",
        etag: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if etag and self.headers.get("If-None-Match") == etag:
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.send_header("Cache-Control", cache_control)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        if etag:
            self.send_header("ETag", etag)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
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

    def send_api_error(
        self,
        message: str,
        status: HTTPStatus,
        code: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_json(
            {"error": message, "code": code, "requestId": self.request_id},
            status,
            extra_headers=extra_headers,
        )

    def check_rate_limit(self, method: str, path: str) -> bool:
        rule = RATE_LIMIT_RULES.get((method, path))
        if rule is None:
            return True
        maximum, window_seconds = rule
        now = time.monotonic()
        key = (method, path, self.client_ip())
        with _RATE_LIMIT_LOCK:
            bucket = _RATE_LIMIT_BUCKETS[key]
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= maximum:
                retry_after = max(1, math.ceil(window_seconds - (now - bucket[0])))
            else:
                bucket.append(now)
                retry_after = 0
        if retry_after:
            self.send_api_error(
                "Demasiados intentos. Espera un momento y vuelve a intentarlo.",
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                {"Retry-After": str(retry_after)},
            )
            return False
        return True

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
                SELECT users.id, users.name, users.email, users.avatar_url,
                       users.auth_provider, users.role
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
            try:
                with connect() as database:
                    database.execute("SELECT 1").fetchone()
                self.send_json({"ok": True, "database": True})
            except sqlite3.Error:
                self.send_api_error(
                    "La base de datos no está disponible.",
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "database_unavailable",
                )
            return
        if parsed.path == "/api/auth/config":
            self.send_json(
                {
                    "googleEnabled": bool(GOOGLE_CLIENT_ID),
                    "googleClientId": GOOGLE_CLIENT_ID,
                }
            )
            return
        if parsed.path == "/api/listings":
            try:
                rows, metadata = listings_query(parse_qs(parsed.query, keep_blank_values=True))
            except ValueError as error:
                self.send_api_error(str(error), HTTPStatus.BAD_REQUEST, "invalid_filters")
                return
            payload = {
                "listings": [listing_dict(row) for row in rows],
                "meta": metadata,
                "source": "database",
            }
            serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            etag = f'"{hashlib.sha256(serialized).hexdigest()[:24]}"'
            self.send_json(
                payload,
                cache_control="public, max-age=30, stale-while-revalidate=120",
                etag=etag,
            )
            return
        if parsed.path == "/api/auth/me":
            user = self.authenticated_user()
            self.send_json({"user": user_dict(user) if user is not None else None})
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
            self.send_api_error("Ruta no encontrada.", HTTPStatus.NOT_FOUND, "not_found")
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self.check_rate_limit("POST", parsed.path):
            return
        try:
            if parsed.path == "/api/auth/register":
                self.register_user()
            elif parsed.path == "/api/auth/login":
                self.login_user()
            elif parsed.path == "/api/auth/google":
                self.google_login()
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
                self.send_api_error("Ruta no encontrada.", HTTPStatus.NOT_FOUND, "not_found")
        except (ValueError, json.JSONDecodeError):
            self.send_api_error(
                "La solicitud no es válida.", HTTPStatus.BAD_REQUEST, "invalid_request"
            )
        except Exception as error:  # keep API failures private but logged
            print(
                json.dumps(
                    {"requestId": self.request_id, "error": repr(error)},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            self.send_api_error(
                "No se pudo completar la operación.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
            )

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/favorites":
            self.send_api_error("Ruta no encontrada.", HTTPStatus.NOT_FOUND, "not_found")
            return
        if not self.check_rate_limit("DELETE", path):
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
            self.send_api_error(
                "Publicación inválida.", HTTPStatus.BAD_REQUEST, "invalid_listing"
            )

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
                user = database.execute(
                    """
                    SELECT id, name, email, avatar_url, auth_provider, role
                    FROM users WHERE id = ?
                    """,
                    (user_id,),
                ).fetchone()
                token = self.create_session(database, user_id)
        except sqlite3.IntegrityError:
            self.send_json(
                {"error": "Ya existe una cuenta con ese correo."},
                HTTPStatus.CONFLICT,
            )
            return
        self.send_json(
            {"user": user_dict(user)},
            HTTPStatus.CREATED,
            session_token=token,
        )

    def login_user(self) -> None:
        payload = self.read_json()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        with connect() as database:
            user = database.execute(
                """
                SELECT id, name, email, password_hash, avatar_url,
                       auth_provider, role
                FROM users WHERE email = ?
                """,
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
            {"user": user_dict(user)},
            session_token=token,
        )

    def google_login(self) -> None:
        if not GOOGLE_CLIENT_ID:
            self.send_json(
                {"error": "El acceso con Google todavía no está configurado."},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        payload = self.read_json()
        credential = str(payload.get("credential", "")).strip()
        if not credential or len(credential) > 12_000:
            self.send_json(
                {"error": "Google no entregó una credencial válida."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            claims = verify_google_credential(credential)
        except ValueError:
            self.send_json(
                {"error": "No pudimos validar tu cuenta de Google. Inténtalo otra vez."},
                HTTPStatus.UNAUTHORIZED,
            )
            return
        except RuntimeError as error:
            print(f"Google authentication unavailable: {error!r}", flush=True)
            self.send_json(
                {"error": "Google no está disponible en este momento."},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        google_sub = str(claims.get("sub", "")).strip()
        email = str(claims.get("email", "")).strip().lower()
        name = str(claims.get("name", "")).strip()[:80] or email.split("@", 1)[0]
        avatar_url = str(claims.get("picture", "")).strip()[:500]
        if not avatar_url.startswith("https://"):
            avatar_url = ""
        if (
            not google_sub
            or len(google_sub) > 255
            or len(email) > 160
            or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
        ):
            self.send_json(
                {"error": "La cuenta de Google no contiene un correo válido."},
                HTTPStatus.UNAUTHORIZED,
            )
            return

        role = "admin" if email == OWNER_EMAIL else "user"
        try:
            with connect() as database:
                by_google = database.execute(
                    "SELECT id FROM users WHERE google_sub = ?", (google_sub,)
                ).fetchone()
                by_email = database.execute(
                    "SELECT id FROM users WHERE email = ?", (email,)
                ).fetchone()
                if (
                    by_google is not None
                    and by_email is not None
                    and by_google["id"] != by_email["id"]
                ):
                    self.send_json(
                        {"error": "Ese correo ya pertenece a otra cuenta."},
                        HTTPStatus.CONFLICT,
                    )
                    return
                existing = by_google or by_email
                if existing is None:
                    cursor = database.execute(
                        """
                        INSERT INTO users
                          (name, email, password_hash, google_sub, avatar_url,
                           auth_provider, role)
                        VALUES (?, ?, '', ?, ?, 'google', ?)
                        """,
                        (name, email, google_sub, avatar_url, role),
                    )
                    user_id = int(cursor.lastrowid)
                else:
                    user_id = int(existing["id"])
                    database.execute(
                        """
                        UPDATE users
                        SET name = ?, email = ?, google_sub = ?, avatar_url = ?,
                            auth_provider = 'google', role = ?
                        WHERE id = ?
                        """,
                        (name, email, google_sub, avatar_url, role, user_id),
                    )
                user = database.execute(
                    """
                    SELECT id, name, email, avatar_url, auth_provider, role
                    FROM users WHERE id = ?
                    """,
                    (user_id,),
                ).fetchone()
                token = self.create_session(database, user_id)
        except sqlite3.IntegrityError:
            self.send_json(
                {"error": "No pudimos vincular esa cuenta de Google."},
                HTTPStatus.CONFLICT,
            )
            return

        self.send_json({"user": user_dict(user)}, session_token=token)

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
            or len(title) > 120
            or len(location) > 160
            or len(description) > 2_000
            or len(owner_name) > 80
            or not 8 <= len(owner_whatsapp) <= 15
            or price <= 0
            or price > 10_000_000
        ):
            self.send_json({"error": "Completa todos los campos obligatorios."}, HTTPStatus.BAD_REQUEST)
            return
        if not (
            image.startswith("/api/uploads/")
            or image.startswith("https://images.unsplash.com/")
        ):
            self.send_json({"error": "La fotografía no es válida."}, HTTPStatus.BAD_REQUEST)
            return
        details = sanitize_depa_details(payload.get("details"), location) if category == "Depas" else {}
        with connect() as database:
            cursor = database.execute(
                """
                INSERT INTO listings
                  (category, title, location, description, image, gallery, price,
                   price_label, rating, reviews, meta, owner_name, owner_whatsapp,
                   details_json, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 5, 0, ?, ?, ?, ?, ?)
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
                    json.dumps(details, ensure_ascii=False),
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
            exists = database.execute(
                "SELECT 1 FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
            if exists is None:
                self.send_api_error(
                    "La publicación ya no está disponible.",
                    HTTPStatus.NOT_FOUND,
                    "listing_not_found",
                )
                return
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
            exists = database.execute(
                "SELECT 1 FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
            if exists is None:
                self.send_api_error(
                    "La publicación ya no está disponible.",
                    HTTPStatus.NOT_FOUND,
                    "listing_not_found",
                )
                return
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
        claimed_extension = IMAGE_TYPES.get(mime_type)
        if not claimed_extension:
            self.send_json({"error": "El archivo debe ser una imagen."}, HTTPStatus.BAD_REQUEST)
            return
        content = field.file.read(MAX_UPLOAD_BYTES + 1)
        if not content or len(content) > MAX_UPLOAD_BYTES:
            self.send_json({"error": "La imagen debe pesar menos de 8 MB."}, HTTPStatus.BAD_REQUEST)
            return
        extension = image_extension_from_content(content)
        if extension is None or extension != claimed_extension:
            self.send_api_error(
                "El contenido del archivo no coincide con una imagen válida.",
                HTTPStatus.BAD_REQUEST,
                "invalid_image",
            )
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
        is_spa_fallback = PUBLIC_DIR.resolve() not in file_path.parents or not file_path.is_file()
        if is_spa_fallback:
            file_path = PUBLIC_DIR / "index.html"
        is_versioned_asset = relative.startswith("assets/") and not is_spa_fallback
        cache_control = (
            "public, max-age=31536000, immutable"
            if is_versioned_asset
            else "no-cache, no-store, must-revalidate"
        )
        self.serve_file(file_path, cache_control)

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
    server = ThreadingHTTPServer((arguments.host, arguments.port), Roomies20Handler)
    print(f"roomies20 API listening on {arguments.host}:{arguments.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
