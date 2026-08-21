#!/usr/bin/env python3
"""Small production API for the roomies20 VPS deployment."""

from __future__ import annotations

import argparse
import base64
import binascii
from collections import defaultdict, deque
from email import policy as email_policy
from email.parser import BytesParser
import hashlib
import hmac
import html
import io
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
import shutil
import unicodedata
import uuid
from datetime import date
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qs, unquote, urlencode, urlparse


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
    "ESTADIA20_OWNER_EMAIL",
    os.environ.get(
        "LLAVES365_OWNER_EMAIL",
        os.environ.get("ROOMIES20_OWNER_EMAIL", "carrerajorge874@gmail.com"),
    ),
).strip().lower()
# Los anuncios de demostración solo se insertan si se pide explícitamente;
# así el administrador puede eliminarlos sin que reaparezcan al reiniciar.
SEED_DEMO_DATA = os.environ.get("ESTADIA20_SEED_DEMO", "").strip().lower() in {
    "1", "true", "yes", "si", "sí",
}
VISITOR_COOKIE = "depitass_visitor"
SESSION_COOKIE = "estadia20_session"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
# Flujo alternativo de Google por redirección (OAuth 2.0 con id_token) para
# navegadores donde el iframe de Google Identity Services no carga (Safari
# móvil, FedCM bloqueado, etc.). El dominio de retorno debe estar autorizado
# en Google Cloud Console como "Authorized redirect URI".
OAUTH_STATE_COOKIE = "estadia20_oauth"
OAUTH_STATE_TTL_SECONDS = 10 * 60
OAUTH_CALLBACK_PATH = "/api/auth/google/callback"
GOOGLE_OAUTH_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
# Destinos internos del puente HTML (200) que evita fijar cookies en un 302/303
# de rebote: Safari ITP y Chrome tiran esas cookies y la sesión no sobrevive.
AUTH_BRIDGE_HOME = frozenset({"/", "/?auth=google-ok", "/?auth=google-error"})
OAUTH_REDIRECT_HOSTS = frozenset(
    host.strip().lower()
    for host in os.environ.get(
        "ESTADIA20_OAUTH_HOSTS",
        "llaves365.com,www.llaves365.com,estadia20.com,www.estadia20.com",
    ).split(",")
    if host.strip()
)
OAUTH_DEFAULT_HOST = "llaves365.com"
# URL pública canónica del sitio: alimenta el sitemap y robots.txt.
SITE_BASE_URL = os.environ.get("LLAVES365_BASE_URL", "https://llaves365.com").rstrip("/")
# WhatsApp del software/administrador (pie y «Contacto» del sitio). Nunca se
# usa como respaldo al contactar un anuncio: ese chat va al número que el
# anunciante registró al publicar.
SITE_CONTACT_WHATSAPP = "51918714054"
# Cadena de versión para /api/health; el despliegue puede inyectarla con
# ESTADIA20_RELEASE (por ejemplo, el SHA del commit).
RELEASE_VERSION = os.environ.get(
    "ESTADIA20_RELEASE", os.environ.get("LLAVES365_RELEASE", "dev")
).strip() or "dev"


def session_cookie_header(token: str, *, same_site: str = "Lax") -> str:
    """Cookie de sesión HttpOnly. SameSite=Lax en el POST mismo origen (GIS);
    SameSite=None en el retorno form_post de Google, que es cross-site."""
    if same_site not in {"Lax", "None"}:
        raise ValueError("SameSite de sesión inválido")
    return (
        f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; "
        f"HttpOnly; SameSite={same_site}; Secure"
    )


def cleared_session_cookie_headers() -> tuple[str, str]:
    # El retorno OAuth puede haber fijado SameSite=None; el cierre de sesión
    # del sitio tiene que borrar las dos variantes. Nunca se llama a Google.
    return (
        f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax; Secure",
        f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=None; Secure",
    )


def oauth_state_cookie_header(value: str | None = None) -> str:
    if value:
        return (
            f"{OAUTH_STATE_COOKIE}={value}; Path=/; "
            f"Max-Age={OAUTH_STATE_TTL_SECONDS}; HttpOnly; SameSite=None; Secure"
        )
    return (
        f"{OAUTH_STATE_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=None; Secure"
    )


PASSWORD_ITERATIONS = 310_000
# Los tokens de «olvidé mi contraseña» viven 45 minutos y se guardan con hash;
# el token en claro solo se registra en los logs del servidor (no hay SMTP aún).
PASSWORD_RESET_TTL_SECONDS = 45 * 60
# Cada foto original puede pesar hasta 12 MB; el servidor la redimensiona a un
# tamaño profesional (máx. 1600×1200) antes de guardarla, así el archivo final
# queda mucho más liviano.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_GALLERY_PHOTOS = 15
MAX_UPLOAD_FILES = MAX_GALLERY_PHOTOS
MAX_UPLOAD_REQUEST_BYTES = MAX_UPLOAD_BYTES * MAX_UPLOAD_FILES + 512 * 1024
PHOTO_MAX_WIDTH = 1600
PHOTO_MAX_HEIGHT = 1200
PHOTO_QUALITY = 82
CATEGORIES = {"Roomies", "Depas", "Airbnb", "Transporte"}
# La pestaña pública se llama «Estadías», pero la base de datos conserva la
# categoría histórica «Airbnb». El alias se acepta en todos los filtros y al
# publicar, así los enlaces compartidos (?category=Estadías) siempre funcionan.
CATEGORY_ALIASES = {"Estadías": "Airbnb", "Estadias": "Airbnb"}
CATEGORY_PRICE_LABELS = {
    "Roomies": "por mes",
    "Depas": "por mes",
    "Airbnb": "por noche",
    "Transporte": "por servicio",
}
IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    # Fotos del iPhone: se convierten a JPEG con pillow-heif al subirlas. Si el
    # servidor no puede decodificarlas, esa foto falla con un mensaje claro en
    # español en lugar de guardar un original que el navegador no muestra.
    "image/heic": "heic",
    "image/heif": "heic",
}
HEIC_MESSAGE = (
    "Tu foto está en formato HEIC (iPhone) y no pudimos convertirla. "
    "En tu iPhone activa Ajustes → Cámara → Formatos → Más compatible "
    "para enviar JPEG, o elige otra foto."
)
# Ciclo de vida del anuncio. Los anuncios existentes y los de demostración
# quedan «published»; los nuevos anuncios de usuarios no administradores nacen
# «pending» hasta que el administrador los apruebe.
LISTING_STATUSES = {"published", "paused", "rented", "pending", "rejected"}
# El dueño puede pausar, reanudar, marcar alquilado o republicar; aprobar un
# anuncio pendiente o rechazado es exclusivo del administrador.
OWNER_STATUS_CHOICES = {"published", "paused", "rented"}
REPORT_REASONS = {"spam", "alquilado", "numero_falso", "otro"}
DEPA_FEATURES = {
    "Amoblado",
    "Permite mascotas",
    "Área de lavandería",
    "Balcón",
    "Terraza",
    "Ascensor",
}
ROOMIE_BATHROOM_OPTIONS = {"Privado", "Compartido"}
ROOMIE_BED_OPTIONS = {"1 plaza", "1.5 plazas", "2 plazas"}
STAY_AMENITIES = ("Wifi", "Cocina", "Estacionamiento", "Piscina")
LISTING_SORTS = {
    "recommended": "(badge IS NOT NULL) DESC, rating DESC, reviews DESC, created_at DESC, id DESC",
    "newest": "created_at DESC, id DESC",
    "price_asc": "price ASC, rating DESC, id DESC",
    "price_desc": "price DESC, rating DESC, id DESC",
    "rating": "rating DESC, reviews DESC, id DESC",
}
# Nombres cortos que llegan en enlaces compartidos (?sort=price); cualquier
# otro valor desconocido sigue respondiendo 400.
LISTING_SORT_ALIASES = {"price": "price_asc"}
RATE_LIMIT_RULES = {
    ("POST", "/api/auth/register"): (8, 300),
    ("POST", "/api/auth/login"): (12, 300),
    ("POST", "/api/auth/google"): (20, 300),
    ("POST", OAUTH_CALLBACK_PATH): (20, 300),
    ("POST", "/api/listings"): (12, 3600),
    # Una petición puede traer hasta 15 fotos; con 30 peticiones por hora un
    # anuncio completo (o varios) se publica sin chocar con el límite.
    ("POST", "/api/uploads"): (30, 3600),
    ("POST", "/api/favorites"): (60, 60),
    ("DELETE", "/api/favorites"): (60, 60),
    ("POST", "/api/inquiries"): (20, 60),
    ("POST", "/api/reports"): (10, 3600),
    ("POST", "/api/auth/password/forgot"): (5, 900),
    ("POST", "/api/auth/password/reset"): (10, 900),
    ("PATCH", "/api/listings"): (30, 3600),
    ("PATCH", "/api/auth/me"): (30, 3600),
    ("DELETE", "/api/listings"): (30, 3600),
    # Límite de lectura moderado para frenar el raspado masivo de anuncios sin
    # afectar la navegación normal (la lista pagina de a 24 y cachea con ETag).
    ("GET", "/api/listings"): (240, 60),
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
        # Ciclo de vida: los anuncios ya publicados (y los de demostración)
        # conservan «published»; solo los anuncios nuevos de usuarios no
        # administradores entran como «pending».
        if "status" not in listing_columns:
            database.execute(
                "ALTER TABLE listings ADD COLUMN status TEXT NOT NULL DEFAULT 'published'"
            )
        if "updated_at" not in listing_columns:
            database.execute("ALTER TABLE listings ADD COLUMN updated_at TEXT")
        database.execute(
            "CREATE INDEX IF NOT EXISTS idx_listings_status ON listings (status)"
        )
        inquiry_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(inquiries)")
        }
        inquiry_migrations = {
            "message": "ALTER TABLE inquiries ADD COLUMN message TEXT NOT NULL DEFAULT ''",
            "check_in": "ALTER TABLE inquiries ADD COLUMN check_in TEXT",
            "check_out": "ALTER TABLE inquiries ADD COLUMN check_out TEXT",
            "guests": "ALTER TABLE inquiries ADD COLUMN guests INTEGER",
            "user_id": "ALTER TABLE inquiries ADD COLUMN user_id INTEGER REFERENCES users(id)",
        }
        for column, migration in inquiry_migrations.items():
            if column not in inquiry_columns:
                database.execute(migration)
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
            "last_login_at": "ALTER TABLE users ADD COLUMN last_login_at TEXT",
            "last_login_provider": (
                "ALTER TABLE users ADD COLUMN last_login_provider TEXT"
            ),
            # Perfil de publicación: nombre, WhatsApp y última zona. Se
            # rellenan al publicar (o al guardar la cuenta) para no pedirlos
            # otra vez; nunca se pisan con cadenas vacías.
            "publisher_name": (
                "ALTER TABLE users ADD COLUMN publisher_name TEXT NOT NULL DEFAULT ''"
            ),
            "publisher_whatsapp": (
                "ALTER TABLE users ADD COLUMN publisher_whatsapp TEXT NOT NULL DEFAULT ''"
            ),
            "publisher_location": (
                "ALTER TABLE users ADD COLUMN publisher_location TEXT NOT NULL DEFAULT ''"
            ),
        }
        for column, migration in user_migrations.items():
            if column not in user_columns:
                database.execute(migration)
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS login_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              provider TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_login_events_created_at
              ON login_events (created_at DESC, id DESC);
            CREATE TABLE IF NOT EXISTS uploads (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              path TEXT NOT NULL UNIQUE,
              listing_id INTEGER REFERENCES listings(id) ON DELETE SET NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_uploads_user_created_at
              ON uploads (user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_uploads_listing
              ON uploads (listing_id);
            CREATE TABLE IF NOT EXISTS password_resets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              token_hash TEXT NOT NULL UNIQUE,
              expires_at INTEGER NOT NULL,
              used_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_password_resets_user
              ON password_resets (user_id, expires_at);
            CREATE TABLE IF NOT EXISTS reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              visitor_id TEXT NOT NULL,
              listing_id INTEGER NOT NULL,
              reason TEXT NOT NULL,
              comment TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_reports_listing_created_at
              ON reports (listing_id, created_at);
            """
        )
        login_event_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(login_events)")
        }
        login_event_migrations = {
            "ip": "ALTER TABLE login_events ADD COLUMN ip TEXT NOT NULL DEFAULT ''",
            "user_agent": (
                "ALTER TABLE login_events ADD COLUMN user_agent TEXT NOT NULL DEFAULT ''"
            ),
        }
        for column, migration in login_event_migrations.items():
            if column not in login_event_columns:
                database.execute(migration)
        database.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
              ON users (google_sub)
              WHERE google_sub IS NOT NULL
            """
        )
        # El rol admin pertenece únicamente al correo dueño configurado; corrige
        # cuentas que quedaron con un rol desactualizado tras cambiar de dueño.
        database.execute(
            "UPDATE users SET role = 'user' WHERE role = 'admin' AND email <> ?",
            (OWNER_EMAIL,),
        )
        # Solo se promueve la cuenta verificada por Google: una cuenta creada
        # con contraseña y el mismo correo no debe recibir el rol admin.
        database.execute(
            "UPDATE users SET role = 'admin' WHERE email = ? AND auth_provider = 'google'",
            (OWNER_EMAIL,),
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
        if not SEED_DEMO_DATA:
            return
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


def record_login(
    database: sqlite3.Connection,
    user_id: int,
    provider: str,
    ip: str = "",
    user_agent: str = "",
) -> None:
    """Guarda el último acceso del usuario y lo agrega al historial de actividad."""
    database.execute(
        """
        UPDATE users
        SET last_login_at = CURRENT_TIMESTAMP, last_login_provider = ?
        WHERE id = ?
        """,
        (provider, user_id),
    )
    database.execute(
        "INSERT INTO login_events (user_id, provider, ip, user_agent) VALUES (?, ?, ?, ?)",
        (user_id, provider, ip[:64], user_agent[:200]),
    )
    # El historial es para el panel del administrador; basta con lo reciente.
    database.execute(
        """
        DELETE FROM login_events
        WHERE id NOT IN (SELECT id FROM login_events ORDER BY id DESC LIMIT 500)
        """
    )


USER_PUBLIC_COLUMNS = (
    "id, name, email, avatar_url, auth_provider, role, "
    "publisher_name, publisher_whatsapp, publisher_location"
)


def _row_text(row: sqlite3.Row, key: str) -> str:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return ""
    return "" if value is None else str(value)


def user_dict(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "avatarUrl": row["avatar_url"],
        "authProvider": row["auth_provider"],
        "role": row["role"],
        "publisherName": _row_text(row, "publisher_name"),
        "publisherWhatsApp": _row_text(row, "publisher_whatsapp"),
        "publisherLocation": _row_text(row, "publisher_location"),
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


class GoogleAccountError(Exception):
    """Fallo al crear o vincular la cuenta a partir de un id_token válido."""

    def __init__(self, message: str, status: HTTPStatus):
        super().__init__(message)
        self.status = status


def masked_whatsapp(number: object) -> str:
    """Oculta el número de WhatsApp en las respuestas públicas: se conservan
    el prefijo del país y los últimos dos dígitos (ej. 519•••••••77)."""
    digits = re.sub(r"\D", "", str(number or ""))
    if len(digits) <= 5:
        return "•" * len(digits)
    return f"{digits[:3]}{'•' * (len(digits) - 5)}{digits[-2:]}"


def normalize_peru_whatsapp(value: object) -> str | None:
    """Valida y normaliza un celular peruano: 9 dígitos que empiezan con 9,
    guardado siempre como 51XXXXXXXXX. Acepta «9XXXXXXXX», «519XXXXXXXX» y
    variantes con espacios, guiones o el prefijo +."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 9 and digits.startswith("9"):
        return f"51{digits}"
    if len(digits) == 11 and digits.startswith("519"):
        return digits
    return None


def reveal_publisher_whatsapp(listing: sqlite3.Row) -> str | None:
    """Número E.164 del anunciante para «Contactar». Primero el del anuncio,
    luego el perfil guardado. Si ninguno es un celular peruano válido, no se
    inventa ni se sustituye por el WhatsApp del sitio."""
    for key in ("owner_whatsapp", "publisher_whatsapp"):
        try:
            value = listing[key]
        except (IndexError, KeyError):
            continue
        normalized = normalize_peru_whatsapp(value)
        if normalized:
            return normalized
    return None


def persist_publisher_profile(
    database: sqlite3.Connection,
    user_id: int,
    *,
    name: str = "",
    whatsapp: str = "",
    location: str = "",
) -> None:
    """Guarda el perfil de publicación. Nunca pisa un valor existente con
    una cadena vacía: si el cliente omite un campo, se conserva lo anterior."""
    assignments: list[str] = []
    values: list[object] = []
    clean_name = str(name or "").strip()
    if 1 <= len(clean_name) <= 80:
        assignments.append("publisher_name = ?")
        values.append(clean_name)
    normalized_whatsapp = (
        normalize_peru_whatsapp(whatsapp) if str(whatsapp or "").strip() else None
    )
    if normalized_whatsapp:
        assignments.append("publisher_whatsapp = ?")
        values.append(normalized_whatsapp)
    clean_location = str(location or "").strip()
    if 1 <= len(clean_location) <= 160:
        assignments.append("publisher_location = ?")
        values.append(clean_location)
    if not assignments:
        return
    values.append(user_id)
    database.execute(
        f"UPDATE users SET {', '.join(assignments)} WHERE id = ?",
        values,
    )


def listing_dict(row: sqlite3.Row, include_contact: bool = False) -> dict[str, object]:
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
        # El número completo solo viaja al dueño del anuncio o al administrador.
        # Los visitantes reciben una versión enmascarada y obtienen el número
        # real recién al registrar la consulta (POST /api/inquiries).
        "ownerWhatsApp": (
            row["owner_whatsapp"] if include_contact else masked_whatsapp(row["owner_whatsapp"])
        ),
        "ownerWhatsAppMasked": not include_contact,
        "service": row["service"],
        "details": details,
        "status": row["status"],
        # Los anuncios sembrados como demostración no pertenecen a ningún
        # usuario (user_id NULL); la interfaz los marca como «Ejemplo» para no
        # presentarlos como anuncios reales.
        "isDemo": row["user_id"] is None,
    }


def owned_listing_dict(row: sqlite3.Row) -> dict[str, object]:
    data = listing_dict(row, include_contact=True)
    data["createdAt"] = row["created_at"]
    data["updatedAt"] = row["updated_at"]
    data["inquiries"] = row["inquiry_count"]
    data["favorites"] = row["favorite_count"]
    return data


LISTING_COUNTS_SQL = """
    (SELECT COUNT(*) FROM inquiries WHERE inquiries.listing_id = listings.id) AS inquiry_count,
    (SELECT COUNT(*) FROM favorites WHERE favorites.listing_id = listings.id) AS favorite_count
"""


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


def canonical_category(value: object) -> str:
    """Traduce el alias público («Estadías») a la categoría guardada en la
    base de datos («Airbnb»); el resto de categorías pasa sin cambios."""
    text = str(value or "").strip()
    return CATEGORY_ALIASES.get(text, text)


def parse_price(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Precio inválido") from error


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


def extract_multipart_files(
    content_type: str, body: bytes, field_names: tuple[str, ...] = ("files", "file")
) -> list[tuple[bytes, str]]:
    """Extrae los archivos de un cuerpo multipart/form-data sin el módulo cgi
    (eliminado en Python 3.13), usando el parser MIME de la stdlib. Acepta el
    campo repetido `files` (varias fotos) y el campo `file` (una sola foto)."""
    header = (
        b"Content-Type: "
        + content_type.encode("latin-1", "ignore")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
    )
    try:
        message = BytesParser(policy=email_policy.default).parsebytes(header + body)
    except Exception:
        return []
    if not message.is_multipart():
        return []
    files: list[tuple[bytes, str]] = []
    for part in message.iter_parts():
        if part.get_param("name", header="content-disposition") not in field_names:
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes) or not payload:
            continue
        files.append((payload, part.get_content_type()))
    return files


HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


def image_extension_from_content(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    # Contenedor ISO BMFF con marca HEIC/HEIF (fotos de iPhone).
    if len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in HEIC_BRANDS:
        return "heic"
    return None


def load_pillow():
    """Devuelve (Image, ImageOps) de Pillow o None si no está instalada.
    En producción la librería viaja junto al verificador de Google en
    `.server_vendor`; si falta, las fotos se guardan tal cual llegaron."""
    if GOOGLE_VENDOR_DIR.is_dir() and str(GOOGLE_VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(GOOGLE_VENDOR_DIR))
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    return Image, ImageOps


def enable_heic_support() -> bool:
    """Registra el decodificador HEIC de pillow-heif (si está instalado) para
    que Pillow pueda abrir fotos de iPhone. Devuelve True si quedó activo."""
    if GOOGLE_VENDOR_DIR.is_dir() and str(GOOGLE_VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(GOOGLE_VENDOR_DIR))
    try:
        from pillow_heif import register_heif_opener
    except ImportError:
        return False
    register_heif_opener()
    return True


def process_upload_image(content: bytes, extension: str) -> tuple[bytes, str]:
    """Redimensiona la foto a un tamaño profesional: entra en 1600×1200 sin
    agrandar imágenes pequeñas, se convierte a JPEG progresivo (o WebP si ya
    era WebP) y se eliminan los metadatos EXIF. Si Pillow no está disponible
    se conserva el archivo original, salvo HEIC: una foto HEIC que no se puede
    convertir falla con un mensaje claro en vez de guardar un original que los
    navegadores no muestran."""
    pillow = load_pillow()
    if extension == "heic" and (pillow is None or not enable_heic_support()):
        raise ValueError(HEIC_MESSAGE)
    if pillow is None:
        return content, extension
    image_module, image_ops = pillow
    try:
        with image_module.open(io.BytesIO(content)) as source:
            source.load()
            image = image_ops.exif_transpose(source)
    except Exception as error:
        if extension == "heic":
            raise ValueError(HEIC_MESSAGE) from error
        raise ValueError("La imagen está dañada o no se pudo procesar") from error
    # thumbnail() encaja dentro del máximo manteniendo proporción y nunca
    # agranda una imagen más pequeña que el límite.
    image.thumbnail((PHOTO_MAX_WIDTH, PHOTO_MAX_HEIGHT), image_module.Resampling.LANCZOS)
    output = io.BytesIO()
    if extension == "webp":
        image.save(output, format="WEBP", quality=PHOTO_QUALITY, method=4)
        return output.getvalue(), "webp"
    if image.mode in {"RGBA", "LA", "P", "PA"}:
        overlay = image.convert("RGBA")
        flattened = image_module.new("RGB", overlay.size, (255, 255, 255))
        flattened.paste(overlay, mask=overlay.getchannel("A"))
        image = flattened
    elif image.mode != "RGB":
        image = image.convert("RGB")
    image.save(output, format="JPEG", quality=PHOTO_QUALITY, progressive=True, optimize=True)
    return output.getvalue(), "jpg"


def upload_file_path(url: str) -> Path | None:
    """Convierte una URL /api/uploads/… en la ruta segura del archivo en
    disco, o None si no corresponde a una foto subida."""
    if not url.startswith("/api/uploads/"):
        return None
    relative = unquote(url.removeprefix("/api/uploads/")).strip("/")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}/[A-Za-z0-9-]+\.(jpg|png|webp|gif)", relative):
        return None
    file_path = (UPLOADS_DIR / relative).resolve()
    if UPLOADS_DIR.resolve() not in file_path.parents:
        return None
    return file_path


def delete_upload_files(urls: list[str]) -> None:
    """Borra del disco las fotos subidas de un anuncio (mejor esfuerzo)."""
    for url in urls:
        file_path = upload_file_path(str(url))
        if file_path is None:
            continue
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass


def cleanup_orphan_uploads(user_id: int) -> None:
    """Limpieza de mejor esfuerzo: borra las fotos que este usuario subió hace
    más de un día y nunca adjuntó a un anuncio (archivo y registro)."""
    with connect() as database:
        rows = database.execute(
            """
            SELECT id, path FROM uploads
            WHERE user_id = ? AND listing_id IS NULL
              AND created_at < datetime('now', '-1 day')
            """,
            (user_id,),
        ).fetchall()
        if not rows:
            return
        delete_upload_files([row["path"] for row in rows])
        database.execute(
            f"DELETE FROM uploads WHERE id IN ({','.join('?' for _ in rows)})",
            [row["id"] for row in rows],
        )


def listings_query(parameters: dict[str, list[str]]) -> tuple[list[sqlite3.Row], dict[str, object]]:
    category = canonical_category(parameters.get("category", [""])[0])
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

    # Filtros de Roomies sobre details_json estructurado (nada de LIKE).
    bathroom = str(parameters.get("bathroom", [""])[0]).strip()
    if bathroom and bathroom not in ROOMIE_BATHROOM_OPTIONS:
        raise ValueError("Filtro de baño inválido")
    services_included = str(parameters.get("servicesIncluded", [""])[0]).strip().lower()
    if services_included and services_included not in {"1", "true", "si", "sí"}:
        raise ValueError("Filtro de servicios inválido")

    # Filtros de Estadías: comodidades y búsqueda con fechas y huéspedes.
    requested_amenities = [
        amenity.strip()
        for amenity in str(parameters.get("amenities", [""])[0]).split(",")
        if amenity.strip()
    ]
    if any(amenity not in STAY_AMENITIES for amenity in requested_amenities):
        raise ValueError("Comodidad inválida")
    check_in = str(parameters.get("checkIn", [""])[0]).strip()
    check_out = str(parameters.get("checkOut", [""])[0]).strip()
    for stay_date in (check_in, check_out):
        if stay_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stay_date):
            raise ValueError("Fecha inválida")
    if check_in and check_out and check_out <= check_in:
        raise ValueError("La salida debe ser posterior a la llegada")
    guests = optional_integer(parameters.get("guests", [None])[0], 1, 16)

    page = optional_integer(parameters.get("page", ["1"])[0], 1, 10_000) or 1
    page_size = optional_integer(parameters.get("pageSize", ["12"])[0], 1, 48) or 12
    sort = str(parameters.get("sort", ["recommended"])[0]).strip()
    sort = LISTING_SORT_ALIASES.get(sort, sort)
    if sort not in LISTING_SORTS:
        raise ValueError("Orden inválido")

    # Solo los anuncios publicados son visibles en la lista pública; los
    # pendientes, pausados, alquilados o rechazados no aparecen.
    clauses: list[str] = ["status = 'published'"]
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
        # El filtro de dormitorios usa bedroomsMin/Max (Depas) o bedrooms
        # (Estadías / Roomies) cuando el campo existe; un anuncio sin ese dato
        # no se oculta: solo se filtra cuando hay una restricción real.
        maximum_expression = (
            "CASE WHEN json_valid(details_json) THEN COALESCE("
            "json_extract(details_json, '$.bedroomsMax'), "
            "json_extract(details_json, '$.bedrooms')) END"
        )
        minimum_expression = (
            "CASE WHEN json_valid(details_json) THEN COALESCE("
            "json_extract(details_json, '$.bedroomsMin'), "
            "json_extract(details_json, '$.bedrooms')) END"
        )
        clauses.append(
            f"({maximum_expression} IS NULL OR CAST({maximum_expression} AS INTEGER) >= ?)"
        )
        values.append(bedrooms)
        if bedrooms_value != "4+":
            clauses.append(
                f"({minimum_expression} IS NULL OR CAST({minimum_expression} AS INTEGER) <= ?)"
            )
            values.append(bedrooms)
    for feature in requested_features:
        # Coincidencia estructurada dentro del arreglo JSON de características.
        clauses.append(
            "(json_valid(details_json) AND EXISTS ("
            "SELECT 1 FROM json_each(details_json, '$.features') "
            "WHERE json_each.value = ?))"
        )
        values.append(feature)
    if bathroom:
        clauses.append(
            "(json_valid(details_json) "
            "AND json_extract(details_json, '$.bathroom') = ?)"
        )
        values.append(bathroom)
    if services_included:
        clauses.append(
            "(json_valid(details_json) "
            "AND CAST(json_extract(details_json, '$.servicesIncluded') AS INTEGER) = 1)"
        )
    for amenity in requested_amenities:
        clauses.append(
            "(json_valid(details_json) AND EXISTS ("
            "SELECT 1 FROM json_each(details_json, '$.amenities') "
            "WHERE json_each.value = ?))"
        )
        values.append(amenity)
    if guests is not None and category == "Airbnb":
        # Capacidad real de la estadía. Un anuncio sin el dato (por ejemplo,
        # los de demostración) no se oculta. Los anuncios no guardan un
        # calendario de disponibilidad, así que checkIn/checkOut se validan y
        # se tratan como «siempre disponible» hasta que exista ese dato.
        guests_expression = (
            "CASE WHEN json_valid(details_json) "
            "THEN json_extract(details_json, '$.guests') END"
        )
        clauses.append(
            f"({guests_expression} IS NULL OR CAST({guests_expression} AS INTEGER) >= ?)"
        )
        values.append(guests)

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
            "SELECT COUNT(*) FROM listings WHERE status = 'published'"
            + (" AND category = ?" if category else ""),
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


def sanitize_roomies_details(value: object) -> dict[str, object]:
    source = value if isinstance(value, dict) else {}
    bathroom = str(source.get("bathroom", "")).strip()
    if bathroom not in ROOMIE_BATHROOM_OPTIONS:
        bathroom = "Compartido"
    bed = str(source.get("bed", "")).strip()
    if bed not in ROOMIE_BED_OPTIONS:
        bed = "1 plaza"
    return {
        "bathroom": bathroom,
        "bed": bed,
        "furnished": bool(source.get("furnished")),
        "servicesIncluded": bool(source.get("servicesIncluded")),
    }


def sanitize_stay_details(value: object) -> dict[str, object]:
    source = value if isinstance(value, dict) else {}
    amenities_value = source.get("amenities")
    amenities_source = amenities_value if isinstance(amenities_value, list) else []
    amenities = [amenity for amenity in STAY_AMENITIES if amenity in amenities_source]
    return {
        "guests": bounded_integer(source.get("guests"), 1, 16, 2),
        "bedrooms": bounded_integer(source.get("bedrooms"), 1, 20, 1),
        "beds": bounded_integer(source.get("beds"), 1, 30, 1),
        "bathrooms": bounded_integer(source.get("bathrooms"), 1, 20, 1),
        "amenities": amenities,
    }


def sanitize_transport_details(value: object) -> dict[str, object]:
    source = value if isinstance(value, dict) else {}

    def clean_text(key: str, limit: int) -> str:
        return str(source.get(key, "")).strip()[:limit]

    return {
        "vehicle": clean_text("vehicle", 80),
        "capacity": clean_text("capacity", 80),
        "coverage": clean_text("coverage", 120),
    }


def count_range_label(minimum: int, maximum: int, singular: str, plural: str) -> str:
    if minimum == maximum:
        return f"{minimum} {singular if minimum == 1 else plural}"
    return f"{minimum} a {maximum} {plural}"


def build_listing_meta(category: str, details: dict[str, object], service: str | None) -> str:
    """Resumen corto que se muestra en la tarjeta, construido con los datos
    saneados de cada categoría (ej. «1 cama · 1 baño compartido · Amoblado»)."""
    if category == "Roomies":
        bed = str(details["bed"])
        parts = [
            "1 cama" if bed == "1 plaza" else f"1 cama de {bed}",
            "1 baño privado" if details["bathroom"] == "Privado" else "1 baño compartido",
            "Amoblado" if details["furnished"] else "Sin amoblar",
        ]
        if details["servicesIncluded"]:
            parts.append("Incluye servicios")
        return " · ".join(parts)
    if category == "Depas":
        return " · ".join(
            (
                count_range_label(
                    int(details["bedroomsMin"]), int(details["bedroomsMax"]),
                    "dormitorio", "dormitorios",
                ),
                count_range_label(
                    int(details["bathroomsMin"]), int(details["bathroomsMax"]),
                    "baño", "baños",
                ),
                str(details["areaTotal"]),
            )
        )
    if category == "Airbnb":
        guests = int(details["guests"])
        bedrooms = int(details["bedrooms"])
        amenities = details["amenities"] if isinstance(details["amenities"], list) else []
        parts = [
            f"{guests} {'huésped' if guests == 1 else 'huéspedes'}",
            f"{bedrooms} {'habitación' if bedrooms == 1 else 'habitaciones'}",
        ]
        if amenities:
            parts.append(str(amenities[0]))
        else:
            beds = int(details["beds"])
            parts.append(f"{beds} {'cama' if beds == 1 else 'camas'}")
        return " · ".join(parts)
    # Transporte
    parts = [
        str(details.get(key, "")).strip()
        for key in ("vehicle", "capacity", "coverage")
        if str(details.get(key, "")).strip()
    ]
    if not parts:
        parts = [service or "Servicio de transporte"]
    return " · ".join(parts[:3])


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
            "img-src 'self' data: blob: https://images.unsplash.com https://lh3.googleusercontent.com; "
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
        oauth_state_value: str | None = None,
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
            self.send_header("Set-Cookie", session_cookie_header(session_token))
        if oauth_state_value:
            self.send_header("Set-Cookie", oauth_state_cookie_header(oauth_state_value))
        if clear_session:
            for cookie in cleared_session_cookie_headers():
                self.send_header("Set-Cookie", cookie)
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
            if len(_RATE_LIMIT_BUCKETS) > 5_000:
                cutoff = now - 3600
                stale_keys = [
                    bucket_key
                    for bucket_key, timestamps in _RATE_LIMIT_BUCKETS.items()
                    if not timestamps or timestamps[-1] <= cutoff
                ]
                for bucket_key in stale_keys:
                    del _RATE_LIMIT_BUCKETS[bucket_key]
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
                       users.auth_provider, users.role,
                       users.publisher_name, users.publisher_whatsapp,
                       users.publisher_location
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
            self.send_api_error(
                "Inicia sesión para continuar.",
                HTTPStatus.UNAUTHORIZED,
                "unauthorized",
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
            except sqlite3.Error:
                self.send_api_error(
                    "La base de datos no está disponible.",
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "database_unavailable",
                )
                return
            uploads_usable = False
            uploads_free_bytes = 0
            try:
                UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
                uploads_free_bytes = shutil.disk_usage(UPLOADS_DIR).free
                uploads_usable = (
                    os.access(UPLOADS_DIR, os.W_OK)
                    and uploads_free_bytes > 64 * 1024 * 1024
                )
            except OSError:
                uploads_usable = False
            self.send_json(
                {
                    "ok": True,
                    "database": True,
                    "uploads": uploads_usable,
                    "uploadsFreeBytes": uploads_free_bytes,
                    "version": RELEASE_VERSION,
                }
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
        if parsed.path == "/api/auth/google/start":
            self.google_oauth_start()
            return
        if parsed.path == OAUTH_CALLBACK_PATH:
            # Google entrega el id_token con POST; un GET aquí es una recarga
            # o una cancelación, así que se vuelve al inicio sin sesión.
            self.send_redirect("/", HTTPStatus.FOUND, clear_oauth_state=True)
            return
        if parsed.path == "/api/listings":
            # Límite de lectura moderado compartido entre la lista y el
            # detalle: reduce el raspado masivo sin frenar la navegación.
            if not self.check_rate_limit("GET", "/api/listings"):
                return
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
        listing_match = re.fullmatch(r"/api/listings/(\d{1,10})", parsed.path)
        if listing_match:
            if not self.check_rate_limit("GET", "/api/listings"):
                return
            self.get_listing(int(listing_match.group(1)))
            return
        if parsed.path == "/api/inquiries":
            self.list_inquiries(parse_qs(parsed.query, keep_blank_values=True))
            return
        if parsed.path in {"/api/auth/me", "/api/me"}:
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
        if parsed.path == "/api/favorites/listings":
            # Anuncios completos de los favoritos del visitante (cookie), en el
            # orden en que se guardaron: alimenta la hoja «Mis favoritos» sin
            # depender de qué categoría esté cargada en la portada.
            visitor_id, is_new = self.visitor()
            with connect() as database:
                rows = database.execute(
                    """
                    SELECT listings.*
                    FROM favorites
                    JOIN listings ON listings.id = favorites.listing_id
                    WHERE favorites.visitor_id = ?
                    ORDER BY favorites.created_at, favorites.listing_id
                    """,
                    (visitor_id,),
                ).fetchall()
            self.send_json(
                {"listings": [listing_dict(row) for row in rows]},
                visitor_id=visitor_id if is_new else None,
            )
            return
        if parsed.path == "/api/my/listings":
            self.my_listings()
            return
        if parsed.path.startswith("/api/admin/"):
            self.handle_admin_get(parsed)
            return
        if parsed.path.startswith("/api/uploads/"):
            self.serve_upload(parsed.path)
            return
        if parsed.path.startswith("/api/"):
            self.send_api_error("Ruta no encontrada.", HTTPStatus.NOT_FOUND, "not_found")
            return
        if parsed.path == "/sitemap.xml":
            self.serve_sitemap()
            return
        if parsed.path == "/robots.txt":
            self.serve_robots()
            return
        self.serve_static(parsed.path)

    def require_admin(self) -> sqlite3.Row | None:
        user = self.authenticated_user()
        if user is None:
            self.send_api_error(
                "Inicia sesión para continuar.", HTTPStatus.UNAUTHORIZED, "unauthorized"
            )
            return None
        if user["role"] != "admin":
            self.send_api_error(
                "Necesitas permisos de administrador.", HTTPStatus.FORBIDDEN, "forbidden"
            )
            return None
        return user

    def get_listing(self, listing_id: int) -> None:
        """Detalle público de un anuncio (GET /api/listings/{id}), con la
        misma forma que un elemento del listado: alimenta los enlaces
        compartidos del tipo /?listing=ID. El número de WhatsApp viaja
        enmascarado salvo para el dueño del anuncio o el administrador."""
        with connect() as database:
            row = database.execute(
                "SELECT * FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
        if row is None:
            self.send_api_error(
                "La publicación ya no está disponible.",
                HTTPStatus.NOT_FOUND,
                "listing_not_found",
            )
            return
        user = self.authenticated_user()
        is_privileged = user is not None and (
            user["role"] == "admin" or row["user_id"] == user["id"]
        )
        if row["status"] != "published" and not is_privileged:
            # Un anuncio pausado, alquilado, pendiente o rechazado no es
            # visible con el enlace compartido; solo su dueño o el admin.
            self.send_api_error(
                "La publicación ya no está disponible.",
                HTTPStatus.NOT_FOUND,
                "listing_not_found",
            )
            return
        payload = {"listing": listing_dict(row, include_contact=is_privileged)}
        if is_privileged:
            self.send_json(payload)
            return
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        etag = f'"{hashlib.sha256(serialized).hexdigest()[:24]}"'
        self.send_json(
            payload,
            cache_control="public, max-age=30, stale-while-revalidate=120",
            etag=etag,
        )

    def my_listings(self) -> None:
        user = self.authenticated_user()
        if user is None:
            self.send_api_error(
                "Inicia sesión para ver tus anuncios.", HTTPStatus.UNAUTHORIZED, "unauthorized"
            )
            return
        with connect() as database:
            rows = database.execute(
                f"""
                SELECT listings.*, {LISTING_COUNTS_SQL}
                FROM listings
                WHERE listings.user_id = ?
                ORDER BY listings.created_at DESC, listings.id DESC
                """,
                (user["id"],),
            ).fetchall()
        self.send_json({"listings": [owned_listing_dict(row) for row in rows]})

    def list_inquiries(self, parameters: dict[str, list[str]]) -> None:
        """Consultas recibidas por los anuncios del usuario con sesión (o de
        cualquier anuncio para el administrador). Incluye mensaje y fechas."""
        user = self.require_user()
        if user is None:
            return
        try:
            listing_id = optional_integer(
                parameters.get("listingId", [None])[0], 1, 2_000_000_000
            )
        except ValueError:
            self.send_api_error(
                "Publicación inválida.", HTTPStatus.BAD_REQUEST, "invalid_listing"
            )
            return
        clauses = []
        values: list[object] = []
        if user["role"] != "admin":
            clauses.append("listings.user_id = ?")
            values.append(user["id"])
        if listing_id is not None:
            clauses.append("inquiries.listing_id = ?")
            values.append(listing_id)
        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect() as database:
            rows = database.execute(
                f"""
                SELECT inquiries.id, inquiries.listing_id, inquiries.channel,
                       inquiries.message, inquiries.check_in, inquiries.check_out,
                       inquiries.guests, inquiries.created_at,
                       listings.title, listings.category
                FROM inquiries JOIN listings ON listings.id = inquiries.listing_id
                {where_clause}
                ORDER BY inquiries.created_at DESC, inquiries.id DESC
                LIMIT 100
                """,
                values,
            ).fetchall()
        self.send_json(
            {
                "inquiries": [
                    {
                        "id": row["id"],
                        "listingId": row["listing_id"],
                        "title": row["title"],
                        "category": row["category"],
                        "channel": row["channel"],
                        "message": row["message"],
                        "checkIn": row["check_in"],
                        "checkOut": row["check_out"],
                        "guests": row["guests"],
                        "createdAt": row["created_at"],
                    }
                    for row in rows
                ]
            }
        )

    def serve_sitemap(self) -> None:
        """Mapa del sitio real: portada, categorías públicas y cada anuncio
        publicado con su enlace compartible (?listing=ID)."""
        with connect() as database:
            rows = database.execute(
                """
                SELECT id, COALESCE(updated_at, created_at) AS last_modified
                FROM listings WHERE status = 'published'
                ORDER BY id
                LIMIT 5000
                """
            ).fetchall()
        entries = [f"<url><loc>{SITE_BASE_URL}/</loc></url>"]
        for public_name in ("Roomies", "Depas", "Estad%C3%ADas", "Transporte"):
            entries.append(
                f"<url><loc>{SITE_BASE_URL}/?category={public_name}</loc></url>"
            )
        for row in rows:
            last_modified = str(row["last_modified"] or "")[:10]
            lastmod = f"<lastmod>{last_modified}</lastmod>" if last_modified else ""
            entries.append(
                f"<url><loc>{SITE_BASE_URL}/?listing={row['id']}</loc>{lastmod}</url>"
            )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(entries)
            + "</urlset>\n"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def serve_robots(self) -> None:
        body = (
            "User-agent: *\n"
            "Allow: /api/uploads/\n"
            "Disallow: /api/\n"
            f"Sitemap: {SITE_BASE_URL}/sitemap.xml\n"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def handle_admin_get(self, parsed) -> None:
        if self.require_admin() is None:
            return
        if parsed.path == "/api/admin/overview":
            self.admin_overview()
        elif parsed.path == "/api/admin/listings":
            self.admin_listings(parse_qs(parsed.query, keep_blank_values=True))
        elif parsed.path == "/api/admin/users":
            self.admin_users(parse_qs(parsed.query, keep_blank_values=True))
        elif parsed.path == "/api/admin/inquiries":
            self.admin_inquiries()
        elif parsed.path == "/api/admin/activity":
            self.admin_activity()
        elif parsed.path == "/api/admin/reports":
            self.admin_reports()
        else:
            self.send_api_error("Ruta no encontrada.", HTTPStatus.NOT_FOUND, "not_found")

    def admin_overview(self) -> None:
        with connect() as database:
            listings_total = database.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            by_category = {
                row["category"]: row["total"]
                for row in database.execute(
                    "SELECT category, COUNT(*) AS total FROM listings GROUP BY category"
                )
            }
            users_total = database.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            favorites_total = database.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
            inquiries_total = database.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0]
            inquiries_week = database.execute(
                "SELECT COUNT(*) FROM inquiries WHERE created_at >= datetime('now', '-7 days')"
            ).fetchone()[0]
            top_rows = database.execute(
                """
                SELECT listings.id, listings.title, listings.category,
                       COUNT(inquiries.id) AS total
                FROM inquiries JOIN listings ON listings.id = inquiries.listing_id
                GROUP BY inquiries.listing_id
                ORDER BY total DESC, listings.id DESC
                LIMIT 5
                """
            ).fetchall()
            recent_rows = database.execute(
                """
                SELECT id, title, category, price, created_at
                FROM listings ORDER BY created_at DESC, id DESC LIMIT 5
                """
            ).fetchall()
        self.send_json(
            {
                "stats": {
                    "listings": listings_total,
                    "byCategory": by_category,
                    "users": users_total,
                    "favorites": favorites_total,
                    "inquiries": inquiries_total,
                    "inquiriesLast7Days": inquiries_week,
                },
                "topListings": [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "category": row["category"],
                        "total": row["total"],
                    }
                    for row in top_rows
                ],
                "recentListings": [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "category": row["category"],
                        "price": row["price"],
                        "createdAt": row["created_at"],
                    }
                    for row in recent_rows
                ],
            }
        )

    def admin_listings(self, parameters: dict[str, list[str]]) -> None:
        category = canonical_category(parameters.get("category", [""])[0])
        if category and category not in CATEGORIES:
            self.send_api_error("Categoría inválida.", HTTPStatus.BAD_REQUEST, "invalid_filters")
            return
        try:
            page = optional_integer(parameters.get("page", ["1"])[0], 1, 10_000) or 1
            page_size = optional_integer(parameters.get("pageSize", ["10"])[0], 1, 50) or 10
        except ValueError:
            self.send_api_error("Paginación inválida.", HTTPStatus.BAD_REQUEST, "invalid_filters")
            return
        status_filter = str(parameters.get("status", [""])[0]).strip()
        if status_filter and status_filter not in LISTING_STATUSES:
            self.send_api_error("Estado inválido.", HTTPStatus.BAD_REQUEST, "invalid_filters")
            return
        # Separa anuncios reales (con dueño) de los sembrados de demostración.
        origin_filter = str(parameters.get("origin", [""])[0]).strip()
        if origin_filter and origin_filter not in {"demo", "real"}:
            self.send_api_error("Filtro inválido.", HTTPStatus.BAD_REQUEST, "invalid_filters")
            return
        query_text = str(parameters.get("q", [""])[0]).strip()[:120]
        clauses: list[str] = []
        values: list[object] = []
        if category:
            clauses.append("listings.category = ?")
            values.append(category)
        if status_filter:
            clauses.append("listings.status = ?")
            values.append(status_filter)
        if origin_filter == "demo":
            clauses.append("listings.user_id IS NULL")
        elif origin_filter == "real":
            clauses.append("listings.user_id IS NOT NULL")
        if query_text:
            clauses.append(
                "search_matches(search_normalize(listings.title || ' ' || "
                "listings.location || ' ' || listings.owner_name), ?) = 1"
            )
            values.append(normalize_search_text(query_text))
        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with connect() as database:
            total = database.execute(
                f"SELECT COUNT(*) FROM listings{where_clause}", values
            ).fetchone()[0]
            rows = database.execute(
                f"""
                SELECT listings.*, users.email AS owner_email, {LISTING_COUNTS_SQL}
                FROM listings LEFT JOIN users ON users.id = listings.user_id
                {where_clause}
                ORDER BY listings.created_at DESC, listings.id DESC
                LIMIT ? OFFSET ?
                """,
                [*values, page_size, offset],
            ).fetchall()
        results = []
        for row in rows:
            data = owned_listing_dict(row)
            data["ownerEmail"] = row["owner_email"]
            results.append(data)
        total_pages = max(1, math.ceil(total / page_size))
        self.send_json(
            {
                "listings": results,
                "meta": {
                    "total": total,
                    "page": page,
                    "pageSize": page_size,
                    "totalPages": total_pages,
                    "hasMore": page < total_pages,
                },
            }
        )

    def admin_users(self, parameters: dict[str, list[str]] | None = None) -> None:
        parameters = parameters or {}
        try:
            page = optional_integer(parameters.get("page", ["1"])[0], 1, 10_000) or 1
            page_size = optional_integer(parameters.get("pageSize", ["25"])[0], 1, 100) or 25
        except ValueError:
            self.send_api_error("Paginación inválida.", HTTPStatus.BAD_REQUEST, "invalid_filters")
            return
        query_text = str(parameters.get("q", [""])[0]).strip()[:120]
        clauses: list[str] = []
        values: list[object] = []
        if query_text:
            clauses.append(
                "search_matches(search_normalize(users.name || ' ' || users.email), ?) = 1"
            )
            values.append(normalize_search_text(query_text))
        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with connect() as database:
            users_total = database.execute(
                f"SELECT COUNT(*) FROM users{where_clause}", values
            ).fetchone()[0]
            rows = database.execute(
                f"""
                SELECT users.id, users.name, users.email, users.auth_provider,
                       users.role, users.created_at, users.last_login_at,
                       users.last_login_provider,
                       (SELECT COUNT(*) FROM listings
                        WHERE listings.user_id = users.id) AS listing_count
                FROM users
                {where_clause}
                ORDER BY users.last_login_at DESC, users.created_at DESC, users.id DESC
                LIMIT ? OFFSET ?
                """,
                [*values, page_size, offset],
            ).fetchall()
            category_rows = database.execute(
                """
                SELECT user_id, category, COUNT(*) AS total
                FROM listings
                WHERE user_id IS NOT NULL
                GROUP BY user_id, category
                """
            ).fetchall()
        listings_by_user: dict[int, dict[str, int]] = defaultdict(dict)
        for row in category_rows:
            listings_by_user[row["user_id"]][row["category"]] = row["total"]
        total_pages = max(1, math.ceil(users_total / page_size))
        self.send_json(
            {
                "total": users_total,
                "meta": {
                    "total": users_total,
                    "page": page,
                    "pageSize": page_size,
                    "totalPages": total_pages,
                    "hasMore": page < total_pages,
                },
                "users": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "email": row["email"],
                        "authProvider": row["auth_provider"],
                        "role": row["role"],
                        "createdAt": row["created_at"],
                        "lastLoginAt": row["last_login_at"],
                        "lastLoginProvider": row["last_login_provider"],
                        "listings": row["listing_count"],
                        "listingsByCategory": listings_by_user.get(row["id"], {}),
                    }
                    for row in rows
                ],
            }
        )

    def admin_activity(self) -> None:
        with connect() as database:
            login_rows = database.execute(
                """
                SELECT login_events.id, login_events.provider, login_events.ip,
                       login_events.user_agent, login_events.created_at,
                       users.name, users.email
                FROM login_events JOIN users ON users.id = login_events.user_id
                ORDER BY login_events.created_at DESC, login_events.id DESC
                LIMIT 60
                """
            ).fetchall()
            listing_rows = database.execute(
                """
                SELECT listings.id, listings.title, listings.category,
                       listings.created_at, users.name AS user_name,
                       users.email AS user_email, listings.owner_name
                FROM listings LEFT JOIN users ON users.id = listings.user_id
                ORDER BY listings.created_at DESC, listings.id DESC
                LIMIT 60
                """
            ).fetchall()
            logins_today = database.execute(
                "SELECT COUNT(*) FROM login_events WHERE created_at >= date('now')"
            ).fetchone()[0]
            listings_today = database.execute(
                "SELECT COUNT(*) FROM listings WHERE created_at >= date('now')"
            ).fetchone()[0]
        events: list[dict[str, object]] = []
        for row in login_rows:
            events.append(
                {
                    "type": "login",
                    "id": f"login-{row['id']}",
                    "name": row["name"],
                    "email": row["email"],
                    "provider": row["provider"],
                    "ip": row["ip"],
                    "userAgent": row["user_agent"],
                    "createdAt": row["created_at"],
                }
            )
        for row in listing_rows:
            events.append(
                {
                    "type": "listing",
                    "id": f"listing-{row['id']}",
                    "listingId": row["id"],
                    "title": row["title"],
                    "category": row["category"],
                    "name": row["user_name"] or row["owner_name"],
                    "email": row["user_email"],
                    "createdAt": row["created_at"],
                }
            )
        events.sort(key=lambda event: str(event["createdAt"]), reverse=True)
        self.send_json(
            {
                "events": events[:80],
                "today": {"logins": logins_today, "newListings": listings_today},
            }
        )

    def admin_reports(self) -> None:
        with connect() as database:
            recent = database.execute(
                """
                SELECT reports.id, reports.listing_id, reports.reason,
                       reports.comment, reports.created_at,
                       listings.title, listings.category, listings.status
                FROM reports JOIN listings ON listings.id = reports.listing_id
                ORDER BY reports.created_at DESC, reports.id DESC
                LIMIT 100
                """
            ).fetchall()
            by_listing = database.execute(
                """
                SELECT listings.id, listings.title, listings.category,
                       COUNT(reports.id) AS total
                FROM reports JOIN listings ON listings.id = reports.listing_id
                GROUP BY reports.listing_id
                ORDER BY total DESC, listings.id DESC
                LIMIT 20
                """
            ).fetchall()
        self.send_json(
            {
                "recent": [
                    {
                        "id": row["id"],
                        "listingId": row["listing_id"],
                        "title": row["title"],
                        "category": row["category"],
                        "status": row["status"],
                        "reason": row["reason"],
                        "comment": row["comment"],
                        "createdAt": row["created_at"],
                    }
                    for row in recent
                ],
                "byListing": [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "category": row["category"],
                        "total": row["total"],
                    }
                    for row in by_listing
                ],
            }
        )

    def admin_inquiries(self) -> None:
        with connect() as database:
            recent = database.execute(
                """
                SELECT inquiries.id, inquiries.listing_id, inquiries.channel,
                       inquiries.created_at, listings.title, listings.category
                FROM inquiries JOIN listings ON listings.id = inquiries.listing_id
                ORDER BY inquiries.created_at DESC, inquiries.id DESC
                LIMIT 50
                """
            ).fetchall()
            by_listing = database.execute(
                """
                SELECT listings.id, listings.title, listings.category,
                       COUNT(inquiries.id) AS total
                FROM inquiries JOIN listings ON listings.id = inquiries.listing_id
                GROUP BY inquiries.listing_id
                ORDER BY total DESC, listings.id DESC
                LIMIT 20
                """
            ).fetchall()
        self.send_json(
            {
                "recent": [
                    {
                        "id": row["id"],
                        "listingId": row["listing_id"],
                        "channel": row["channel"],
                        "createdAt": row["created_at"],
                        "title": row["title"],
                        "category": row["category"],
                    }
                    for row in recent
                ],
                "byListing": [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "category": row["category"],
                        "total": row["total"],
                    }
                    for row in by_listing
                ],
            }
        )

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
            elif parsed.path == OAUTH_CALLBACK_PATH:
                self.google_oauth_callback()
            elif parsed.path == "/api/auth/logout":
                self.logout_user()
            elif parsed.path == "/api/auth/logout-all":
                self.logout_all_sessions()
            elif parsed.path == "/api/auth/password/forgot":
                self.request_password_reset()
            elif parsed.path == "/api/auth/password/reset":
                self.reset_password()
            elif parsed.path == "/api/listings":
                self.create_listing()
            elif parsed.path == "/api/favorites":
                self.save_favorite()
            elif parsed.path == "/api/inquiries":
                self.create_inquiry()
            elif parsed.path == "/api/reports":
                self.create_report()
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
        listing_match = re.fullmatch(r"/api/listings/(\d{1,10})", path)
        if listing_match:
            if not self.check_rate_limit("DELETE", "/api/listings"):
                return
            try:
                self.delete_listing(int(listing_match.group(1)))
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
            return
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

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/api/auth/me", "/api/me"}:
            if not self.check_rate_limit("PATCH", "/api/auth/me"):
                return
            try:
                self.update_publisher_profile()
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
            return
        listing_match = re.fullmatch(r"/api/listings/(\d{1,10})", path)
        if not listing_match:
            self.send_api_error("Ruta no encontrada.", HTTPStatus.NOT_FOUND, "not_found")
            return
        if not self.check_rate_limit("PATCH", "/api/listings"):
            return
        try:
            self.update_listing(int(listing_match.group(1)))
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

    def delete_listing(self, listing_id: int) -> None:
        user = self.require_user()
        if user is None:
            return
        with connect() as database:
            row = database.execute(
                "SELECT id, user_id, gallery, image FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()
            if row is None:
                self.send_api_error(
                    "La publicación ya no está disponible.",
                    HTTPStatus.NOT_FOUND,
                    "listing_not_found",
                )
                return
            if user["role"] != "admin" and row["user_id"] != user["id"]:
                self.send_api_error(
                    "Solo puedes eliminar tus propios anuncios.",
                    HTTPStatus.FORBIDDEN,
                    "forbidden",
                )
                return
            try:
                gallery = json.loads(row["gallery"] or "[]")
            except (json.JSONDecodeError, TypeError):
                gallery = []
            upload_urls = {
                str(url)
                for url in [*gallery, row["image"]]
                if str(url).startswith("/api/uploads/")
            }
            database.execute("DELETE FROM favorites WHERE listing_id = ?", (listing_id,))
            database.execute("DELETE FROM inquiries WHERE listing_id = ?", (listing_id,))
            database.execute("DELETE FROM reports WHERE listing_id = ?", (listing_id,))
            database.execute("DELETE FROM uploads WHERE listing_id = ?", (listing_id,))
            database.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        # Con el anuncio fuera de la base, sus fotos se borran del disco.
        delete_upload_files(sorted(upload_urls))
        self.send_json({"deleted": True, "listingId": listing_id})

    def update_listing(self, listing_id: int) -> None:
        user = self.require_user()
        if user is None:
            return
        payload = self.read_json()
        with connect() as database:
            row = database.execute(
                "SELECT * FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
            if row is None:
                self.send_api_error(
                    "La publicación ya no está disponible.",
                    HTTPStatus.NOT_FOUND,
                    "listing_not_found",
                )
                return
            is_admin = user["role"] == "admin"
            if not is_admin and row["user_id"] != user["id"]:
                self.send_api_error(
                    "Solo puedes editar tus propios anuncios.",
                    HTTPStatus.FORBIDDEN,
                    "forbidden",
                )
                return

            updates: dict[str, object] = {}
            if "title" in payload:
                title = str(payload["title"]).strip()
                if not 1 <= len(title) <= 120:
                    self.send_json({"error": "El título no es válido."}, HTTPStatus.BAD_REQUEST)
                    return
                updates["title"] = title
            if "location" in payload:
                location = str(payload["location"]).strip()
                if not 1 <= len(location) <= 160:
                    self.send_json({"error": "La ubicación no es válida."}, HTTPStatus.BAD_REQUEST)
                    return
                updates["location"] = location
            if "description" in payload:
                description = str(payload["description"]).strip()
                if not 1 <= len(description) <= 2_000:
                    self.send_json({"error": "La descripción no es válida."}, HTTPStatus.BAD_REQUEST)
                    return
                updates["description"] = description
            if "price" in payload:
                price = parse_price(payload["price"])
                if price <= 0 or price > 10_000_000:
                    self.send_json({"error": "El precio no es válido."}, HTTPStatus.BAD_REQUEST)
                    return
                updates["price"] = price
            if "ownerName" in payload:
                owner_name = str(payload["ownerName"]).strip()
                if not 1 <= len(owner_name) <= 80:
                    self.send_json({"error": "El nombre no es válido."}, HTTPStatus.BAD_REQUEST)
                    return
                updates["owner_name"] = owner_name
            if "ownerWhatsApp" in payload:
                owner_whatsapp = normalize_peru_whatsapp(payload["ownerWhatsApp"])
                if owner_whatsapp is None:
                    self.send_json(
                        {
                            "error": (
                                "Ingresa un WhatsApp peruano válido: un celular "
                                "de 9 dígitos que empiece con 9."
                            )
                        },
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                updates["owner_whatsapp"] = owner_whatsapp
            if "status" in payload:
                new_status = str(payload["status"] or "").strip()
                if new_status not in LISTING_STATUSES:
                    self.send_json({"error": "Estado inválido."}, HTTPStatus.BAD_REQUEST)
                    return
                # El dueño pausa, reanuda, marca alquilado o republica sus
                # anuncios ya aprobados; aprobar un anuncio pendiente o
                # rechazado es exclusivo del administrador.
                if not is_admin and (
                    new_status not in OWNER_STATUS_CHOICES
                    or row["status"] not in OWNER_STATUS_CHOICES
                ):
                    self.send_json(
                        {"error": "Ese cambio de estado lo aprueba el administrador."},
                        HTTPStatus.FORBIDDEN,
                    )
                    return
                updates["status"] = new_status
            if is_admin and "badge" in payload:
                badge = str(payload["badge"] or "").strip()[:60]
                updates["badge"] = badge or None
            if not updates:
                self.send_json({"error": "No hay cambios para guardar."}, HTTPStatus.BAD_REQUEST)
                return
            assignments = ", ".join(f"{column} = ?" for column in updates)
            database.execute(
                f"UPDATE listings SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [*updates.values(), listing_id],
            )
            persist_publisher_profile(
                database,
                int(user["id"]),
                name=str(updates.get("owner_name") or ""),
                whatsapp=str(updates.get("owner_whatsapp") or ""),
                location=str(updates.get("location") or ""),
            )
            updated = database.execute(
                "SELECT * FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
        self.send_json({"listing": listing_dict(updated, include_contact=True)})

    def update_publisher_profile(self) -> None:
        user = self.require_user()
        if user is None:
            return
        payload = self.read_json()
        name = str(
            payload.get("publisherName") or payload.get("ownerName") or ""
        ).strip()
        whatsapp_raw = payload.get("publisherWhatsApp")
        if whatsapp_raw is None:
            whatsapp_raw = payload.get("ownerWhatsApp")
        location = str(
            payload.get("publisherLocation") or payload.get("location") or ""
        ).strip()
        if name and not 1 <= len(name) <= 80:
            self.send_json({"error": "El nombre no es válido."}, HTTPStatus.BAD_REQUEST)
            return
        if location and len(location) > 160:
            self.send_json({"error": "La ubicación no es válida."}, HTTPStatus.BAD_REQUEST)
            return
        if whatsapp_raw is not None and str(whatsapp_raw).strip():
            if normalize_peru_whatsapp(whatsapp_raw) is None:
                self.send_json(
                    {
                        "error": (
                            "Ingresa un WhatsApp peruano válido: un celular "
                            "de 9 dígitos que empiece con 9."
                        )
                    },
                    HTTPStatus.BAD_REQUEST,
                )
                return
        with connect() as database:
            persist_publisher_profile(
                database,
                int(user["id"]),
                name=name,
                whatsapp=str(whatsapp_raw or ""),
                location=location,
            )
            updated = database.execute(
                f"SELECT {USER_PUBLIC_COLUMNS} FROM users WHERE id = ?",
                (user["id"],),
            ).fetchone()
        self.send_json({"user": user_dict(updated)})

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
        if email == OWNER_EMAIL:
            # La cuenta administradora solo se crea mediante Google, donde el
            # correo llega verificado; así nadie puede reservarla con contraseña.
            self.send_json(
                {"error": "Ese correo se administra con el acceso de Google."},
                HTTPStatus.CONFLICT,
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
                    SELECT id, name, email, avatar_url, auth_provider, role,
                           publisher_name, publisher_whatsapp, publisher_location
                    FROM users WHERE id = ?
                    """,
                    (user_id,),
                ).fetchone()
                record_login(
                    database, user_id, "password",
                    self.client_ip(), self.headers.get("User-Agent", ""),
                )
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
                       auth_provider, role, publisher_name, publisher_whatsapp,
                       publisher_location
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
            record_login(
                database, int(user["id"]), "password",
                self.client_ip(), self.headers.get("User-Agent", ""),
            )
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

        try:
            user, token = self.establish_google_session(claims)
        except GoogleAccountError as account_error:
            self.send_json({"error": str(account_error)}, account_error.status)
            return

        self.send_json({"user": user_dict(user)}, session_token=token)

    def establish_google_session(
        self, claims: dict[str, object]
    ) -> tuple[sqlite3.Row, str]:
        """Crea o vincula la cuenta a partir de las claims verificadas de
        Google y devuelve (usuario, token de sesión). Lo comparten el flujo
        del botón GIS (POST /api/auth/google) y el de redirección OAuth."""
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
            raise GoogleAccountError(
                "La cuenta de Google no contiene un correo válido.",
                HTTPStatus.UNAUTHORIZED,
            )

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
                    raise GoogleAccountError(
                        "Ese correo ya pertenece a otra cuenta.",
                        HTTPStatus.CONFLICT,
                    )
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
                    # Vincular Google NO borra la contraseña previa: la cuenta
                    # conserva sus dos formas de entrar (Google y correo con
                    # contraseña).
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
                    SELECT id, name, email, avatar_url, auth_provider, role,
                           publisher_name, publisher_whatsapp, publisher_location
                    FROM users WHERE id = ?
                    """,
                    (user_id,),
                ).fetchone()
                record_login(
                    database, user_id, "google",
                    self.client_ip(), self.headers.get("User-Agent", ""),
                )
                token = self.create_session(database, user_id)
        except sqlite3.IntegrityError as error:
            raise GoogleAccountError(
                "No pudimos vincular esa cuenta de Google.",
                HTTPStatus.CONFLICT,
            ) from error
        return user, token

    def send_redirect(
        self,
        location: str,
        status: HTTPStatus = HTTPStatus.SEE_OTHER,
        oauth_state_value: str | None = None,
        clear_oauth_state: bool = False,
        session_token: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        if oauth_state_value:
            self.send_header("Set-Cookie", oauth_state_cookie_header(oauth_state_value))
        if clear_oauth_state:
            self.send_header("Set-Cookie", oauth_state_cookie_header())
        if session_token:
            self.send_header("Set-Cookie", session_cookie_header(session_token))
        self.end_headers()

    def send_auth_bridge(
        self,
        location: str,
        *,
        oauth_state_value: str | None = None,
        clear_oauth_state: bool = False,
        session_token: str | None = None,
        session_same_site: str = "Lax",
    ) -> None:
        """Página 200 que fija cookies en contexto de primer partido y sigue
        a Google o a la portada. Un 302/303 de rebote pierde la cookie en
        Safari/Chrome (ITP / bounce tracking) y Luis vuelve a parecer invitado."""
        if location.startswith(f"{GOOGLE_OAUTH_AUTHORIZE}?") or location in AUTH_BRIDGE_HOME:
            safe = location
        else:
            safe = "/"
        escaped = html.escape(safe, quote=True)
        body = (
            "<!doctype html><html lang=\"es\"><head>"
            "<meta charset=\"utf-8\">"
            f"<meta http-equiv=\"refresh\" content=\"0;url={escaped}\">"
            "<title>Llaves365</title>"
            "</head><body>"
            f"<p><a href=\"{escaped}\">Continuar</a></p>"
            "</body></html>"
        ).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Refresh", f"0;url={safe}")
        self.send_header("Content-Length", str(len(body)))
        if oauth_state_value:
            self.send_header("Set-Cookie", oauth_state_cookie_header(oauth_state_value))
        if clear_oauth_state:
            self.send_header("Set-Cookie", oauth_state_cookie_header())
        if session_token:
            self.send_header(
                "Set-Cookie",
                session_cookie_header(session_token, same_site=session_same_site),
            )
        self.end_headers()
        self.wfile.write(body)

    def oauth_redirect_uri(self) -> str:
        host = (self.headers.get("Host") or "").split(":", 1)[0].strip().lower()
        if host not in OAUTH_REDIRECT_HOSTS:
            host = OAUTH_DEFAULT_HOST
        return f"https://{host}{OAUTH_CALLBACK_PATH}"

    def google_oauth_start(self) -> None:
        """Inicia el acceso con Google por redirección completa (OAuth 2.0,
        response_type=id_token). Es el respaldo cuando el iframe de GIS no
        carga; Google devuelve el id_token con un form POST al callback.

        No se envía prompt=select_account/consent/login: eso obliga a
        reelegir cuenta o a reautenticarse y parece que el sitio «saca» a
        Luis de Google. Con la sesión de Google del navegador se reutiliza
        la cuenta ya abierta."""
        if not GOOGLE_CLIENT_ID:
            self.send_redirect("/?auth=google-error", HTTPStatus.FOUND)
            return
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        parameters = urlencode(
            {
                "client_id": GOOGLE_CLIENT_ID,
                "redirect_uri": self.oauth_redirect_uri(),
                "response_type": "id_token",
                "response_mode": "form_post",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
            }
        )
        authorize_url = f"{GOOGLE_OAUTH_AUTHORIZE}?{parameters}"
        accept = (self.headers.get("Accept") or "").lower()
        if "application/json" in accept:
            # Cookie en la respuesta JSON (mismo origen, sin rebote). El
            # navegador ya tiene estadia20_oauth antes de ir a Google.
            self.send_json(
                {"authorizeUrl": authorize_url},
                oauth_state_value=f"{state}.{nonce}",
            )
            return
        self.send_auth_bridge(
            authorize_url,
            oauth_state_value=f"{state}.{nonce}",
        )

    def google_oauth_callback(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 0 or length > 64 * 1024:
                raise ValueError("Cuerpo inválido")
            fields = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            credential = (
                fields.get("id_token", [""])[0] or fields.get("credential", [""])[0]
            ).strip()
            state = fields.get("state", [""])[0].strip()
            if fields.get("error", [""])[0] or not credential or len(credential) > 12_000:
                raise ValueError("Google no entregó una credencial válida")

            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            oauth_cookie = cookies.get(OAUTH_STATE_COOKIE)
            stored = re.fullmatch(
                r"([A-Za-z0-9_-]{16,64})\.([A-Za-z0-9_-]{16,64})",
                oauth_cookie.value if oauth_cookie else "",
            )
            if (
                stored is None
                or not state
                or not hmac.compare_digest(state, stored.group(1))
            ):
                raise ValueError("El estado de la solicitud no coincide")

            claims = verify_google_credential(credential)
            nonce = str(claims.get("nonce", ""))
            if not nonce or not hmac.compare_digest(nonce, stored.group(2)):
                raise ValueError("El nonce de la solicitud no coincide")

            user, token = self.establish_google_session(claims)
        except (ValueError, GoogleAccountError, RuntimeError) as error:
            print(
                json.dumps(
                    {
                        "requestId": self.request_id,
                        "googleCallbackError": repr(error),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            self.send_auth_bridge("/?auth=google-error", clear_oauth_state=True)
            return
        self.send_auth_bridge(
            "/?auth=google-ok",
            clear_oauth_state=True,
            session_token=token,
            session_same_site="None",
        )

    def logout_user(self) -> None:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        cookie = cookies.get(SESSION_COOKIE)
        if cookie and re.fullmatch(r"[A-Za-z0-9_-]{32,100}", cookie.value):
            token_hash = hashlib.sha256(cookie.value.encode()).hexdigest()
            with connect() as database:
                database.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        self.send_json({"loggedOut": True}, clear_session=True)

    def logout_all_sessions(self) -> None:
        """«Cerrar sesión en todos los equipos»: elimina todas las sesiones
        activas del usuario, incluida la actual."""
        user = self.require_user()
        if user is None:
            return
        with connect() as database:
            database.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        self.send_json({"loggedOut": True, "allDevices": True}, clear_session=True)

    def request_password_reset(self) -> None:
        """«Olvidé mi contraseña»: guarda un token con hash y vigencia de 45
        minutos. No hay SMTP todavía, así que el token solo se registra en los
        logs del servidor (el administrador puede reenviarlo manualmente); la
        respuesta nunca revela si el correo existe ni incluye el token."""
        payload = self.read_json()
        email = str(payload.get("email", "")).strip().lower()
        message = "Si el correo existe, te escribimos con los pasos para recuperarla."
        if len(email) > 160 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            self.send_json({"requested": True, "message": message})
            return
        with connect() as database:
            user = database.execute(
                "SELECT id, email FROM users WHERE email = ?", (email,)
            ).fetchone()
            if user is not None:
                token = secrets.token_urlsafe(32)
                now = int(time.time())
                database.execute(
                    "DELETE FROM password_resets WHERE expires_at <= ? OR user_id = ?",
                    (now, user["id"]),
                )
                database.execute(
                    """
                    INSERT INTO password_resets (user_id, token_hash, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        user["id"],
                        hashlib.sha256(token.encode()).hexdigest(),
                        now + PASSWORD_RESET_TTL_SECONDS,
                    ),
                )
                # Visible solo en los logs del servidor (journalctl), nunca en
                # la respuesta HTTP de producción.
                print(
                    json.dumps(
                        {
                            "passwordReset": {
                                "email": user["email"],
                                "url": f"{SITE_BASE_URL}/?reset={token}",
                                "expiresInMinutes": PASSWORD_RESET_TTL_SECONDS // 60,
                            }
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
        self.send_json({"requested": True, "message": message})

    def reset_password(self) -> None:
        payload = self.read_json()
        token = str(payload.get("token", "")).strip()
        password = str(payload.get("password", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,100}", token):
            self.send_json(
                {"error": "El enlace de recuperación no es válido o ya venció."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        if len(password) < 8 or len(password) > 128:
            self.send_json(
                {"error": "La nueva contraseña debe tener al menos 8 caracteres."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = int(time.time())
        with connect() as database:
            row = database.execute(
                """
                SELECT id, user_id FROM password_resets
                WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
            if row is None:
                self.send_json(
                    {"error": "El enlace de recuperación no es válido o ya venció."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            database.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), row["user_id"]),
            )
            database.execute(
                "UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
            # Al cambiar la clave se cierran las sesiones abiertas por seguridad.
            database.execute(
                "DELETE FROM sessions WHERE user_id = ?", (row["user_id"],)
            )
        self.send_json({"reset": True})

    def create_listing(self) -> None:
        user = self.require_user()
        if user is None:
            return
        payload = self.read_json()
        category = canonical_category(payload.get("category", ""))
        title = str(payload.get("title", "")).strip()
        location = str(payload.get("location", "")).strip()
        description = str(payload.get("description", "")).strip()
        owner_name = str(payload.get("ownerName", "")).strip()
        owner_whatsapp = normalize_peru_whatsapp(payload.get("ownerWhatsApp", ""))
        price = parse_price(payload.get("price", 0))
        if owner_whatsapp is None:
            self.send_json(
                {
                    "error": (
                        "Ingresa un WhatsApp peruano válido: un celular de 9 "
                        "dígitos que empiece con 9 (se guarda como 51XXXXXXXXX)."
                    )
                },
                HTTPStatus.BAD_REQUEST,
            )
            return
        if (
            category not in CATEGORIES
            or not all((title, location, description, owner_name))
            or len(title) > 120
            or len(location) > 160
            or len(description) > 2_000
            or len(owner_name) > 80
            or price <= 0
            or price > 10_000_000
        ):
            self.send_json({"error": "Completa todos los campos obligatorios."}, HTTPStatus.BAD_REQUEST)
            return
        # Galería de 1 a 15 fotos; la primera URL es la portada. Se mantiene la
        # compatibilidad con el campo `image` cuando no llega una galería.
        gallery_value = payload.get("gallery")
        if gallery_value is not None and not isinstance(gallery_value, list):
            self.send_json({"error": "Las fotos del anuncio no son válidas."}, HTTPStatus.BAD_REQUEST)
            return
        gallery = [str(item).strip() for item in (gallery_value or []) if str(item).strip()]
        if len(gallery) > MAX_GALLERY_PHOTOS:
            self.send_json(
                {"error": f"Puedes publicar máximo {MAX_GALLERY_PHOTOS} fotos por anuncio."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        if not gallery:
            fallback_image = str(payload.get("image", "")).strip() or (
                "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c"
            )
            gallery = [fallback_image]
        if any(
            len(url) > 500
            or not (
                url.startswith("/api/uploads/")
                or url.startswith("https://images.unsplash.com/")
            )
            for url in gallery
        ):
            self.send_json({"error": "La fotografía no es válida."}, HTTPStatus.BAD_REQUEST)
            return
        image = gallery[0]
        service = None
        if category == "Transporte":
            service = str(payload.get("service", "") or "").strip()
            if service not in {"Mudanza", "Corporativo"}:
                self.send_json(
                    {"error": "Elige el tipo de servicio de transporte."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
        # Cada categoría guarda sus propios datos saneados en details_json y
        # arma el resumen (meta) que se ve en la tarjeta.
        if category == "Depas":
            details = sanitize_depa_details(payload.get("details"), location)
        elif category == "Roomies":
            details = sanitize_roomies_details(payload.get("details"))
        elif category == "Airbnb":
            details = sanitize_stay_details(payload.get("details"))
        else:
            details = sanitize_transport_details(payload.get("details"))
        meta = build_listing_meta(category, details, service)
        is_admin = user["role"] == "admin"
        # Un anuncio de usuario común entra «pending» y no aparece en la lista
        # pública hasta que el administrador lo apruebe; el administrador
        # publica de inmediato.
        status = "published" if is_admin else "pending"
        uploaded_paths = [url for url in gallery if url.startswith("/api/uploads/")]
        with connect() as database:
            if uploaded_paths and not is_admin:
                # Cada foto subida pertenece a quien la subió: nadie puede
                # colgar su anuncio de las fotos de otra cuenta.
                owned = {
                    upload_row["path"]
                    for upload_row in database.execute(
                        f"""
                        SELECT path FROM uploads
                        WHERE user_id = ? AND path IN (
                          {",".join("?" for _ in uploaded_paths)}
                        )
                        """,
                        [user["id"], *uploaded_paths],
                    )
                }
                if any(path not in owned for path in uploaded_paths):
                    self.send_json(
                        {"error": "Una de las fotos no pertenece a tu cuenta."},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
            cursor = database.execute(
                """
                INSERT INTO listings
                  (category, title, location, description, image, gallery, price,
                   price_label, rating, reviews, meta, owner_name, owner_whatsapp,
                   service, details_json, user_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 5, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category,
                    title,
                    location,
                    description,
                    image,
                    json.dumps(gallery, ensure_ascii=False),
                    price,
                    CATEGORY_PRICE_LABELS[category],
                    meta,
                    owner_name,
                    owner_whatsapp,
                    service,
                    json.dumps(details, ensure_ascii=False),
                    user["id"],
                    status,
                ),
            )
            listing_id = int(cursor.lastrowid)
            if uploaded_paths:
                database.execute(
                    f"""
                    UPDATE uploads SET listing_id = ?
                    WHERE user_id = ? AND path IN (
                      {",".join("?" for _ in uploaded_paths)}
                    )
                    """,
                    [listing_id, user["id"], *uploaded_paths],
                )
            persist_publisher_profile(
                database,
                int(user["id"]),
                name=owner_name,
                whatsapp=owner_whatsapp,
                location=location,
            )
            row = database.execute(
                "SELECT * FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
        # Limpieza sencilla y segura: fotos del mismo usuario subidas hace más
        # de un día y nunca adjuntadas a un anuncio.
        try:
            cleanup_orphan_uploads(int(user["id"]))
        except Exception as cleanup_error:  # nunca frena la publicación
            print(
                json.dumps(
                    {"requestId": self.request_id, "cleanupError": repr(cleanup_error)},
                    ensure_ascii=False,
                ),
                flush=True,
            )
        self.send_json(
            {"listing": listing_dict(row, include_contact=True)}, HTTPStatus.CREATED
        )

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
        """Registra la consulta (con mensaje y fechas opcionales) y devuelve
        el WhatsApp completo del anunciante: es el único camino público para
        obtener el número, que en los listados viaja enmascarado."""
        payload = self.read_json()
        listing_id = int(payload.get("listingId", 0))
        if listing_id <= 0:
            self.send_json({"error": "Publicación inválida."}, HTTPStatus.BAD_REQUEST)
            return
        message = str(payload.get("message", "") or "").strip()[:1000]
        check_in = str(payload.get("checkIn", "") or "").strip()
        check_out = str(payload.get("checkOut", "") or "").strip()
        if check_in and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", check_in):
            check_in = ""
        if check_out and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", check_out):
            check_out = ""
        guests_value = payload.get("guests")
        try:
            guests = int(guests_value) if guests_value is not None else None
        except (TypeError, ValueError):
            guests = None
        if guests is not None and not 1 <= guests <= 16:
            guests = None
        visitor_id, is_new = self.visitor()
        channel = "whatsapp" if payload.get("channel") == "whatsapp" else "direct"
        user = self.authenticated_user()
        with connect() as database:
            listing = database.execute(
                """
                SELECT listings.id, listings.user_id, listings.status,
                       listings.owner_whatsapp, listings.owner_name,
                       listings.title, users.publisher_whatsapp
                FROM listings
                LEFT JOIN users ON users.id = listings.user_id
                WHERE listings.id = ?
                """,
                (listing_id,),
            ).fetchone()
            if listing is None:
                self.send_api_error(
                    "La publicación ya no está disponible.",
                    HTTPStatus.NOT_FOUND,
                    "listing_not_found",
                )
                return
            database.execute(
                """
                INSERT INTO inquiries
                  (visitor_id, listing_id, channel, message, check_in, check_out,
                   guests, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    visitor_id,
                    listing_id,
                    channel,
                    message,
                    check_in or None,
                    check_out or None,
                    guests,
                    user["id"] if user is not None else None,
                ),
            )
        # Los anuncios de demostración no tienen contacto real, y un anuncio
        # que salió de circulación no revela el número a visitantes nuevos.
        is_demo = listing["user_id"] is None
        is_privileged = user is not None and (
            user["role"] == "admin" or listing["user_id"] == user["id"]
        )
        can_reveal = not is_demo and (
            listing["status"] == "published" or is_privileged
        )
        publisher_number = reveal_publisher_whatsapp(listing) if can_reveal else None
        self.send_json(
            {
                "recorded": True,
                "whatsapp": publisher_number,
                "whatsappUrl": (
                    f"https://wa.me/{publisher_number}"
                    if publisher_number
                    else None
                ),
            },
            HTTPStatus.CREATED,
            visitor_id=visitor_id if is_new else None,
        )

    def create_report(self) -> None:
        """«Reportar anuncio»: spam, ya alquilado, número falso u otro."""
        payload = self.read_json()
        listing_id = int(payload.get("listingId", 0))
        reason = str(payload.get("reason", "")).strip()
        comment = str(payload.get("comment", "") or "").strip()[:500]
        if listing_id <= 0 or reason not in REPORT_REASONS:
            self.send_json({"error": "Cuéntanos el motivo del reporte."}, HTTPStatus.BAD_REQUEST)
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
                """
                INSERT INTO reports (visitor_id, listing_id, reason, comment)
                VALUES (?, ?, ?, ?)
                """,
                (visitor_id, listing_id, reason, comment),
            )
        self.send_json(
            {"reported": True},
            HTTPStatus.CREATED,
            visitor_id=visitor_id if is_new else None,
        )

    def create_upload(self) -> None:
        """Recibe de 1 a 15 fotos en una sola petición multipart (campo `files`
        repetido o el campo `file` de una sola foto) y las redimensiona a un
        tamaño profesional antes de guardarlas."""
        user = self.require_user()
        if user is None:
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_REQUEST_BYTES:
            self.send_json(
                {"error": "Las fotos superan el tamaño permitido (máximo 12 MB por foto)."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            self.send_json({"error": "Selecciona al menos una fotografía."}, HTTPStatus.BAD_REQUEST)
            return
        body = self.rfile.read(length)
        uploads = extract_multipart_files(content_type, body)
        if not uploads:
            self.send_json({"error": "Selecciona al menos una fotografía."}, HTTPStatus.BAD_REQUEST)
            return
        if len(uploads) > MAX_UPLOAD_FILES:
            self.send_json(
                {"error": f"Puedes subir máximo {MAX_UPLOAD_FILES} fotos por anuncio."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        # Se validan y procesan todas las fotos antes de escribir nada en
        # disco, para no dejar archivos huérfanos si una foto es inválida.
        processed_files: list[tuple[bytes, str]] = []
        for content, mime_type in uploads:
            claimed_extension = IMAGE_TYPES.get(mime_type)
            if not claimed_extension:
                self.send_json({"error": "Cada archivo debe ser una imagen."}, HTTPStatus.BAD_REQUEST)
                return
            if len(content) > MAX_UPLOAD_BYTES:
                self.send_json(
                    {"error": "Cada foto debe pesar menos de 12 MB."}, HTTPStatus.BAD_REQUEST
                )
                return
            extension = image_extension_from_content(content)
            if extension is None or extension != claimed_extension:
                self.send_api_error(
                    "El contenido del archivo no coincide con una imagen válida.",
                    HTTPStatus.BAD_REQUEST,
                    "invalid_image",
                )
                return
            try:
                processed_files.append(process_upload_image(content, extension))
            except ValueError as error:
                # El mensaje ya viene en español (p. ej. el aviso de HEIC).
                self.send_api_error(
                    str(error) or "Una de las fotos está dañada o no se pudo procesar.",
                    HTTPStatus.BAD_REQUEST,
                    "invalid_image",
                )
                return
        folder = date.today().isoformat()
        destination = UPLOADS_DIR / folder
        destination.mkdir(parents=True, exist_ok=True)
        urls: list[str] = []
        for content, extension in processed_files:
            filename = f"{uuid.uuid4()}.{extension}"
            (destination / filename).write_bytes(content)
            urls.append(f"/api/uploads/{folder}/{filename}")
        # Cada foto queda ligada a la cuenta que la subió: al publicar se
        # verifica esa propiedad y al borrar el anuncio se limpia el disco.
        with connect() as database:
            database.executemany(
                "INSERT OR IGNORE INTO uploads (user_id, path) VALUES (?, ?)",
                [(user["id"], url) for url in urls],
            )
        self.send_json({"url": urls[0], "urls": urls}, HTTPStatus.CREATED)

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
