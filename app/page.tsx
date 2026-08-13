/* eslint-disable @next/next/no-img-element */
"use client";

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";

import {
  demoListings,
  depaFeatureOptions,
  stayAmenityOptions,
  type Category,
  type DepaDetails,
  type DepaFeature,
  type Listing,
  type StayAmenity,
} from "./data";

// Marca pública: el sitio vive en llaves365.com. Los nombres internos
// (repo, systemd, rutas del VPS, cookies) siguen siendo "estadia20".
const BRAND = "Llaves365";
const BRAND_MARK = "llaves365";
const SUPPORT_EMAIL = "hola@estadia20.com";

const categories: Array<{ id: Category; label: string; short: string }> = [
  { id: "Roomies", label: "Roomies", short: "Habitaciones" },
  { id: "Depas", label: "Depas", short: "Alquiler mensual" },
  { id: "Airbnb", label: "Estadías", short: "Por noche" },
  { id: "Transporte", label: "Transporte", short: "Mudanzas y premium" },
];

const categoryDetails: Record<Category, { noun: string; date: string; guests: string; priceLabel: string }> = {
  Roomies: { noun: "habitaciones", date: "Desde un mes", guests: "1 roomie", priceLabel: "por mes" },
  Depas: { noun: "departamentos", date: "6–12 meses", guests: "2 personas", priceLabel: "por mes" },
  Airbnb: { noun: "alojamientos", date: "9–14 de ago", guests: "2 huéspedes", priceLabel: "por noche" },
  Transporte: { noun: "servicios", date: "Cuando quieras", guests: "Carga o pasajeros", priceLabel: "por servicio" },
};

// Cada categoría tiene su propio formulario de publicación, con una guía de
// descripción distinta para que el anuncio cuente lo que importa.
const publishCopy: Record<Category, { kicker: string; helper: string; placeholder: string; titlePlaceholder: string }> = {
  Roomies: {
    kicker: "Publicar habitación",
    helper: "Cuéntales a tu futuro roomie cómo es la habitación, la casa y con quién van a vivir.",
    placeholder: "Ej. Habitación amoblada con escritorio, casa tranquila con dos roomies que trabajan…",
    titlePlaceholder: "Ej. Habitación con luz y calma",
  },
  Depas: {
    kicker: "Publicar depa",
    helper: "Describe el departamento: ambientes, piso, zona y condiciones del contrato.",
    placeholder: "Ej. Depa de 2 dormitorios en piso 5 con balcón, cerca al parque, contrato de 12 meses…",
    titlePlaceholder: "Ej. Depa luminoso en Barranco",
  },
  Airbnb: {
    kicker: "Publicar estadía",
    helper: "Describe la estadía: el espacio, qué incluye y cómo es la zona para una noche o unos días.",
    placeholder: "Ej. Depa completo con wifi rápido y cocina equipada, a dos cuadras del malecón…",
    titlePlaceholder: "Ej. Suite luminosa cerca al malecón",
  },
  Transporte: {
    kicker: "Publicar transporte",
    helper: "Describe el servicio: vehículo, equipo, zona y cómo coordinan la mudanza o el traslado.",
    placeholder: "Ej. Camión cerrado de 3 t con dos ayudantes, cubrimos Lima y Callao, coordinamos por WhatsApp…",
    titlePlaceholder: "Ej. Mudanza segura para tu depa",
  },
};

// Avisos amables de Google para visitantes sin sesión: máximo dos por visita
// (banner de bienvenida + un recordatorio corto). El cierre queda guardado en
// localStorage para no insistir en cada recarga.
const GOOGLE_NUDGE_STORAGE_KEY = "llaves365-google-nudge";
const GOOGLE_NUDGE_COOLDOWN_MS = 12 * 60 * 60 * 1000;
const MAX_AUTO_GOOGLE_NUDGES = 2;

type GoogleNudgeMemory = { welcomeDismissedAt?: number; reminderShownAt?: number };

function readGoogleNudgeMemory(): GoogleNudgeMemory {
  try {
    if (typeof window === "undefined") return {};
    const raw = window.localStorage.getItem(GOOGLE_NUDGE_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as GoogleNudgeMemory) : null;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function welcomeNudgeRecentlyDismissed() {
  const memory = readGoogleNudgeMemory();
  return typeof memory.welcomeDismissedAt === "number"
    && Date.now() - memory.welcomeDismissedAt < GOOGLE_NUDGE_COOLDOWN_MS;
}

function saveGoogleNudgeMemory(patch: GoogleNudgeMemory) {
  try {
    window.localStorage.setItem(GOOGLE_NUDGE_STORAGE_KEY, JSON.stringify({ ...readGoogleNudgeMemory(), ...patch }));
  } catch {
    // Sin localStorage (modo privado estricto) el aviso simplemente no persiste.
  }
}

const MAX_PUBLISH_PHOTOS = 15;
const MAX_PHOTO_BYTES = 12 * 1024 * 1024;
const PHOTO_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];

// Las fotos se previsualizan en local (object URL) apenas se eligen y solo se
// suben al servidor cuando el anuncio se guarda. Una foto inválida conserva su
// casilla con el motivo en español en vez de desaparecer en silencio.
type PublishPhoto = { id: number; file: File; preview: string; error?: string };

const plans = [
  { name: "Roomie", price: "S/ 25", detail: "por habitación al año", icon: "⌂" },
  { name: "Depa", price: "S/ 50", detail: "por departamento al año", icon: "▦" },
  { name: "Estadía", price: "S/ 100", detail: "por alojamiento al año", icon: "◇" },
  { name: "Transporte", price: "S/ 50", detail: "por servicio al año", icon: "▰" },
];

const searchAliasFamilies = [
  ["habitacion", "cuarto", "dormitorio", "roomie", "roommate"],
  ["amoblado", "amueblado", "equipado", "muebles"],
  ["bano", "servicio", "bathroom"],
  ["escritorio", "oficina", "trabajo", "estudio"],
  ["cerca", "cercano", "proximo"],
  ["departamento", "depa", "apartamento"],
  ["transporte", "movilidad", "traslado"],
  ["mudanza", "carga", "camion", "camioneta"],
];

const searchAliases = new Map<string, string[]>();
for (const family of searchAliasFamilies) {
  for (const term of family) searchAliases.set(term, family);
}

const searchStopWords = new Set([
  "busca", "buscar", "busco", "quiero", "necesito", "para", "por", "una", "uno", "un", "de", "del", "en", "con", "que", "sea", "soles", "s",
]);

const bedroomOptions = ["Todos", "1", "2", "3", "4+"] as const;
type BedroomFilter = typeof bedroomOptions[number];
type ListingSort = "recommended" | "newest" | "price_asc" | "price_desc" | "rating";
type ListingsStatus = "loading" | "ready" | "error";

type ListingsMeta = {
  total: number;
  categoryTotal: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasMore: boolean;
  sort: ListingSort;
};

type ListingsPayload = {
  listings?: Listing[];
  meta?: ListingsMeta;
  error?: string;
  requestId?: string;
};

const sortOptions: Array<{ value: ListingSort; label: string }> = [
  { value: "recommended", label: "Recomendados" },
  { value: "newest", label: "Más recientes" },
  { value: "price_asc", label: "Menor precio" },
  { value: "price_desc", label: "Mayor precio" },
  { value: "rating", label: "Mejor valorados" },
];

type AuthUser = {
  id: number;
  name: string;
  email: string;
  avatarUrl: string;
  authProvider: "google" | "password";
  role: "admin" | "user";
};

type OwnedListing = Listing & {
  createdAt?: string;
  inquiries?: number;
  favorites?: number;
  ownerEmail?: string | null;
};

type AdminOverviewData = {
  stats: {
    listings: number;
    byCategory: Record<string, number>;
    users: number;
    favorites: number;
    inquiries: number;
    inquiriesLast7Days: number;
  };
  topListings: Array<{ id: number; title: string; category: string; total: number }>;
  recentListings: Array<{ id: number; title: string; category: string; price: number; createdAt: string }>;
};

type AdminUserRow = {
  id: number;
  name: string;
  email: string;
  authProvider: string;
  role: string;
  createdAt: string;
  lastLoginAt?: string | null;
  lastLoginProvider?: string | null;
  listings: number;
  listingsByCategory?: Record<string, number>;
};

type AdminActivityEvent = {
  type: "login" | "listing";
  id: string;
  name?: string | null;
  email?: string | null;
  provider?: string;
  listingId?: number;
  title?: string;
  category?: string;
  createdAt: string;
};

type AdminInquiriesData = {
  recent: Array<{ id: number; listingId: number; channel: string; createdAt: string; title: string; category: string }>;
  byListing: Array<{ id: number; title: string; category: string; total: number }>;
};

type PanelStatus = "loading" | "ready" | "error";

type GoogleCredentialResponse = {
  credential: string;
  select_by?: string;
};

type GoogleIdentityClient = {
  initialize: (options: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
    itp_support?: boolean;
    use_fedcm_for_prompt?: boolean;
  }) => void;
  renderButton: (
    parent: HTMLElement,
    options: {
      type: "standard";
      theme: "outline";
      size: "large";
      shape: "rectangular";
      text: "continue_with";
      logo_alignment: "left";
      width: number;
      locale?: string;
    },
  ) => void;
  disableAutoSelect: () => void;
};

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentityClient } };
  }
}

let googleIdentityScript: Promise<void> | null = null;

function loadGoogleIdentityScript() {
  if (window.google?.accounts.id) return Promise.resolve();
  if (googleIdentityScript) return googleIdentityScript;
  googleIdentityScript = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById("google-identity-services") as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");
    const loaded = () => window.google?.accounts.id
      ? resolve()
      : reject(new Error("Google no terminó de cargar"));
    script.addEventListener("load", loaded, { once: true });
    script.addEventListener("error", () => reject(new Error("No se pudo cargar Google")), { once: true });
    if (!existing) {
      script.id = "google-identity-services";
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  }).catch((error) => {
    googleIdentityScript = null;
    document.getElementById("google-identity-services")?.remove();
    throw error;
  });
  return googleIdentityScript;
}

const money = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
  maximumFractionDigits: 0,
});

function whatsappLink(listing: Listing, stay?: { checkIn: string; checkOut: string; guests: number }) {
  const stayDetails = listing.category === "Airbnb" && stay
    ? ` para llegar el ${formatShortDate(stay.checkIn)}, salir el ${formatShortDate(stay.checkOut)} y ${stay.guests} ${stay.guests === 1 ? "huésped" : "huéspedes"}`
    : "";
  const message = encodeURIComponent(
    `Hola ${listing.ownerName}, vi “${listing.title}” en ${BRAND} y me gustaría consultar disponibilidad${stayDetails}.`,
  );
  return `https://wa.me/${listing.ownerWhatsApp}?text=${message}`;
}

function listingImages(listing: Listing) {
  return Array.from(new Set([listing.image, ...(listing.gallery ?? [])].filter(Boolean)));
}

function imageUrl(source: string, width: number) {
  return `${source}${source.includes("?") ? "&" : "?"}auto=format&fit=crop&w=${width}&q=90`;
}

// Galería deslizable estilo iOS Photos: usa scroll horizontal nativo con
// scroll-snap, así la foto sigue al dedo y encaja en la más cercana al soltar
// sin secuestrar el scroll vertical de la página. En escritorio también se
// puede arrastrar con el mouse; un arrastre no dispara el clic de la tarjeta.
function SwipeGallery({ index, count, onIndexChange, className = "", label, children }: {
  index: number;
  count: number;
  onIndexChange: (index: number) => void;
  className?: string;
  label?: string;
  children: React.ReactNode;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const reportedIndex = useRef(index);
  const dragRef = useRef<{ pointerId: number; startX: number; startScroll: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const didMount = useRef(false);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    reportedIndex.current = index;
    const width = Math.max(1, track.clientWidth);
    if (Math.round(track.scrollLeft / width) !== index) {
      track.scrollTo({ left: index * width, behavior: didMount.current ? "smooth" : "auto" });
    }
    didMount.current = true;
  }, [index]);

  function nearestIndex(track: HTMLDivElement) {
    const width = Math.max(1, track.clientWidth);
    return Math.max(0, Math.min(count - 1, Math.round(track.scrollLeft / width)));
  }

  function reportIndex(next: number) {
    if (next === reportedIndex.current) return;
    reportedIndex.current = next;
    onIndexChange(next);
  }

  function handleScroll() {
    const track = trackRef.current;
    if (!track || dragRef.current) return;
    reportIndex(nearestIndex(track));
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "mouse" || event.button !== 0 || count < 2) return;
    const track = trackRef.current;
    if (!track) return;
    dragRef.current = { pointerId: event.pointerId, startX: event.clientX, startScroll: track.scrollLeft, moved: false };
    track.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    const track = trackRef.current;
    if (!drag || !track || event.pointerId !== drag.pointerId) return;
    const delta = event.clientX - drag.startX;
    if (!drag.moved && Math.abs(delta) > 6) {
      drag.moved = true;
      setIsDragging(true);
    }
    if (drag.moved) track.scrollLeft = drag.startScroll - delta;
  }

  function handlePointerEnd(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    const track = trackRef.current;
    if (!drag || !track || event.pointerId !== drag.pointerId) return;
    dragRef.current = null;
    if (track.hasPointerCapture(event.pointerId)) track.releasePointerCapture(event.pointerId);
    if (!drag.moved) return;
    suppressClick.current = true;
    setIsDragging(false);
    const next = nearestIndex(track);
    track.scrollTo({ left: next * Math.max(1, track.clientWidth), behavior: "smooth" });
    reportIndex(next);
  }

  function handleClickCapture(event: React.MouseEvent<HTMLDivElement>) {
    if (!suppressClick.current) return;
    suppressClick.current = false;
    event.preventDefault();
    event.stopPropagation();
  }

  return (
    <div
      ref={trackRef}
      className={`swipe-gallery ${className}${isDragging ? " is-dragging" : ""}`.trim()}
      role="group"
      aria-roledescription="carrusel"
      aria-label={label}
      onScroll={handleScroll}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerEnd}
      onPointerCancel={handlePointerEnd}
      onClickCapture={handleClickCapture}
    >
      {children}
    </div>
  );
}

function Icon({ children }: { children: string }) {
  return <span aria-hidden="true">{children}</span>;
}

function BrandKeysIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 64">
      <g transform="rotate(-38 32 32)">
        <circle cx="14" cy="32" r="12" fill="currentColor" />
        <circle cx="14" cy="32" r="4.5" fill="#ffbd00" />
        <path d="M24 28h34v8H24zM41 35h7v10h-7zM51 35h7v7h-7z" fill="currentColor" />
      </g>
    </svg>
  );
}

function ServiceIcon({ category }: { category: Category }) {
  if (category === "Roomies") {
    return <svg aria-hidden="true" viewBox="0 0 64 64"><rect width="64" height="64" rx="4" fill="#f4e4d2" /><rect x="5" y="7" width="19" height="23" fill="#cfe5ea" /><path d="M6 18h17M15.5 8v21" stroke="#fff" strokeWidth="2" /><rect x="12" y="38" width="43" height="13" rx="3" fill="#be7956" /><path d="M15 37c0-5 4-8 10-8h20c5 0 8 3 8 8" fill="#fff" /><path d="M10 52h47M15 52v6M53 52v6" stroke="#5b4033" strokeWidth="3" strokeLinecap="round" /><rect x="29" y="11" width="23" height="15" rx="2" fill="#f8f5ef" /><rect x="33" y="15" width="15" height="7" fill="#8ca287" /></svg>;
  }
  if (category === "Depas") {
    return <svg aria-hidden="true" viewBox="0 0 64 64"><path d="M13 8h38v49H13zM8 57h48v4H8z" fill="currentColor" /><g fill="#ffbd00"><rect x="20" y="15" width="8" height="8" rx="1" /><rect x="36" y="15" width="8" height="8" rx="1" /><rect x="20" y="29" width="8" height="8" rx="1" /><rect x="36" y="29" width="8" height="8" rx="1" /><rect x="20" y="43" width="8" height="8" rx="1" /><rect x="36" y="43" width="8" height="14" rx="1" /></g></svg>;
  }
  if (category === "Airbnb") {
    return <svg aria-hidden="true" viewBox="0 0 64 64"><defs><linearGradient id="stay-gradient" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#ff2d78" /><stop offset="1" stopColor="#f04b54" /></linearGradient></defs><rect width="64" height="64" rx="15" fill="url(#stay-gradient)" /><path d="m12 31 20-18 20 18M17 28v23h30V28M27 51V38h10v13M24 29a8 8 0 0 1 16 0" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  }
  return <svg aria-hidden="true" viewBox="0 0 76 64"><path d="M4 16h43v32H4zM47 27h14l11 12v9H47z" fill="#2116c6" /><path d="M8 10H2M8 22H0M8 34H3" stroke="#2116c6" strokeWidth="5" strokeLinecap="round" /><path d="m8 18 37 28M8 46l36-28M14 16l33 28M14 48l32-27" stroke="#483be8" strokeWidth="1" /><circle cx="18" cy="50" r="8" fill="#ffbd00" stroke="#2116c6" strokeWidth="4" /><circle cx="59" cy="50" r="8" fill="#ffbd00" stroke="#2116c6" strokeWidth="4" /></svg>;
}

function SearchIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" strokeWidth="2.8" /><path d="m15.5 15.5 5 5" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" /></svg>;
}

function FilterIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M7 14v6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><circle cx="14" cy="7" r="2" fill="#fff" stroke="currentColor" strokeWidth="2" /><circle cx="7" cy="17" r="2" fill="#fff" stroke="currentColor" strokeWidth="2" /></svg>;
}

function GoogleGIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <path d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z" fill="#4285F4" />
      <path d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z" fill="#34A853" />
      <path d="M3.97 10.72a5.41 5.41 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z" fill="#FBBC05" />
      <path d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59A8.98 8.98 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z" fill="#EA4335" />
    </svg>
  );
}

function GlobeIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.7" /><path d="M3.5 12h17M12 3c3.5 3.6 3.5 14.4 0 18M12 3c-3.5 3.6-3.5 14.4 0 18" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>;
}

function LocationIcon() {
  return <svg aria-hidden="true" viewBox="0 0 48 48"><path d="M8 17 24 6l16 11v25H8z" fill="#eeeeea" stroke="#7c7c75" strokeWidth="1.5" /><path d="M6 18 24 5l18 13" fill="none" stroke="#373737" strokeWidth="2.3" strokeLinecap="round" /><rect x="19" y="22" width="12" height="20" rx="1" fill="#ec315d" /><circle cx="28" cy="32" r="1.2" fill="#fff" /><path d="M7 42h34" stroke="#373737" strokeWidth="2" /></svg>;
}

function WhatsappIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path fill="currentColor" d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.17.2-.35.22-.64.07-.3-.15-1.26-.46-2.39-1.47-.88-.79-1.48-1.76-1.65-2.06-.18-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.91-2.21-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.02-1.04 2.48s1.06 2.88 1.21 3.08c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.23 1.36.19 1.87.12.57-.09 1.76-.72 2.01-1.41.25-.7.25-1.29.17-1.41-.07-.13-.27-.2-.57-.35M12.05 21.77h-.01a9.86 9.86 0 0 1-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.85 9.85 0 0 1-1.51-5.26A9.89 9.89 0 0 1 12.05 2c2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 0 1 2.89 6.99c0 5.45-4.43 9.88-9.88 9.88M20.46 3.49A11.82 11.82 0 0 0 12.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 0 0 5.69 1.45c6.55 0 11.89-5.34 11.89-11.9 0-3.18-1.23-6.16-3.48-8.41" /></svg>;
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short" })
    .format(parseDateValue(value))
    .replace(".", "")
    .toLowerCase();
}

function parseDateValue(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 12);
}

function dateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(date: Date, amount: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function addMonths(date: Date, amount: number) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1, 12);
}

function monthStart(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1, 12);
}

function stayNights(from: string, to: string) {
  const first = parseDateValue(from);
  const last = parseDateValue(to);
  return Math.max(1, Math.round((Date.UTC(last.getFullYear(), last.getMonth(), last.getDate()) - Date.UTC(first.getFullYear(), first.getMonth(), first.getDate())) / 86_400_000));
}

function formatCalendarTitle(date: Date) {
  const label = new Intl.DateTimeFormat("es-PE", { month: "long", year: "numeric" }).format(date);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatDetailDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { weekday: "short", day: "numeric", month: "short" })
    .format(parseDateValue(value))
    .replaceAll(".", "");
}

type AirbnbDateStage = "arrival" | "departure";

function ChevronIcon({ direction }: { direction: "left" | "right" }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d={direction === "left" ? "m15 18-6-6 6-6" : "m9 6 6 6-6 6"} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function CalendarMonth({
  month,
  checkIn,
  checkOut,
  stage,
  minimumDate,
  onSelect,
}: {
  month: Date;
  checkIn: string;
  checkOut: string;
  stage: AirbnbDateStage;
  minimumDate: string;
  onSelect: (value: string) => void;
}) {
  const firstWeekday = (month.getDay() + 6) % 7;
  const dayCount = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells: Array<Date | null> = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: dayCount }, (_, index) => new Date(month.getFullYear(), month.getMonth(), index + 1, 12)),
  ];

  return (
    <section className="calendar-month" aria-label={formatCalendarTitle(month)}>
      <h3>{formatCalendarTitle(month)}</h3>
      <div className="calendar-weekdays" aria-hidden="true">{["L", "M", "M", "J", "V", "S", "D"].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}</div>
      <div className="calendar-days">
        {cells.map((date, index) => {
          if (!date) return <span className="calendar-empty" key={`empty-${index}`} />;
          const value = dateValue(date);
          const disabled = value < minimumDate || (stage === "departure" && value < checkIn);
          const isStart = value === checkIn;
          const isEnd = value === checkOut;
          const isBetween = value > checkIn && value < checkOut;
          const className = ["calendar-day", isStart ? "range-start" : "", isEnd ? "range-end" : "", isBetween ? "in-range" : ""].filter(Boolean).join(" ");
          return <button key={value} className={className} disabled={disabled} onClick={() => onSelect(value)} aria-label={`${date.getDate()} de ${formatCalendarTitle(month)}${isStart ? ", llegada" : isEnd ? ", salida" : ""}`} aria-pressed={isStart || isEnd}><span>{date.getDate()}</span></button>;
        })}
      </div>
    </section>
  );
}

function AirbnbDatePicker({
  checkIn,
  checkOut,
  stage,
  visibleMonth,
  onStageChange,
  onMonthChange,
  onSelect,
  onClose,
}: {
  checkIn: string;
  checkOut: string;
  stage: AirbnbDateStage;
  visibleMonth: Date;
  onStageChange: (stage: AirbnbDateStage) => void;
  onMonthChange: (month: Date) => void;
  onSelect: (value: string) => void;
  onClose: () => void;
}) {
  const today = dateValue(new Date());
  const firstAllowedMonth = monthStart(parseDateValue(today));
  const nights = stayNights(checkIn, checkOut);
  const previousDisabled = dateValue(monthStart(visibleMonth)) <= dateValue(firstAllowedMonth);

  return (
    <div className="airbnb-date-popover" role="dialog" aria-modal="false" aria-label="Seleccionar fecha de llegada y fecha de salida">
      <div className="calendar-heading">
        <div><span className="modal-kicker">Reserva por noches</span><strong>Elige tu llegada y salida</strong><small>{stage === "arrival" ? "Selecciona la fecha de llegada." : `Selecciona la salida · ${nights} ${nights === 1 ? "noche" : "noches"}.`}</small></div>
        <button className="calendar-close" onClick={onClose} aria-label="Cerrar calendario">×</button>
      </div>
      <div className="calendar-date-summary" role="group" aria-label="Fechas seleccionadas">
        <button className={stage === "arrival" ? "active" : ""} onClick={() => onStageChange("arrival")}><span>Llegada</span><strong>{formatDetailDate(checkIn)}</strong></button>
        <span aria-hidden="true">→</span>
        <button className={stage === "departure" ? "active" : ""} onClick={() => onStageChange("departure")}><span>Salida</span><strong>{formatDetailDate(checkOut)}</strong></button>
      </div>
      <div className="calendar-navigation">
        <button disabled={previousDisabled} onClick={() => onMonthChange(addMonths(visibleMonth, -1))} aria-label="Mes anterior"><ChevronIcon direction="left" /></button>
        <span>{nights} {nights === 1 ? "noche seleccionada" : "noches seleccionadas"}</span>
        <button onClick={() => onMonthChange(addMonths(visibleMonth, 1))} aria-label="Mes siguiente"><ChevronIcon direction="right" /></button>
      </div>
      <div className="calendar-months">
        <CalendarMonth month={visibleMonth} checkIn={checkIn} checkOut={checkOut} stage={stage} minimumDate={today} onSelect={onSelect} />
        <CalendarMonth month={addMonths(visibleMonth, 1)} checkIn={checkIn} checkOut={checkOut} stage={stage} minimumDate={today} onSelect={onSelect} />
      </div>
      <div className="calendar-footer"><span>El precio final se calcula por la cantidad de noches.</span><button onClick={onClose}>Listo</button></div>
    </div>
  );
}

function normalizeSearchText(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function editDistance(left: string, right: string) {
  if (left === right) return 0;
  if (Math.abs(left.length - right.length) > 2) return 3;

  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    const current = [leftIndex];
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      current[rightIndex] = Math.min(
        current[rightIndex - 1] + 1,
        previous[rightIndex] + 1,
        previous[rightIndex - 1] + (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1),
      );
    }
    previous = current;
  }
  return previous[right.length];
}

function tokenMatchScore(queryToken: string, candidateToken: string) {
  if (queryToken === candidateToken) return 7;
  if (candidateToken.startsWith(queryToken) || queryToken.startsWith(candidateToken)) return 5;
  if (queryToken.length >= 4 && candidateToken.includes(queryToken)) return 4;
  if (queryToken.length >= 4 && editDistance(queryToken, candidateToken) <= (queryToken.length >= 7 ? 2 : 1)) return 2;
  return 0;
}

function listingSearchScore(listing: Listing, query: string) {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return 0;

  const priceCeilingMatch = normalizedQuery.match(/\b(?:hasta|maximo|max|menos\s+de)\s+(?:s\s*)?(\d{2,5})\b/);
  if (priceCeilingMatch && listing.price > Number(priceCeilingMatch[1])) return -1;

  const termSource = priceCeilingMatch
    ? normalizedQuery.replace(priceCeilingMatch[0], " ")
    : normalizedQuery;
  const queryTokens = termSource
    .split(/\s+/)
    .filter((token) => token && !searchStopWords.has(token));

  if (!queryTokens.length) return 1;

  const normalizedListingText = normalizeSearchText([
    listing.title,
    listing.location,
    listing.meta,
    listing.description,
  ].join(" "));
  const furnishingIntent = queryTokens.some((token) => (searchAliases.get(token) ?? []).includes("amoblado"));
  const wantsUnfurnished = /\bsin\s+(?:amoblar|amueblar|muebles|equipar)\b/.test(normalizedQuery);
  const listingIsUnfurnished = /\bsin\s+(?:amoblar|amueblar|muebles|equipar)\b/.test(normalizedListingText);
  if (furnishingIntent && !wantsUnfurnished && listingIsUnfurnished) return -1;

  const fields = [
    { value: listing.title, weight: 10 },
    { value: listing.location, weight: 9 },
    { value: listing.details?.address ?? "", weight: 9 },
    { value: listing.meta, weight: 7 },
    { value: listing.description, weight: 5 },
    { value: listing.details?.features?.join(" ") ?? "", weight: 6 },
    { value: listing.badge ?? "", weight: 3 },
    { value: listing.ownerName, weight: 2 },
    { value: `${listing.price} soles`, weight: 5 },
  ].map((field) => ({ ...field, normalized: normalizeSearchText(field.value) }));

  let score = 0;
  for (const queryToken of queryTokens) {
    const alternatives = searchAliases.get(queryToken) ?? [queryToken];
    let bestTokenScore = 0;

    for (const field of fields) {
      const candidateTokens = field.normalized.split(/\s+/).filter(Boolean);
      for (const alternative of alternatives) {
        if (field.normalized.includes(alternative)) {
          bestTokenScore = Math.max(bestTokenScore, field.weight * 5);
        }
        for (const candidateToken of candidateTokens) {
          bestTokenScore = Math.max(bestTokenScore, tokenMatchScore(alternative, candidateToken) * field.weight);
        }
      }
    }

    if (!bestTokenScore) return -1;
    score += bestTokenScore;
  }

  const combinedText = fields.map((field) => field.normalized).join(" ");
  const meaningfulPhrase = queryTokens.join(" ");
  if (meaningfulPhrase.length >= 4 && combinedText.includes(meaningfulPhrase)) score += 80;
  return score;
}

function rangeLabel(minimum: number, maximum: number, singular: string, plural: string) {
  if (minimum === maximum) return `${minimum} ${minimum === 1 ? singular : plural}`;
  return `${minimum} a ${maximum} ${plural}`;
}

function inferredRange(meta: string, noun: "dormitorios" | "baños") {
  const normalized = normalizeSearchText(meta);
  const pattern = noun === "dormitorios"
    ? /(\d+)\s*(?:a\s*(\d+))?\s*(?:dormitorios?|habitaciones?)/
    : /(\d+)\s*(?:a\s*(\d+))?\s*banos?/;
  const match = normalized.match(pattern);
  const minimum = match ? Number(match[1]) : 1;
  return { minimum, maximum: match?.[2] ? Number(match[2]) : minimum };
}

function depaDetails(listing: Listing): DepaDetails {
  const details = listing.details;
  if (details && typeof details.units === "number" && typeof details.bedroomsMin === "number" && typeof details.bedroomsMax === "number" && typeof details.bathroomsMin === "number" && typeof details.bathroomsMax === "number") {
    return {
      delivery: details.delivery ?? "Disponible ahora",
      availability: details.availability ?? "Alquiler mensual",
      address: details.address ?? listing.location,
      units: details.units,
      areaTotal: details.areaTotal ?? "Área por consultar",
      areaCovered: details.areaCovered ?? "Área techada por consultar",
      bedroomsMin: details.bedroomsMin,
      bedroomsMax: details.bedroomsMax,
      bathroomsMin: details.bathroomsMin,
      bathroomsMax: details.bathroomsMax,
      features: details.features ?? [],
    };
  }
  const bedrooms = inferredRange(listing.meta, "dormitorios");
  const bathrooms = inferredRange(listing.meta, "baños");
  const searchable = normalizeSearchText(`${listing.meta} ${listing.description}`);
  const features = depaFeatureOptions.filter((feature) => {
    const normalizedFeature = normalizeSearchText(feature);
    if (normalizedFeature === "area de lavanderia") return searchable.includes("lavanderia");
    if (normalizedFeature === "permite mascotas") return searchable.includes("mascota");
    return searchable.includes(normalizedFeature);
  });
  return {
    delivery: listing.badge ?? "Disponible ahora",
    availability: "Alquiler mensual",
    address: listing.location,
    units: 1,
    areaTotal: "Área por consultar",
    areaCovered: "Área techada por consultar",
    bedroomsMin: bedrooms.minimum,
    bedroomsMax: bedrooms.maximum,
    bathroomsMin: bathrooms.minimum,
    bathroomsMax: bathrooms.maximum,
    features,
  };
}

function DepaFilterControls({
  bedrooms,
  minimumPrice,
  maximumPrice,
  features,
  onBedroomsChange,
  onMinimumPriceChange,
  onMaximumPriceChange,
  onToggleFeature,
}: {
  bedrooms: BedroomFilter;
  minimumPrice: string;
  maximumPrice: string;
  features: DepaFeature[];
  onBedroomsChange: (value: BedroomFilter) => void;
  onMinimumPriceChange: (value: string) => void;
  onMaximumPriceChange: (value: string) => void;
  onToggleFeature: (feature: DepaFeature) => void;
}) {
  return (
    <div className="depa-filter-content">
      <section className="depa-filter-section">
        <h3>¿Cuántos dormitorios buscas?</h3>
        <div className="bedroom-options" role="group" aria-label="Cantidad de dormitorios">
          {bedroomOptions.map((option) => (
            <button key={option} className={bedrooms === option ? "selected" : ""} aria-pressed={bedrooms === option} onClick={() => onBedroomsChange(option)}>
              {option === "Todos" ? "Cualquiera" : option === "4+" ? "4 o más" : `${option} dorm.`}
            </button>
          ))}
        </div>
      </section>
      <section className="depa-filter-section">
        <h3>¿Cuánto quieres pagar?</h3>
        <div className="depa-price-range">
          <label><span>Precio mínimo</span><div><b>S/</b><input type="number" min="0" inputMode="numeric" value={minimumPrice} onChange={(event) => onMinimumPriceChange(event.target.value)} placeholder="Sin mínimo" /></div></label>
          <span className="price-separator" aria-hidden="true">—</span>
          <label><span>Precio máximo</span><div><b>S/</b><input type="number" min="0" inputMode="numeric" value={maximumPrice} onChange={(event) => onMaximumPriceChange(event.target.value)} placeholder="Sin máximo" /></div></label>
        </div>
      </section>
      <section className="depa-filter-section depa-features-section">
        <h3>¿Quieres agregar características a tu búsqueda?</h3>
        <p>Puedes seleccionar más de una opción.</p>
        <div className="feature-options" role="group" aria-label="Características del departamento">
          {depaFeatureOptions.map((feature) => {
            const selected = features.includes(feature);
            return <button key={feature} className={selected ? "selected" : ""} aria-pressed={selected} onClick={() => onToggleFeature(feature)}><span>{selected ? "✓" : "+"}</span>{feature}</button>;
          })}
        </div>
      </section>
    </div>
  );
}

function useDebouncedValue<T>(value: T, delay: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timeout);
  }, [delay, value]);
  return debounced;
}

function ListingSkeleton() {
  return (
    <div className="listing-card listing-skeleton" aria-hidden="true">
      <span className="skeleton-image" />
      <span className="skeleton-line wide" />
      <span className="skeleton-line medium" />
      <span className="skeleton-line short" />
      <span className="skeleton-action" />
    </div>
  );
}

function readInitialUrlState() {
  const defaults = {
    category: "Roomies" as Category,
    search: "",
    service: "Todos",
    minPrice: "",
    maxPrice: "",
    bedrooms: "Todos" as BedroomFilter,
    features: [] as DepaFeature[],
    sort: "recommended" as ListingSort,
    checkIn: dateValue(addDays(new Date(), 14)),
    checkOut: dateValue(addDays(new Date(), 15)),
    guests: 2,
  };
  if (typeof window === "undefined") return defaults;
  const parameters = new URLSearchParams(window.location.search);
  const category = parameters.get("category");
  const requestedSort = parameters.get("sort");
  const requestedBedrooms = parameters.get("bedrooms");
  const requestedService = parameters.get("service");
  const requestedCheckIn = parameters.get("checkIn");
  const requestedCheckOut = parameters.get("checkOut");
  const requestedGuests = Number(parameters.get("guests"));
  return {
    category: category && categories.some((item) => item.id === category) ? category as Category : defaults.category,
    search: parameters.get("q") ?? defaults.search,
    service: ["Todos", "Mudanza", "Corporativo"].includes(requestedService ?? "") ? requestedService as string : defaults.service,
    minPrice: parameters.get("minPrice") ?? defaults.minPrice,
    maxPrice: parameters.get("maxPrice") ?? defaults.maxPrice,
    bedrooms: requestedBedrooms && bedroomOptions.includes(requestedBedrooms as BedroomFilter) ? requestedBedrooms as BedroomFilter : defaults.bedrooms,
    features: (parameters.get("features") ?? "").split(",").filter((feature): feature is DepaFeature => depaFeatureOptions.includes(feature as DepaFeature)),
    sort: requestedSort && sortOptions.some((item) => item.value === requestedSort) ? requestedSort as ListingSort : defaults.sort,
    checkIn: requestedCheckIn && /^\d{4}-\d{2}-\d{2}$/.test(requestedCheckIn) ? requestedCheckIn : defaults.checkIn,
    checkOut: requestedCheckOut && /^\d{4}-\d{2}-\d{2}$/.test(requestedCheckOut) ? requestedCheckOut : defaults.checkOut,
    guests: Number.isInteger(requestedGuests) && requestedGuests >= 1 && requestedGuests <= 16 ? requestedGuests : defaults.guests,
  };
}

export default function Home() {
  const [initialUrlState] = useState(readInitialUrlState);
  const [activeCategory, setActiveCategory] = useState<Category>(initialUrlState.category);
  const [search, setSearch] = useState(initialUrlState.search);
  const [service, setService] = useState(initialUrlState.service);
  const [minPrice, setMinPrice] = useState(initialUrlState.minPrice);
  const [maxPrice, setMaxPrice] = useState(initialUrlState.maxPrice);
  const [bedrooms, setBedrooms] = useState<BedroomFilter>(initialUrlState.bedrooms);
  const [selectedDepaFeatures, setSelectedDepaFeatures] = useState<DepaFeature[]>(initialUrlState.features);
  const [sort, setSort] = useState<ListingSort>(initialUrlState.sort);
  const [checkIn, setCheckIn] = useState(initialUrlState.checkIn);
  const [checkOut, setCheckOut] = useState(initialUrlState.checkOut);
  const [guestCount, setGuestCount] = useState(initialUrlState.guests);
  const [showSearchOptions, setShowSearchOptions] = useState(false);
  const [showAirbnbCalendar, setShowAirbnbCalendar] = useState(false);
  const [showAirbnbGuests, setShowAirbnbGuests] = useState(false);
  const [airbnbDateStage, setAirbnbDateStage] = useState<AirbnbDateStage>("arrival");
  const [calendarMonth, setCalendarMonth] = useState(() => monthStart(addDays(new Date(), 14)));
  const [showDepaFilters, setShowDepaFilters] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showPlans, setShowPlans] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [showMyListings, setShowMyListings] = useState(false);
  const [showFavorites, setShowFavorites] = useState(false);
  const [favoriteDetails, setFavoriteDetails] = useState<Listing[]>([]);
  const [favoritesStatus, setFavoritesStatus] = useState<"idle" | "loading" | "error">("idle");
  const [favoritesRetry, setFavoritesRetry] = useState(0);
  const [publishAfterLogin, setPublishAfterLogin] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authLoaded, setAuthLoaded] = useState(false);
  const [oauthRedirectResult, setOauthRedirectResult] = useState<string | null>(() =>
    typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("auth"));
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [galleryIndexes, setGalleryIndexes] = useState<Record<number, number>>({});
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [favorites, setFavorites] = useState<number[]>([]);
  const [listingsFromDb, setListingsFromDb] = useState<Listing[]>([]);
  const [loadedCategory, setLoadedCategory] = useState<Category | null>(null);
  const [listingsMeta, setListingsMeta] = useState<ListingsMeta | null>(null);
  const [listingsStatus, setListingsStatus] = useState<ListingsStatus>("loading");
  const [listingsError, setListingsError] = useState("");
  const [retryListings, setRetryListings] = useState(0);
  const [favoriteMutations, setFavoriteMutations] = useState<number[]>([]);
  const [notice, setNotice] = useState("");
  const [noticeTone, setNoticeTone] = useState<"success" | "error">("success");
  const [showGoogleNudge, setShowGoogleNudge] = useState(false);
  // Si el visitante ya cerró el banner hace poco (localStorage) no se vuelve
  // a mostrar; en ese caso solo queda armado el recordatorio corto.
  const [welcomeNudgeDismissed, setWelcomeNudgeDismissed] = useState(welcomeNudgeRecentlyDismissed);
  const autoNudgesShownRef = useRef(0);
  const favoritesFetchedRef = useRef("");
  const listingsCacheRef = useRef(new Map<string, { etag: string; payload: ListingsPayload }>());
  const noticeTimeoutRef = useRef<number | null>(null);
  const nextPageRef = useRef(2);
  const listingsQueryRef = useRef("");
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const deferredSearch = useDeferredValue(search);
  const debouncedSearch = useDebouncedValue(deferredSearch, 260);
  const debouncedMinPrice = useDebouncedValue(minPrice, 350);
  const debouncedMaxPrice = useDebouncedValue(maxPrice, 350);

  const detail = categoryDetails[activeCategory];
  const airbnbNights = stayNights(checkIn, checkOut);
  const dateLabel = activeCategory === "Airbnb"
    ? `${formatShortDate(checkIn)} – ${formatShortDate(checkOut)} · ${airbnbNights} ${airbnbNights === 1 ? "noche" : "noches"}`
    : detail.date;
  const bedroomSummary = bedrooms === "Todos"
    ? "Cualquier cantidad"
    : bedrooms === "4+"
      ? "4 o más dormitorios"
      : `${bedrooms} ${bedrooms === "1" ? "dormitorio" : "dormitorios"}`;
  const budgetSummary = minPrice && maxPrice
    ? `S/ ${Number(minPrice).toLocaleString("es-PE")} – ${Number(maxPrice).toLocaleString("es-PE")}`
    : maxPrice
      ? `Hasta S/ ${Number(maxPrice).toLocaleString("es-PE")}`
      : minPrice
        ? `Desde S/ ${Number(minPrice).toLocaleString("es-PE")}`
        : "Cualquier presupuesto";
  const activeDepaFilterCount = (bedrooms === "Todos" ? 0 : 1) + (minPrice ? 1 : 0) + (maxPrice ? 1 : 0) + selectedDepaFeatures.length;

  useEffect(() => {
    const parameters = new URLSearchParams();
    parameters.set("category", activeCategory);
    if (search.trim()) parameters.set("q", search.trim());
    if (sort !== "recommended") parameters.set("sort", sort);
    if (activeCategory === "Depas") {
      if (minPrice) parameters.set("minPrice", minPrice);
      if (maxPrice) parameters.set("maxPrice", maxPrice);
      if (bedrooms !== "Todos") parameters.set("bedrooms", bedrooms);
      if (selectedDepaFeatures.length) parameters.set("features", selectedDepaFeatures.join(","));
    }
    if (activeCategory !== "Roomies" && activeCategory !== "Depas" && maxPrice) parameters.set("maxPrice", maxPrice);
    if (activeCategory === "Transporte" && service !== "Todos") parameters.set("service", service);
    if (activeCategory === "Airbnb") {
      parameters.set("checkIn", checkIn);
      parameters.set("checkOut", checkOut);
      parameters.set("guests", String(guestCount));
    }
    const query = parameters.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  }, [activeCategory, bedrooms, checkIn, checkOut, guestCount, maxPrice, minPrice, search, selectedDepaFeatures, service, sort]);

  const listingsQueryString = useMemo(() => {
    const parameters = new URLSearchParams({ category: activeCategory, pageSize: "24", sort });
    if (debouncedSearch.trim()) parameters.set("q", debouncedSearch.trim());
    const invalidPriceRange = Boolean(
      debouncedMinPrice && debouncedMaxPrice && Number(debouncedMinPrice) > Number(debouncedMaxPrice),
    );
    if (activeCategory === "Depas") {
      if (debouncedMinPrice && !invalidPriceRange) parameters.set("minPrice", debouncedMinPrice);
      if (debouncedMaxPrice) parameters.set("maxPrice", debouncedMaxPrice);
      if (bedrooms !== "Todos") parameters.set("bedrooms", bedrooms);
      if (selectedDepaFeatures.length) parameters.set("features", selectedDepaFeatures.join(","));
    }
    if (activeCategory !== "Roomies" && activeCategory !== "Depas" && debouncedMaxPrice) parameters.set("maxPrice", debouncedMaxPrice);
    if (activeCategory === "Transporte" && service !== "Todos") parameters.set("service", service);
    return parameters.toString();
  }, [activeCategory, bedrooms, debouncedMaxPrice, debouncedMinPrice, debouncedSearch, selectedDepaFeatures, service, sort]);

  useEffect(() => {
    const controller = new AbortController();
    listingsQueryRef.current = listingsQueryString;
    const requestUrl = `/api/listings?${listingsQueryString}`;
    const cached = listingsCacheRef.current.get(requestUrl);
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setListingsStatus("loading");
      setListingsError("");
    });

    fetch(requestUrl, {
      signal: controller.signal,
      cache: "no-cache",
      headers: cached?.etag ? { "If-None-Match": cached.etag } : undefined,
    })
      .then(async (response) => {
        if (response.status === 304 && cached) return cached.payload;
        const payload = (await response.json()) as ListingsPayload;
        if (!response.ok) throw new Error(payload.error ?? "No se pudo consultar la base de datos");
        const etag = response.headers.get("ETag") ?? "";
        if (etag) listingsCacheRef.current.set(requestUrl, { etag, payload });
        return payload;
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        setListingsFromDb(payload.listings ?? []);
        setListingsMeta(payload.meta ?? null);
        setLoadedCategory(activeCategory);
        setListingsStatus("ready");
        nextPageRef.current = 2;
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setListingsFromDb([]);
        setListingsMeta(null);
        setLoadedCategory(activeCategory);
        setListingsStatus("error");
        setListingsError(error instanceof Error ? error.message : "No se pudo actualizar la búsqueda");
      });

    return () => controller.abort();
  }, [activeCategory, listingsQueryString, retryListings]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me")
      .then(async (response) => {
        if (!response.ok) throw new Error("No se pudo verificar la sesión");
        return (await response.json()) as { user?: AuthUser | null };
      })
      .then((payload) => {
        if (!cancelled) setCurrentUser(payload.user ?? null);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setAuthLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // El acceso con Google por redirección vuelve a la portada con ?auth=…: el
  // parámetro se lee antes de que el efecto de filtros reescriba la URL y la
  // sesión ya viene en la cookie; aquí solo se avisa el resultado.
  useEffect(() => {
    if (!oauthRedirectResult) return;
    const timer = window.setTimeout(() => {
      if (oauthRedirectResult === "google-ok") flashNotice("Sesión iniciada con Google");
      if (oauthRedirectResult === "google-error") {
        setShowLogin(true);
        flashNotice("No pudimos completar el acceso con Google. Inténtalo nuevamente.", "error");
      }
      setOauthRedirectResult(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [oauthRedirectResult]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/favorites")
      .then(async (response) => {
        if (!response.ok) throw new Error("No se pudieron leer los favoritos");
        return (await response.json()) as { favorites?: number[] };
      })
      .then((payload) => {
        if (!cancelled) setFavorites(payload.favorites ?? []);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Al abrir «Mis favoritos», si algún guardado no está entre los anuncios ya
  // cargados se piden todos al backend (mismo visitante por cookie) para que
  // la lista siempre muestre foto, precio y contacto completos. La firma en
  // favoritesFetchedRef evita repetir la consulta si un favorito apunta a un
  // anuncio que ya no existe en la base.
  useEffect(() => {
    if (!showFavorites || favorites.length === 0) return;
    const signature = [...favorites].sort((left, right) => left - right).join(",");
    if (favoritesFetchedRef.current === signature) return;
    const knownIds = new Set([...listingsFromDb, ...favoriteDetails, ...demoListings].map((listing) => listing.id));
    if (favorites.every((id) => knownIds.has(id))) return;
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) setFavoritesStatus("loading");
    });
    fetch("/api/favorites/listings", { signal: controller.signal, cache: "no-cache" })
      .then(async (response) => {
        const payload = (await response.json()) as { listings?: Listing[]; error?: string };
        if (!response.ok) throw new Error(payload.error ?? "No se pudieron cargar tus favoritos");
        return payload.listings ?? [];
      })
      .then((favoriteListings) => {
        if (controller.signal.aborted) return;
        favoritesFetchedRef.current = signature;
        setFavoriteDetails(favoriteListings);
        setFavoritesStatus("idle");
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setFavoritesStatus("error");
      });
    return () => controller.abort();
  }, [favoriteDetails, favorites, favoritesRetry, listingsFromDb, showFavorites]);

  useEffect(() => () => {
    if (noticeTimeoutRef.current !== null) window.clearTimeout(noticeTimeoutRef.current);
  }, []);

  // Primer aviso para visitantes: un banner discreto bajo la cabecera ~1.5 s
  // después de pintar. Nunca se muestra con sesión activa ni si el visitante
  // lo cerró hace poco (queda registrado en localStorage).
  useEffect(() => {
    if (!authLoaded || currentUser || welcomeNudgeDismissed) return;
    if (autoNudgesShownRef.current >= MAX_AUTO_GOOGLE_NUDGES) return;
    const timer = window.setTimeout(() => {
      autoNudgesShownRef.current += 1;
      setShowGoogleNudge(true);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [authLoaded, currentUser, welcomeNudgeDismissed]);

  // Segundo aviso, solo si cerraron el primero: un toast corto al bajar ~40 %
  // de los resultados o tras ~20 s seguir como visitante, lo que pase antes.
  useEffect(() => {
    if (!authLoaded || currentUser || !welcomeNudgeDismissed) return;
    if (autoNudgesShownRef.current >= MAX_AUTO_GOOGLE_NUDGES) return;
    const memory = readGoogleNudgeMemory();
    if (typeof memory.reminderShownAt === "number" && Date.now() - memory.reminderShownAt < GOOGLE_NUDGE_COOLDOWN_MS) return;
    let fired = false;
    function cleanup() {
      window.clearTimeout(timer);
      window.removeEventListener("scroll", handleScroll);
    }
    function fire() {
      if (fired) return;
      fired = true;
      cleanup();
      autoNudgesShownRef.current += 1;
      saveGoogleNudgeMemory({ reminderShownAt: Date.now() });
      flashNotice("Inicia sesión con Google para no perder tus favoritos.");
    }
    function handleScroll() {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      if (scrollable > 0 && window.scrollY / scrollable >= 0.4) fire();
    }
    const timer = window.setTimeout(fire, 20_000);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return cleanup;
  }, [authLoaded, currentUser, welcomeNudgeDismissed]);

  useEffect(() => {
    function closeTransientUi(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setShowMenu(false);
      setShowSearchOptions(false);
      setShowAirbnbCalendar(false);
      setShowAirbnbGuests(false);
      setShowDepaFilters(false);
    }
    document.addEventListener("keydown", closeTransientUi);
    return () => document.removeEventListener("keydown", closeTransientUi);
  }, []);

  const hasDatabaseCategory = loadedCategory === activeCategory && listingsStatus !== "error";
  const categoryListings = (hasDatabaseCategory ? listingsFromDb : demoListings)
    .filter((listing) => listing.category === activeCategory);

  const visibleListings = useMemo(() => {
    const parsedMin = Number(minPrice);
    const parsedMax = Number(maxPrice);
    const filteredListings = categoryListings.filter((listing) => {
      if (activeCategory === "Transporte" && service !== "Todos" && listing.service !== service) return false;
      if (activeCategory === "Depas" && minPrice && listing.price < parsedMin) return false;
      if (maxPrice && listing.price > parsedMax) return false;
      if (activeCategory === "Depas") {
        const details = depaDetails(listing);
        if (bedrooms !== "Todos") {
          const requestedBedrooms = bedrooms === "4+" ? 4 : Number(bedrooms);
          if (bedrooms === "4+") {
            if (details.bedroomsMax < requestedBedrooms) return false;
          } else if (requestedBedrooms < details.bedroomsMin || requestedBedrooms > details.bedroomsMax) {
            return false;
          }
        }
        if (!selectedDepaFeatures.every((feature) => details.features.includes(feature))) return false;
      }
      return true;
    });

    let results = filteredListings;
    if (search.trim()) {
      const scored = filteredListings
        .map((listing) => ({ listing, score: listingSearchScore(listing, search) }))
        .filter((result) => result.score >= 0);
      if (sort === "recommended") scored.sort((left, right) => right.score - left.score);
      results = scored.map((result) => result.listing);
    }
    if (sort === "price_asc") return [...results].sort((left, right) => left.price - right.price);
    if (sort === "price_desc") return [...results].sort((left, right) => right.price - left.price);
    if (sort === "rating") return [...results].sort((left, right) => right.rating - left.rating || right.reviews - left.reviews);
    if (sort === "newest" && !hasDatabaseCategory) return [...results].sort((left, right) => right.id - left.id);
    return results;
  }, [activeCategory, bedrooms, categoryListings, hasDatabaseCategory, maxPrice, minPrice, search, selectedDepaFeatures, service, sort]);

  const resultsTotal = hasDatabaseCategory ? (listingsMeta?.total ?? visibleListings.length) : visibleListings.length;
  const isInitialListingsLoad = listingsStatus === "loading" && loadedCategory !== activeCategory;
  const isRefreshingListings = listingsStatus === "loading" && loadedCategory === activeCategory;
  const resultsTitle = search.trim()
    ? `${detail.noun.charAt(0).toUpperCase()}${detail.noun.slice(1)} para “${search.trim()}”`
    : activeCategory === "Roomies"
      ? "Habitaciones para compartir"
      : activeCategory === "Depas"
        ? "Departamentos en Lima"
        : activeCategory === "Airbnb"
          ? "Alojamientos para tu próxima estadía"
          : "Transporte verificado en Lima";
  const singularNoun: Record<Category, string> = { Roomies: "habitación", Depas: "departamento", Airbnb: "alojamiento", Transporte: "servicio" };
  const filterButtonCount = activeCategory === "Depas"
    ? activeDepaFilterCount
    : (maxPrice ? 1 : 0) + (activeCategory === "Transporte" && service !== "Todos" ? 1 : 0);
  const activeFilterChips: Array<{ key: string; label: string; clear: () => void }> = [];
  if (search.trim()) activeFilterChips.push({ key: "search", label: search.trim(), clear: () => setSearch("") });
  if (bedrooms !== "Todos" && activeCategory === "Depas") activeFilterChips.push({ key: "bedrooms", label: bedroomSummary, clear: () => setBedrooms("Todos") });
  if ((minPrice || maxPrice) && activeCategory === "Depas") activeFilterChips.push({ key: "budget", label: budgetSummary, clear: () => { setMinPrice(""); setMaxPrice(""); } });
  if (maxPrice && activeCategory !== "Depas") activeFilterChips.push({ key: "budget", label: `Hasta S/ ${Number(maxPrice).toLocaleString("es-PE")}`, clear: () => setMaxPrice("") });
  if (activeCategory === "Depas") selectedDepaFeatures.forEach((feature) => activeFilterChips.push({ key: feature, label: feature, clear: () => toggleDepaFeature(feature) }));
  if (activeCategory === "Transporte" && service !== "Todos") activeFilterChips.push({ key: "service", label: service, clear: () => setService("Todos") });

  // Los favoritos se resuelven contra los anuncios ya cargados; los que
  // vienen del backend (favoriteDetails) pisan a los de demostración y los de
  // la búsqueda activa pisan a ambos, respetando el orden en que se guardaron.
  const favoriteListings = useMemo(() => {
    const pool = new Map<number, Listing>();
    for (const listing of demoListings) pool.set(listing.id, listing);
    for (const listing of favoriteDetails) pool.set(listing.id, listing);
    for (const listing of listingsFromDb) pool.set(listing.id, listing);
    return favorites
      .map((id) => pool.get(id))
      .filter((listing): listing is Listing => Boolean(listing));
  }, [favoriteDetails, favorites, listingsFromDb]);

  const selectedGallery = selectedListing ? listingImages(selectedListing) : [];
  const safeSelectedImageIndex = selectedGallery.length
    ? Math.min(selectedImageIndex, selectedGallery.length - 1)
    : 0;

  function changeCategory(category: Category) {
    setActiveCategory(category);
    setSort("recommended");
    setSearch("");
    setService("Todos");
    setMinPrice("");
    setMaxPrice("");
    setBedrooms("Todos");
    setSelectedDepaFeatures([]);
    setShowSearchOptions(false);
    setShowAirbnbCalendar(false);
    setShowAirbnbGuests(false);
    setShowDepaFilters(false);
    setShowMenu(false);
  }

  function runSearch() {
    setShowSearchOptions(false);
    setShowAirbnbCalendar(false);
    setShowAirbnbGuests(false);
    setShowDepaFilters(false);
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
  }

  function openDepaFilters() {
    setShowMenu(false);
    setShowSearchOptions(false);
    setShowAirbnbCalendar(false);
    setShowAirbnbGuests(false);
    setShowDepaFilters(true);
  }

  function openFiltersModal() {
    setShowMenu(false);
    setShowFilters(true);
  }

  function openAirbnbCalendar(stage: AirbnbDateStage) {
    const selectedDate = stage === "arrival" ? checkIn : checkOut;
    setAirbnbDateStage(stage);
    setCalendarMonth(monthStart(parseDateValue(selectedDate)));
    setShowAirbnbCalendar(true);
    setShowAirbnbGuests(false);
    setShowSearchOptions(false);
    setShowDepaFilters(false);
  }

  function selectAirbnbDate(value: string) {
    if (airbnbDateStage === "arrival") {
      setCheckIn(value);
      setCheckOut(dateValue(addDays(parseDateValue(value), 1)));
      setAirbnbDateStage("departure");
      return;
    }
    if (value <= checkIn) return;
    setCheckOut(value);
  }

  function openAirbnbGuests() {
    setShowAirbnbGuests((open) => !open);
    setShowAirbnbCalendar(false);
    setShowSearchOptions(false);
    setShowDepaFilters(false);
  }

  function toggleDepaFeature(feature: DepaFeature) {
    setSelectedDepaFeatures((current) => current.includes(feature)
      ? current.filter((item) => item !== feature)
      : [...current, feature]);
  }

  async function toggleFavorite(id: number) {
    if (favoriteMutations.includes(id)) return;
    const alreadyFavorite = favorites.includes(id);
    setFavoriteMutations((current) => [...current, id]);
    setFavorites((current) => alreadyFavorite
      ? current.filter((favoriteId) => favoriteId !== id)
      : [...current, id]);
    try {
      const response = await fetch("/api/favorites", {
        method: alreadyFavorite ? "DELETE" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listingId: id }),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "No se pudo guardar");
      flashNotice(alreadyFavorite ? "Quitado de tus favoritos" : "Guardado en tus favoritos");
    } catch (error) {
      setFavorites((current) => alreadyFavorite
        ? [...current, id]
        : current.filter((favoriteId) => favoriteId !== id));
      flashNotice(error instanceof Error ? error.message : "No pudimos actualizar tus favoritos", "error");
    } finally {
      setFavoriteMutations((current) => current.filter((listingId) => listingId !== id));
    }
  }

  function trackInquiry(listingId: number) {
    void fetch("/api/inquiries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ listingId, channel: "whatsapp" }),
      keepalive: true,
    });
  }

  function flashNotice(message: string, tone: "success" | "error" = "success") {
    if (noticeTimeoutRef.current !== null) window.clearTimeout(noticeTimeoutRef.current);
    setNotice(message);
    setNoticeTone(tone);
    noticeTimeoutRef.current = window.setTimeout(() => setNotice(""), 3000);
  }

  function resetFilters() {
    setSearch("");
    setMinPrice("");
    setMaxPrice("");
    setService("Todos");
    setBedrooms("Todos");
    setSelectedDepaFeatures([]);
  }

  function refreshListings() {
    listingsCacheRef.current.clear();
    setRetryListings((value) => value + 1);
  }

  async function loadMoreListings() {
    if (isLoadingMore || !listingsMeta?.hasMore) return;
    const queryAtStart = listingsQueryString;
    setIsLoadingMore(true);
    try {
      const response = await fetch(`/api/listings?${listingsQueryString}&page=${nextPageRef.current}`, { cache: "no-cache" });
      const payload = (await response.json()) as ListingsPayload;
      if (!response.ok) throw new Error(payload.error ?? "No se pudieron cargar más anuncios");
      if (listingsQueryRef.current !== queryAtStart) return;
      setListingsFromDb((current) => {
        const knownIds = new Set(current.map((listing) => listing.id));
        return [...current, ...(payload.listings ?? []).filter((listing) => !knownIds.has(listing.id))];
      });
      setListingsMeta(payload.meta ?? null);
      nextPageRef.current += 1;
    } catch (loadError) {
      flashNotice(loadError instanceof Error ? loadError.message : "No se pudieron cargar más anuncios", "error");
    } finally {
      setIsLoadingMore(false);
    }
  }

  function requestPublish() {
    setShowMenu(false);
    if (!currentUser) {
      setPublishAfterLogin(true);
      setShowLogin(true);
      flashNotice(authLoaded ? "Inicia sesión con Google para publicar" : "Verificando tu sesión…");
      return;
    }
    setPublishAfterLogin(false);
    setShowPublish(true);
  }

  // Cierra el banner de bienvenida y lo anota en localStorage. Si el visitante
  // tocó «Continuar con Google» se abre el acceso; si solo lo cerró, queda
  // armado el único recordatorio corto de la visita.
  function dismissGoogleNudge(continueWithGoogle: boolean) {
    setShowGoogleNudge(false);
    saveGoogleNudgeMemory({ welcomeDismissedAt: Date.now() });
    if (continueWithGoogle) {
      openLogin();
      return;
    }
    setWelcomeNudgeDismissed(true);
  }

  function authenticated(user: AuthUser) {
    setCurrentUser(user);
    setShowLogin(false);
    setShowGoogleNudge(false);
    flashNotice(`Bienvenido, ${user.name}`);
    if (publishAfterLogin) {
      setPublishAfterLogin(false);
      setShowPublish(true);
    }
  }

  function loggedOut() {
    setCurrentUser(null);
    setPublishAfterLogin(false);
    setShowLogin(false);
    flashNotice("Sesión cerrada correctamente");
  }

  function moveGallery(listing: Listing, direction: 1 | -1) {
    const images = listingImages(listing);
    if (images.length < 2) return;
    setGalleryIndexes((current) => {
      const index = Math.min(current[listing.id] ?? 0, images.length - 1);
      const next = Math.min(images.length - 1, Math.max(0, index + direction));
      return next === index ? current : { ...current, [listing.id]: next };
    });
  }

  function openListing(listing: Listing) {
    setShowMenu(false);
    setSelectedImageIndex(galleryIndexes[listing.id] ?? 0);
    setSelectedListing(listing);
  }

  function openLogin() {
    setShowMenu(false);
    setShowLogin(true);
  }

  function openPlans() {
    setShowMenu(false);
    setShowPlans(true);
  }

  function openFavorites() {
    setShowMenu(false);
    setShowFavorites(true);
  }

  return (
    <div className="app-shell">
      <header className="market-header">
        <div className="services-top">
          <button className="brand" onClick={() => changeCategory("Roomies")} aria-label={`Ir al inicio de ${BRAND}`}>
            <span className="brand-symbol"><BrandKeysIcon /></span>
            <span>{BRAND_MARK}</span>
          </button>

          <nav className="service-nav" aria-label={`Servicios de ${BRAND}`}>
            {categories.map((category) => (
              <button key={category.id} className={`service-tab ${activeCategory === category.id ? "active" : ""}`} aria-current={activeCategory === category.id ? "page" : undefined} onClick={() => changeCategory(category.id)}>
                <span className={`service-icon service-icon-${category.id.toLowerCase()}`}><ServiceIcon category={category.id} /></span>
                <span><strong>{category.label}</strong><small>{category.short}</small></span>
              </button>
            ))}
          </nav>

          <div className="header-actions">
            {/* CTA principal de la cabecera: el acceso con Google para
                visitantes, o la cuenta activa si ya hay sesión. Publicar vive
                en el menú (hamburguesa) y en el pie de página. */}
            {currentUser ? (
              <button className="host-link account-link" onClick={openLogin} aria-label={`Abrir mi cuenta, ${currentUser.name}`}>
                {currentUser.avatarUrl ? (
                  <img className="account-avatar" src={currentUser.avatarUrl} alt="" referrerPolicy="no-referrer" />
                ) : (
                  <span className="account-initial" aria-hidden="true">{currentUser.name.trim().charAt(0).toUpperCase() || "☺"}</span>
                )}
                <span className="account-name">{currentUser.name.trim().split(/\s+/)[0] || "Mi cuenta"}</span>
              </button>
            ) : (
              <button className="host-link login-link" onClick={openLogin}>
                <span className="login-google-badge" aria-hidden="true"><GoogleGIcon /></span>
                <span>Iniciar sesión</span>
              </button>
            )}
            <button className="globe-button" aria-label="Idioma y moneda"><GlobeIcon /></button>
            <button className="menu-trigger" aria-label="Abrir menú" aria-expanded={showMenu} onClick={() => setShowMenu((open) => !open)}>
              <span className="hamburger"><i /><i /><i /></span>
            </button>
          </div>
        </div>

        <div className="search-row">
          <div className={`compact-search ${activeCategory === "Roomies" ? "roomies-search" : ""} ${activeCategory === "Depas" ? "depas-search" : ""} ${activeCategory === "Airbnb" ? "airbnb-search" : ""}`} role="search">
            <label className="compact-field location-field">
              <span className="location-icon"><LocationIcon /></span>
              <input
                aria-label={activeCategory === "Roomies" ? "Buscar habitaciones" : "Ubicación"}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter") runSearch(); }}
                placeholder={activeCategory === "Roomies" ? "Distrito, zona o cuarto" : activeCategory === "Depas" ? "Busca departamentos por distrito o ciudad" : activeCategory === "Airbnb" ? "Busca alojamientos por destino" : "Busca mudanzas o transporte corporativo"}
              />
            </label>
            {activeCategory === "Depas" && <>
              <button className="compact-field depa-filter-field" onClick={openDepaFilters} aria-expanded={showDepaFilters}>
                <span>Dormitorios</span><strong>{bedroomSummary}</strong>
              </button>
              <button className="compact-field depa-filter-field" onClick={openDepaFilters} aria-expanded={showDepaFilters}>
                <span>Presupuesto</span><strong>{budgetSummary}</strong>
              </button>
              <button className="depa-mobile-filter" onClick={openDepaFilters} aria-label={`Abrir filtros de departamentos${activeDepaFilterCount ? `, ${activeDepaFilterCount} activos` : ""}`} aria-expanded={showDepaFilters}>
                <FilterIcon />{activeDepaFilterCount > 0 && <b>{activeDepaFilterCount}</b>}
              </button>
            </>}
            {activeCategory === "Airbnb" && <>
              <button className={`compact-field airbnb-date-field ${showAirbnbCalendar && airbnbDateStage === "arrival" ? "active" : ""}`} onClick={() => openAirbnbCalendar("arrival")} aria-label={`Llegada, ${formatDetailDate(checkIn)}`} aria-expanded={showAirbnbCalendar && airbnbDateStage === "arrival"}>
                <span>Llegada</span><strong>{formatShortDate(checkIn)}</strong>
              </button>
              <button className={`compact-field airbnb-date-field ${showAirbnbCalendar && airbnbDateStage === "departure" ? "active" : ""}`} onClick={() => openAirbnbCalendar("departure")} aria-label={`Salida, ${formatDetailDate(checkOut)}`} aria-expanded={showAirbnbCalendar && airbnbDateStage === "departure"}>
                <span>Salida</span><strong>{formatShortDate(checkOut)}</strong>
              </button>
              <button className={`compact-field guest-field airbnb-guest-field ${showAirbnbGuests ? "active" : ""}`} onClick={openAirbnbGuests} aria-expanded={showAirbnbGuests}>
                <span>Huéspedes</span><strong>{guestCount} {guestCount === 1 ? "huésped" : "huéspedes"}</strong>
              </button>
            </>}
            {activeCategory === "Transporte" && <>
              <button className="compact-field date-field" onClick={() => setShowSearchOptions((open) => !open)} aria-expanded={showSearchOptions}>
                <strong>{detail.date}</strong>
              </button>
              <button className="compact-field guest-field" onClick={() => setShowSearchOptions((open) => !open)} aria-expanded={showSearchOptions}>
                <strong>{detail.guests}</strong>
              </button>
            </>}
            <button className="search-button" onClick={runSearch} aria-label="Buscar">
              <SearchIcon />
            </button>
          </div>
        </div>

        {showDepaFilters && activeCategory === "Depas" && (
          <div className="depa-filter-popover" role="dialog" aria-label="Filtros de departamentos">
            <div className="depa-filter-heading"><div><strong>Encuentra el departamento ideal</strong><span>Los resultados se actualizan al instante.</span></div><button onClick={() => setShowDepaFilters(false)} aria-label="Cerrar filtros">×</button></div>
            <DepaFilterControls
              bedrooms={bedrooms}
              minimumPrice={minPrice}
              maximumPrice={maxPrice}
              features={selectedDepaFeatures}
              onBedroomsChange={setBedrooms}
              onMinimumPriceChange={setMinPrice}
              onMaximumPriceChange={setMaxPrice}
              onToggleFeature={toggleDepaFeature}
            />
            <div className="depa-filter-footer"><button className="text-action" onClick={resetFilters}>Limpiar todo</button><button className="dark-button" onClick={runSearch}>Ver {visibleListings.length} {visibleListings.length === 1 ? "departamento" : "departamentos"}</button></div>
          </div>
        )}

        {showAirbnbCalendar && activeCategory === "Airbnb" && <AirbnbDatePicker
          checkIn={checkIn}
          checkOut={checkOut}
          stage={airbnbDateStage}
          visibleMonth={calendarMonth}
          onStageChange={(stage) => {
            setAirbnbDateStage(stage);
            setCalendarMonth(monthStart(parseDateValue(stage === "arrival" ? checkIn : checkOut)));
          }}
          onMonthChange={setCalendarMonth}
          onSelect={selectAirbnbDate}
          onClose={() => setShowAirbnbCalendar(false)}
        />}

        {showAirbnbGuests && activeCategory === "Airbnb" && (
          <div className="airbnb-guests-popover" role="dialog" aria-label="Cantidad de huéspedes">
            <div className="guest-control"><span><strong>Huéspedes</strong><small>Adultos y viajeros desde 13 años</small></span><div><button onClick={() => setGuestCount((count) => Math.max(1, count - 1))} disabled={guestCount === 1} aria-label="Quitar huésped">−</button><b>{guestCount}</b><button onClick={() => setGuestCount((count) => Math.min(16, count + 1))} disabled={guestCount === 16} aria-label="Agregar huésped">＋</button></div></div>
            <button className="apply-search" onClick={() => setShowAirbnbGuests(false)}>Listo</button>
          </div>
        )}

        {showSearchOptions && activeCategory === "Transporte" && (
          <div className="search-options-popover">
            <div className="date-controls"><label>Llegada<input type="date" value={checkIn} onChange={(event) => setCheckIn(event.target.value)} /></label><label>Salida<input type="date" min={checkIn} value={checkOut} onChange={(event) => setCheckOut(event.target.value)} /></label></div>
            <div className="guest-control"><span><strong>Viajeros</strong><small>¿Cuántas personas van?</small></span><div><button onClick={() => setGuestCount((count) => Math.max(1, count - 1))} aria-label="Quitar huésped">−</button><b>{guestCount}</b><button onClick={() => setGuestCount((count) => Math.min(16, count + 1))} aria-label="Agregar huésped">＋</button></div></div>
            <button className="apply-search" onClick={() => setShowSearchOptions(false)}>Aplicar búsqueda</button>
          </div>
        )}

        {showMenu && (
          <div className="menu-popover">
            <span className="menu-section-label">Cuenta</span>
            <button className="menu-strong" onClick={openLogin}>{currentUser ? `Mi cuenta · ${currentUser.name}` : "Iniciar sesión"}</button>
            {currentUser?.role === "admin" && <button onClick={() => { setShowMenu(false); setShowAdminPanel(true); }}>Panel de administración</button>}
            {currentUser && <button onClick={() => { setShowMenu(false); setShowMyListings(true); }}>Mis anuncios</button>}
            <div className="menu-divider" />
            <span className="menu-section-label">Publicar</span>
            {/* Entrada principal de publicación: la cabecera ahora es para el
                acceso, así que publicar vive aquí, en el menú. */}
            <button className="menu-strong" onClick={requestPublish}>Publicar un anuncio</button>
            <button onClick={openPlans}>Ver planes para publicar</button>
            <div className="menu-divider" />
            <span className="menu-section-label">Guardados</span>
            <button onClick={openFavorites}>Mis favoritos {favorites.length > 0 && <span>{favorites.length}</span>}</button>
            <div className="menu-divider" />
            <span className="menu-section-label">Ayuda</span>
            <button onClick={openFiltersModal}>Filtros de búsqueda</button>
            <button onClick={() => { flashNotice(`Soporte directo: ${SUPPORT_EMAIL}`); setShowMenu(false); }}>Centro de ayuda</button>
          </div>
        )}
      </header>

      {showGoogleNudge && !currentUser && (
        <div className="google-nudge-banner" role="status" aria-live="polite">
          <span className="google-nudge-icon" aria-hidden="true"><GoogleGIcon /></span>
          <p>Entra con Google para guardar favoritos y publicar.</p>
          <button type="button" className="google-nudge-action" onClick={() => dismissGoogleNudge(true)}>Continuar con Google</button>
          <button type="button" className="google-nudge-close" onClick={() => dismissGoogleNudge(false)} aria-label="Cerrar aviso de acceso con Google">×</button>
        </div>
      )}

      <main className="results-layout" id="results">
        <section className="list-panel">
          <div className="results-toolbar" aria-busy={isRefreshingListings}>
            <div className="results-copy">
              <span className="results-kicker">{activeCategory === "Depas" ? "Alquiler mensual" : activeCategory === "Airbnb" ? "Estadías por noche" : activeCategory === "Transporte" ? "Servicios afiliados" : "Contacto directo"}</span>
              <h1>{resultsTitle}</h1>
              <p aria-live="polite">
                {isInitialListingsLoad ? "Buscando las mejores opciones…" : `${resultsTotal} ${resultsTotal === 1 ? singularNoun[activeCategory] : detail.noun} ${resultsTotal === 1 ? "disponible" : "disponibles"} · Sin comisiones extras`}
                {isRefreshingListings && <span className="refreshing-label"><i />Actualizando</span>}
              </p>
            </div>
            <div className="results-actions">
              <label className="sort-control"><span>Ordenar por</span><select value={sort} onChange={(event) => setSort(event.target.value as ListingSort)} aria-label="Ordenar resultados">{sortOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
              <button className={`toolbar-filter ${activeCategory === "Roomies" ? "mobile-only-filter" : ""}`} onClick={() => activeCategory === "Depas" ? openDepaFilters() : openFiltersModal()} aria-label={`Abrir filtros${filterButtonCount ? `, ${filterButtonCount} activos` : ""}`}><FilterIcon /><span>Filtros</span>{filterButtonCount > 0 && <b>{filterButtonCount}</b>}</button>
            </div>
          </div>

          {activeFilterChips.length > 0 && <div className="active-filter-chips" aria-label="Filtros activos">{activeFilterChips.map((chip) => <button key={chip.key} onClick={chip.clear}>{chip.label}<span aria-hidden="true">×</span><span className="sr-only">Quitar filtro</span></button>)}<button className="clear-all-chip" onClick={resetFilters}>Limpiar todo</button></div>}

          {listingsStatus === "error" && <div className="results-error" role="alert"><div><strong>No pudimos actualizar los anuncios</strong><span>{listingsError}. Puedes seguir viendo las opciones disponibles.</span></div><button onClick={() => setRetryListings((value) => value + 1)}>Reintentar</button></div>}

          {isInitialListingsLoad ? (
            <div className={`listing-grid ${activeCategory === "Depas" ? "depa-listing-grid" : ""}`} aria-label="Cargando anuncios">{Array.from({ length: activeCategory === "Depas" ? 6 : 4 }, (_, index) => <ListingSkeleton key={index} />)}</div>
          ) : visibleListings.length > 0 ? (
            <div className={`listing-grid ${activeCategory === "Depas" ? "depa-listing-grid" : ""}`}>
              {visibleListings.map((listing, listingIndex) => {
                const images = listingImages(listing);
                const imageIndex = Math.min(galleryIndexes[listing.id] ?? 0, images.length - 1);
                return (
                <article key={listing.id} className={`listing-card ${activeCategory === "Depas" ? "depa-card" : ""}`} onClick={() => openListing(listing)}>
                  <div className="listing-image-wrap">
                    {images.length > 1 ? (
                      <SwipeGallery
                        index={imageIndex}
                        count={images.length}
                        onIndexChange={(index) => setGalleryIndexes((current) => (current[listing.id] === index ? current : { ...current, [listing.id]: index }))}
                        label={`Fotografías de ${listing.title}`}
                      >
                        {images.map((image, index) => (
                          <img
                            key={`${listing.id}-slide-${index}`}
                            src={imageUrl(image, 900)}
                            srcSet={`${imageUrl(image, 480)} 480w, ${imageUrl(image, 900)} 900w, ${imageUrl(image, 1200)} 1200w`}
                            sizes={activeCategory === "Depas" ? "(max-width: 700px) 92vw, (max-width: 1050px) 46vw, 31vw" : "(max-width: 700px) 92vw, (max-width: 1050px) 46vw, 24vw"}
                            alt={`${listing.title}, fotografía ${index + 1}`}
                            className="listing-image"
                            loading={listingIndex < 4 && index === 0 ? "eager" : "lazy"}
                            decoding="async"
                            fetchPriority={listingIndex < 2 && index === 0 ? "high" : "auto"}
                            draggable={false}
                          />
                        ))}
                      </SwipeGallery>
                    ) : (
                      <img
                        src={imageUrl(images[0] ?? listing.image, 900)}
                        srcSet={`${imageUrl(images[0] ?? listing.image, 480)} 480w, ${imageUrl(images[0] ?? listing.image, 900)} 900w, ${imageUrl(images[0] ?? listing.image, 1200)} 1200w`}
                        sizes={activeCategory === "Depas" ? "(max-width: 700px) 92vw, (max-width: 1050px) 46vw, 31vw" : "(max-width: 700px) 92vw, (max-width: 1050px) 46vw, 24vw"}
                        alt={`${listing.title}, fotografía 1`}
                        className="listing-image"
                        loading={listingIndex < 4 ? "eager" : "lazy"}
                        decoding="async"
                        fetchPriority={listingIndex < 2 ? "high" : "auto"}
                        draggable={false}
                      />
                    )}
                    {listing.badge && <span className="listing-badge">{listing.badge}</span>}
                    <button disabled={favoriteMutations.includes(listing.id)} className={`favorite-button ${favorites.includes(listing.id) ? "is-favorite" : ""}`} onClick={(event) => { event.stopPropagation(); toggleFavorite(listing.id); }} aria-label={favorites.includes(listing.id) ? "Quitar de favoritos" : "Guardar en favoritos"} aria-pressed={favorites.includes(listing.id)}>{favoriteMutations.includes(listing.id) ? "…" : favorites.includes(listing.id) ? "♥" : "♡"}</button>
                    <button className="carousel-arrow previous" disabled={images.length < 2 || imageIndex === 0} onClick={(event) => { event.stopPropagation(); moveGallery(listing, -1); }} aria-label={`Fotografía anterior de ${listing.title}`}>‹</button>
                    <button className="carousel-arrow" disabled={images.length < 2 || imageIndex >= images.length - 1} onClick={(event) => { event.stopPropagation(); moveGallery(listing, 1); }} aria-label={`Siguiente fotografía de ${listing.title}`}>›</button>
                    {images.length > 1 && <div className="image-dots" aria-label={`Fotografía ${imageIndex + 1} de ${images.length}`}>
                      {images.map((_, index) => <button key={`${listing.id}-${index}`} className={index === imageIndex ? "active" : ""} onClick={(event) => { event.stopPropagation(); setGalleryIndexes((current) => ({ ...current, [listing.id]: index })); }} aria-label={`Ver fotografía ${index + 1}`} aria-current={index === imageIndex ? "true" : undefined} />)}
                    </div>}
                  </div>
                  {activeCategory === "Depas" ? (() => {
                    const details = depaDetails(listing);
                    return <div className="listing-copy depa-copy">
                      <div className="depa-title-row"><h2><button className="card-title-link" onClick={(event) => { event.stopPropagation(); openListing(listing); }}>{listing.title}</button></h2><span>★ {listing.rating.toFixed(2).replace(/0$/, "")} <small>({listing.reviews})</small></span></div>
                      <p className="depa-status"><strong>{details.delivery}</strong><span>·</span>{details.availability}</p>
                      <p className="depa-rent"><span>Alquiler desde</span><strong>{money.format(listing.price)}</strong></p>
                      <p className="depa-address">{details.address}</p>
                      <div className="depa-specs" aria-label="Resumen del departamento">
                        <span>{details.units} {details.units === 1 ? "unidad" : "unidades"}</span>
                        <span>{details.areaTotal}</span>
                        <span>{details.areaCovered}</span>
                        <span>{rangeLabel(details.bedroomsMin, details.bedroomsMax, "dorm.", "dorm.")}</span>
                        <span>{rangeLabel(details.bathroomsMin, details.bathroomsMax, "baño", "baños")}</span>
                      </div>
                      <div className="depa-card-footer">
                        <div className="depa-feature-preview">{details.features.slice(0, 3).map((feature) => <span key={feature}>{feature}</span>)}</div>
                        <a className="whatsapp-card" href={whatsappLink(listing)} onClick={(event) => { event.stopPropagation(); trackInquiry(listing.id); }} target="_blank" rel="noreferrer" aria-label={`Contactar a ${listing.ownerName} por WhatsApp`} title={`Chatear con ${listing.ownerName} en WhatsApp`}><WhatsappIcon /><span>WhatsApp</span></a>
                      </div>
                    </div>;
                  })() : <div className="listing-copy">
                      <div className="card-title-row"><h2><button className="card-title-link" onClick={(event) => { event.stopPropagation(); openListing(listing); }}>{listing.title}</button></h2><span>★ {listing.rating.toFixed(2).replace(/0$/, "")} <small>({listing.reviews})</small></span></div>
                      <p className="listing-location">{listing.location}</p>
                      <p className="listing-meta">{listing.meta}</p>
                      <p className="listing-dates">{dateLabel}</p>
                      <div className="price-row">
                        <div><p><strong>{money.format(listing.price)}</strong> <span>{listing.priceLabel}</span></p><span className="cancellation-tag">Contacto directo</span></div>
                        <a className="whatsapp-card" href={whatsappLink(listing)} onClick={(event) => { event.stopPropagation(); trackInquiry(listing.id); }} target="_blank" rel="noreferrer" aria-label={`Contactar a ${listing.ownerName} por WhatsApp`} title={`Chatear con ${listing.ownerName} en WhatsApp`}><WhatsappIcon /><span>WhatsApp</span></a>
                      </div>
                    </div>}
                </article>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">
              <span className="empty-icon"><Icon>⌂</Icon></span>
              <h2>No encontramos opciones con esos filtros</h2>
              <p>Prueba otra ubicación o amplía tu presupuesto.</p>
              <button className="dark-button" onClick={resetFilters}>Limpiar filtros</button>
            </div>
          )}

          {hasDatabaseCategory && listingsMeta?.hasMore && visibleListings.length > 0 && (
            <div className="load-more-row">
              <button className="dark-button" disabled={isLoadingMore} onClick={loadMoreListings}>{isLoadingMore ? "Cargando…" : "Ver más anuncios"}</button>
            </div>
          )}

        </section>
      </main>

      <footer className="footer">
        <div className="footer-top">
          <div><strong>Asistencia</strong><button onClick={() => flashNotice(`Soporte: ${SUPPORT_EMAIL}`)}>Centro de ayuda</button><button onClick={() => flashNotice("Próximamente: seguridad y confianza")}>Seguridad</button></div>
          <div className="footer-publish-card">
            <strong>Publica</strong>
            <button className="footer-publish-primary" onClick={requestPublish}>Anuncia tu espacio</button>
            <button className="footer-publish-secondary" onClick={openPlans}>Planes anuales</button>
          </div>
          <div><strong>{BRAND}</strong><button onClick={() => flashNotice(`Muy pronto: conoce al equipo ${BRAND}`)}>Quiénes somos</button><button onClick={() => flashNotice(`Soporte: ${SUPPORT_EMAIL}`)}>Contacto</button></div>
        </div>
        <div className="footer-bottom"><span>© 2026 {BRAND} · llaves365.com · Privacidad · Términos</span><span>Español (PE) · S/ PEN</span></div>
      </footer>

      <div className={`toast ${notice ? "visible" : ""} ${noticeTone === "error" ? "error" : ""}`} role={noticeTone === "error" ? "alert" : "status"} aria-live={noticeTone === "error" ? "assertive" : "polite"} aria-atomic="true"><span>{noticeTone === "error" ? "!" : "✓"}</span>{notice}</div>

      {showFilters && (
        <Modal onClose={() => setShowFilters(false)} className="filters-modal">
          <div className="modal-header"><div><span className="modal-kicker">Personaliza tu búsqueda</span><h2>Filtros</h2></div><button className="close-button" onClick={() => setShowFilters(false)} aria-label="Cerrar filtros">×</button></div>
          <div className="filter-section"><h3>Ubicación</h3><input className="full-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Distrito o ciudad" /></div>
          {activeCategory === "Depas" ? <DepaFilterControls
            bedrooms={bedrooms}
            minimumPrice={minPrice}
            maximumPrice={maxPrice}
            features={selectedDepaFeatures}
            onBedroomsChange={setBedrooms}
            onMinimumPriceChange={setMinPrice}
            onMaximumPriceChange={setMaxPrice}
            onToggleFeature={toggleDepaFeature}
          /> : <div className="filter-section"><h3>Presupuesto máximo</h3><div className="price-input"><span>S/</span><input type="number" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} placeholder="Sin límite" /></div></div>}
          {activeCategory === "Transporte" && <div className="filter-section"><h3>Tipo de servicio</h3><div className="modal-options">{["Todos", "Mudanza", "Corporativo"].map((item) => <button key={item} className={service === item ? "selected" : ""} onClick={() => setService(item)}>{item}</button>)}</div></div>}
          <div className="modal-footer"><button className="text-action" onClick={resetFilters}>Limpiar todo</button><button className="dark-button" onClick={() => setShowFilters(false)}>Mostrar {visibleListings.length} resultados</button></div>
        </Modal>
      )}

      {showPlans && (
        <Modal onClose={() => setShowPlans(false)} className="plans-modal">
          <div className="modal-header"><div><span className="modal-kicker">Anuncia en {BRAND}</span><h2>Un pago anual. Cero comisiones extras.</h2></div><button className="close-button" onClick={() => setShowPlans(false)} aria-label="Cerrar planes">×</button></div>
          <p className="modal-lead">Nosotros llevamos tráfico a la plataforma y cada consulta llega directamente a ti.</p>
          <div className="plans-list">{plans.map((plan) => <button key={plan.name} onClick={() => { setShowPlans(false); requestPublish(); }}><span className="plan-icon"><Icon>{plan.icon}</Icon></span><span><strong>{plan.name}</strong><small>{plan.detail}</small></span><b>{plan.price}</b><Icon>›</Icon></button>)}</div>
          <div className="benefits"><span>✓ 12 meses publicado</span><span>✓ Contacto directo</span><span>✓ Sin comisión por reserva</span></div>
        </Modal>
      )}

      {showLogin && (
        <AuthModal
          user={currentUser}
          onClose={() => { setShowLogin(false); setPublishAfterLogin(false); }}
          onAuthenticated={authenticated}
          onLoggedOut={loggedOut}
          onOpenAdmin={() => { setShowLogin(false); setShowAdminPanel(true); }}
          onOpenMyListings={() => { setShowLogin(false); setShowMyListings(true); }}
        />
      )}

      {showAdminPanel && currentUser?.role === "admin" && (
        <AdminPanelModal onClose={() => setShowAdminPanel(false)} onListingsChanged={refreshListings} notify={flashNotice} />
      )}

      {showMyListings && currentUser && (
        <Modal onClose={() => setShowMyListings(false)} className="admin-modal">
          <div className="modal-header"><div><span className="modal-kicker">Tu espacio en {BRAND}</span><h2>Mis anuncios</h2></div><button className="close-button" onClick={() => setShowMyListings(false)} aria-label="Cerrar mis anuncios">×</button></div>
          <ListingManager mode="mine" onChanged={refreshListings} notify={flashNotice} />
        </Modal>
      )}

      {showFavorites && (
        <Modal onClose={() => setShowFavorites(false)} className="favorites-modal">
          <div className="modal-header"><div><span className="modal-kicker">Tus guardados en {BRAND}</span><h2>Mis favoritos</h2></div><button className="close-button" onClick={() => setShowFavorites(false)} aria-label="Cerrar mis favoritos">×</button></div>
          {favorites.length === 0 ? (
            <div className="favorites-empty">
              <span className="favorites-empty-heart" aria-hidden="true">♡</span>
              <p>Todavía no guardaste favoritos. Toca el corazón en un anuncio para guardarlo.</p>
            </div>
          ) : (
            <>
              {favoritesStatus === "error" && (
                <div className="results-error" role="alert">
                  <div><strong>No pudimos cargar algunos favoritos</strong><span>Revisa tu conexión e inténtalo otra vez.</span></div>
                  <button onClick={() => setFavoritesRetry((value) => value + 1)}>Reintentar</button>
                </div>
              )}
              {favoritesStatus === "loading" && favoriteListings.length < favorites.length && <p className="favorites-loading" aria-live="polite">Cargando tus favoritos…</p>}
              <div className="favorites-list">
                {favoriteListings.map((listing) => (
                  <article key={listing.id} className="favorite-row" onClick={() => openListing(listing)}>
                    <img src={imageUrl(listingImages(listing)[0] ?? listing.image, 480)} alt={`${listing.title}, fotografía`} loading="lazy" decoding="async" />
                    <div className="favorite-copy">
                      <h3><button className="card-title-link" onClick={(event) => { event.stopPropagation(); openListing(listing); }}>{listing.title}</button></h3>
                      <span className="favorite-location">{listing.location}</span>
                      <p className="favorite-price"><strong>{money.format(listing.price)}</strong> <em>{listing.priceLabel}</em></p>
                    </div>
                    <div className="favorite-actions">
                      <a className="whatsapp-card" href={whatsappLink(listing)} onClick={(event) => { event.stopPropagation(); trackInquiry(listing.id); }} target="_blank" rel="noreferrer" aria-label={`Contactar a ${listing.ownerName} por WhatsApp`} title={`Chatear con ${listing.ownerName} en WhatsApp`}><WhatsappIcon /><span>WhatsApp</span></a>
                      <button className="favorite-remove" disabled={favoriteMutations.includes(listing.id)} onClick={(event) => { event.stopPropagation(); toggleFavorite(listing.id); }} aria-label={`Quitar ${listing.title} de favoritos`}>{favoriteMutations.includes(listing.id) ? "…" : "♥"}</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
          {!currentUser && favorites.length > 0 && (
            <p className="favorites-guest-note"><span className="google-nudge-icon" aria-hidden="true"><GoogleGIcon /></span>Entra con Google para no perderlos en otro teléfono.</p>
          )}
        </Modal>
      )}

      {showPublish && currentUser && <PublishModal category={activeCategory} defaultOwnerName={currentUser.name} onClose={() => setShowPublish(false)} onCreated={(listing) => { setListingsFromDb((current) => [listing, ...current]); setActiveCategory(listing.category); setRetryListings((value) => value + 1); setShowPublish(false); flashNotice("Tu publicación fue guardada"); }} />}

      {selectedListing && (
        <Modal onClose={() => setSelectedListing(null)} className="detail-modal">
          <button className="close-button detail-close" onClick={() => setSelectedListing(null)} aria-label="Cerrar detalle">×</button>
          <div className="detail-image">
            {selectedGallery.length > 1 ? (
              <SwipeGallery
                className="detail-swipe-gallery"
                index={safeSelectedImageIndex}
                count={selectedGallery.length}
                onIndexChange={setSelectedImageIndex}
                label={`Fotografías de ${selectedListing.title}`}
              >
                {selectedGallery.map((image, index) => (
                  <img key={`${selectedListing.id}-detail-slide-${index}`} src={imageUrl(image, 1200)} alt={`${selectedListing.title}, fotografía ${index + 1}`} loading={index === 0 ? "eager" : "lazy"} decoding="async" draggable={false} />
                ))}
              </SwipeGallery>
            ) : (
              <img src={imageUrl(selectedGallery[0] ?? selectedListing.image, 1200)} alt={`${selectedListing.title}, fotografía 1`} draggable={false} />
            )}
            {selectedListing.badge && <span>{selectedListing.badge}</span>}
            {selectedGallery.length > 1 && <>
              <button className="detail-gallery-arrow previous" disabled={safeSelectedImageIndex === 0} onClick={() => setSelectedImageIndex((current) => Math.max(0, current - 1))} aria-label="Fotografía anterior">‹</button>
              <button className="detail-gallery-arrow next" disabled={safeSelectedImageIndex >= selectedGallery.length - 1} onClick={() => setSelectedImageIndex((current) => Math.min(selectedGallery.length - 1, current + 1))} aria-label="Siguiente fotografía">›</button>
              <span className="detail-image-count">{safeSelectedImageIndex + 1} / {selectedGallery.length}</span>
              <div className="detail-thumbnails" aria-label="Seleccionar fotografía">
                {selectedGallery.map((image, index) => <button key={`${selectedListing.id}-detail-${index}`} className={index === safeSelectedImageIndex ? "active" : ""} onClick={() => setSelectedImageIndex(index)} aria-label={`Ver fotografía ${index + 1}`} aria-current={index === safeSelectedImageIndex ? "true" : undefined}><img src={imageUrl(image, 180)} alt="" /></button>)}
              </div>
            </>}
          </div>
          <div className="detail-body">
            <div className="detail-title"><div><span className="modal-kicker">{selectedListing.category}</span><h2>{selectedListing.title}</h2></div><strong>★ {selectedListing.rating.toFixed(1)} ({selectedListing.reviews})</strong></div>
            <p className="detail-location">{selectedListing.category === "Depas" ? depaDetails(selectedListing).address : selectedListing.location}</p>
            <p className="detail-description">{selectedListing.description}</p>
            {selectedListing.category === "Depas" && (() => {
              const details = depaDetails(selectedListing);
              return <><div className="detail-depa-status"><strong>{details.delivery}</strong><span>· {details.availability}</span></div><div className="detail-depa-specs"><span><strong>{details.units}</strong><small>unidades</small></span><span><strong>{details.areaTotal}</strong><small>área total</small></span><span><strong>{details.areaCovered}</strong><small>área techada</small></span><span><strong>{rangeLabel(details.bedroomsMin, details.bedroomsMax, "dorm.", "dorm.")}</strong><small>dormitorios</small></span><span><strong>{rangeLabel(details.bathroomsMin, details.bathroomsMax, "baño", "baños")}</strong><small>baños</small></span></div><div className="detail-depa-features">{details.features.map((feature) => <span key={feature}>✓ {feature}</span>)}</div></>;
            })()}
            {selectedListing.category === "Airbnb" && <div className="detail-stay-panel">
              <div className="detail-stay-dates">
                <span><small>Llegada</small><strong>{formatDetailDate(checkIn)}</strong></span>
                <span><small>Salida</small><strong>{formatDetailDate(checkOut)}</strong></span>
              </div>
              <div className="detail-stay-guests"><span><small>Huéspedes</small><strong>{guestCount} {guestCount === 1 ? "huésped" : "huéspedes"}</strong></span><span>{airbnbNights} {airbnbNights === 1 ? "noche" : "noches"}</span></div>
              <div className="detail-stay-total"><span>{money.format(selectedListing.price)} × {airbnbNights} {airbnbNights === 1 ? "noche" : "noches"}</span><strong>{money.format(selectedListing.price * airbnbNights)}</strong></div>
            </div>}
            <div className="detail-benefits"><span>✓ Contacto directo con quien publica</span><span>✓ Coordinas por WhatsApp</span><span>✓ Sin comisiones</span></div>
            <div className="detail-footer"><div><small>{selectedListing.category === "Depas" ? "Alquiler desde" : selectedListing.category === "Airbnb" ? `Total por ${airbnbNights} ${airbnbNights === 1 ? "noche" : "noches"}` : "Precio"}</small><strong>{selectedListing.category === "Airbnb" ? money.format(selectedListing.price * airbnbNights) : money.format(selectedListing.price)} {selectedListing.category !== "Airbnb" && <em>{selectedListing.priceLabel}</em>}</strong></div><a className="primary-button" href={whatsappLink(selectedListing, { checkIn, checkOut, guests: guestCount })} onClick={() => trackInquiry(selectedListing.id)} target="_blank" rel="noreferrer">{selectedListing.category === "Airbnb" ? "Consultar disponibilidad" : "Contactar por WhatsApp"} <Icon>↗</Icon></a></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Modal({ children, onClose, className = "" }: { children: React.ReactNode; onClose: () => void; className?: string }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);

  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => {
      const firstFocusable = dialogRef.current?.querySelector<HTMLElement>("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])");
      (firstFocusable ?? dialogRef.current)?.focus();
    });

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"));
      if (!focusable.length) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeRef.current(); }}><div ref={dialogRef} className={`modal ${className}`} role="dialog" aria-modal="true" aria-label={`Ventana de ${BRAND}`} tabIndex={-1}>{children}</div></div>;
}

function AuthModal({ user, onClose, onAuthenticated, onLoggedOut, onOpenAdmin, onOpenMyListings }: { user: AuthUser | null; onClose: () => void; onAuthenticated: (user: AuthUser) => void; onLoggedOut: () => void; onOpenAdmin: () => void; onOpenMyListings: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [showPasswordAccess, setShowPasswordAccess] = useState(false);
  const [googleStatus, setGoogleStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [googleMessage, setGoogleMessage] = useState("");
  const [googleRetry, setGoogleRetry] = useState(0);
  const [googleFlowEnabled, setGoogleFlowEnabled] = useState(true);
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const authenticatedRef = useRef(onAuthenticated);

  useEffect(() => {
    authenticatedRef.current = onAuthenticated;
  }, [onAuthenticated]);

  useEffect(() => {
    if (user) return;
    let cancelled = false;
    let renderCheckTimeout: number | undefined;

    async function configureGoogle() {
      try {
        const response = await fetch("/api/auth/config");
        const config = (await response.json()) as { googleEnabled?: boolean; googleClientId?: string };
        if (!response.ok || !config.googleEnabled || !config.googleClientId) {
          if (!cancelled) setGoogleFlowEnabled(false);
          throw new Error("El acceso con Google está terminando de configurarse. Vuelve a intentarlo en unos minutos.");
        }
        if (!cancelled) setGoogleFlowEnabled(true);
        await loadGoogleIdentityScript();
        if (cancelled || !googleButtonRef.current || !window.google?.accounts.id) return;
        const authenticateWithGoogle = async (credential: string) => {
          setIsSaving(true);
          setError("");
          try {
            const authResponse = await fetch("/api/auth/google", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ credential }),
            });
            const authPayload = (await authResponse.json()) as { user?: AuthUser; error?: string };
            if (!authResponse.ok || !authPayload.user) throw new Error(authPayload.error ?? "No se pudo iniciar sesión con Google");
            authenticatedRef.current(authPayload.user);
          } catch (googleError) {
            setError(googleError instanceof Error ? googleError.message : "No pudimos validar tu cuenta de Google.");
          } finally {
            setIsSaving(false);
          }
        };
        googleButtonRef.current.replaceChildren();
        window.google.accounts.id.initialize({
          client_id: config.googleClientId,
          callback: (credentialResponse) => {
            void authenticateWithGoogle(credentialResponse.credential);
          },
          auto_select: false,
          cancel_on_tap_outside: false,
          // Mantiene el flujo del botón funcionando en Safari (ITP) y en los
          // Chrome recientes que ya bloquean cookies de terceros (FedCM).
          itp_support: true,
          use_fedcm_for_prompt: true,
        });
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "rectangular",
          text: "continue_with",
          logo_alignment: "left",
          // Botón oficial a todo el ancho del modal (Google admite hasta 400 px).
          width: Math.max(200, Math.min(400, Math.floor(googleButtonRef.current.getBoundingClientRect().width))),
          locale: "es",
        });
        if (cancelled) return;
        setGoogleStatus("ready");
        // Si Google rechaza el origen (falta autorizar el dominio en Google
        // Cloud Console) o el navegador bloquea el iframe del botón, este
        // nunca aparece: avisamos en claro y dejamos activo el acceso por
        // redirección de "Continuar con Google".
        renderCheckTimeout = window.setTimeout(() => {
          if (cancelled) return;
          const officialButton = googleButtonRef.current?.querySelector("iframe");
          // Un iframe colapsado (sin tamaño) equivale a que no cargó.
          if (!officialButton || officialButton.clientWidth < 40 || officialButton.clientHeight < 20) {
            setGoogleStatus("unavailable");
            setGoogleMessage(
              "El botón oficial de Google no cargó en este navegador. Toca «Continuar con Google» para entrar desde la página segura de Google, o vuelve a intentarlo.",
            );
          }
        }, 3000);
      } catch (setupError) {
        if (!cancelled) {
          setGoogleStatus("unavailable");
          setGoogleMessage(setupError instanceof Error ? setupError.message : "Google no está disponible.");
        }
      }
    }

    void configureGoogle();
    return () => {
      cancelled = true;
      if (renderCheckTimeout !== undefined) window.clearTimeout(renderCheckTimeout);
    };
  }, [user, googleRetry]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/auth/${mode === "login" ? "login" : "register"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const payload = (await response.json()) as { user?: AuthUser; error?: string };
      if (!response.ok || !payload.user) throw new Error(payload.error ?? "No se pudo iniciar sesión");
      onAuthenticated(payload.user);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Revisa tus datos e intenta otra vez.");
    } finally {
      setIsSaving(false);
    }
  }

  async function logout() {
    setIsSaving(true);
    setError("");
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error("No se pudo cerrar la sesión");
      window.google?.accounts.id.disableAutoSelect();
      onLoggedOut();
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : "Inténtalo nuevamente.");
      setIsSaving(false);
    }
  }

  return (
    <Modal onClose={onClose} className="login-modal">
      <button className="close-button login-close" onClick={onClose} aria-label="Cerrar inicio de sesión">×</button>
      {user?.avatarUrl
        ? <img className="account-avatar" src={user.avatarUrl} alt="" referrerPolicy="no-referrer" />
        : <span className="login-logo"><Icon>⌂</Icon></span>}
      <span className="modal-kicker">{user?.role === "admin" ? "Cuenta administradora" : `Tu cuenta ${BRAND}`}</span>
      {user ? (
        <div className="account-summary">
          <h2>Hola, {user.name}</h2>
          <p>Tu sesión está activa y ya puedes publicar anuncios con tu cuenta.</p>
          <span>{user.email}{user.role === "admin" && <b>Administrador</b>}</span>
          {error && <p className="form-error">{error}</p>}
          {user.role === "admin" && <button className="primary-button account-button" onClick={onOpenAdmin}>Panel de administración <Icon>→</Icon></button>}
          <button className={`${user.role === "admin" ? "dark-button" : "primary-button"} account-button`} onClick={onOpenMyListings}>Mis anuncios <Icon>→</Icon></button>
          <button className="text-action account-logout" disabled={isSaving} onClick={logout}>{isSaving ? "Cerrando…" : "Cerrar sesión"}</button>
        </div>
      ) : (
        <>
          <h2>Inicia sesión con Google</h2>
          <p>Usa tu cuenta de Google para guardar favoritos, publicar anuncios y gestionar tus consultas de forma segura.</p>
          <div className={`google-auth-panel ${isSaving ? "busy" : ""}`}>
            <div className="google-cta">
              {/* Botón propio a todo el ancho: si el iframe oficial de Google
                  se muestra encima, el toque llega a Google Identity Services;
                  si el iframe no carga, este botón inicia sesión con Google
                  mediante la redirección OAuth (/api/auth/google/start). */}
              <button
                type="button"
                className="google-cta-button"
                disabled={!googleFlowEnabled || isSaving}
                onClick={() => window.location.assign("/api/auth/google/start")}
              >
                <GoogleGIcon />
                <span>Continuar con Google</span>
              </button>
              <div ref={googleButtonRef} className="google-button-target" aria-label="Continuar con Google" />
            </div>
            {googleStatus === "unavailable" && (
              <>
                <span className="google-unavailable" role="alert">{googleMessage}</span>
                <button
                  type="button"
                  className="google-retry"
                  onClick={() => {
                    setGoogleStatus("loading");
                    setGoogleMessage("");
                    setGoogleRetry((attempt) => attempt + 1);
                  }}
                >
                  Reintentar el botón de Google
                </button>
              </>
            )}
            <small>Google confirma tu identidad; {BRAND} crea una sesión segura en este dispositivo.</small>
          </div>
          {error && <p className="form-error auth-error">{error}</p>}
          <div className="auth-divider"><span>o</span></div>
          <button className="email-access-toggle" onClick={() => { setShowPasswordAccess((current) => !current); setError(""); }} aria-expanded={showPasswordAccess}>
            {showPasswordAccess ? "Ocultar acceso con correo" : "Usar correo y contraseña"}<Icon>{showPasswordAccess ? "⌃" : "⌄"}</Icon>
          </button>
          {showPasswordAccess && <div className="password-access">
            <div className="auth-switch" role="group" aria-label="Tipo de acceso">
              <button className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>Ingresar</button>
              <button className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(""); }}>Crear cuenta</button>
            </div>
            <form className="auth-form" onSubmit={submit}>
              {mode === "register" && <label>Nombre<input required minLength={2} maxLength={80} autoComplete="name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Tu nombre" /></label>}
              <label>Correo electrónico<input required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="tu@correo.com" /></label>
              <label>Contraseña<input required minLength={8} maxLength={128} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="Mínimo 8 caracteres" /></label>
              <button className="primary-button wide" disabled={isSaving}>{isSaving ? "Procesando…" : mode === "login" ? "Iniciar sesión" : "Crear mi cuenta"}<Icon>→</Icon></button>
            </form>
          </div>}
          <small>Al continuar aceptas nuestros términos de uso y política de privacidad.</small>
        </>
      )}
    </Modal>
  );
}

async function uploadPublishPhotos(files: File[]): Promise<string[]> {
  // Una sola petición con todas las fotos: el servidor las redimensiona y
  // devuelve las URLs en orden.
  const multiData = new FormData();
  for (const file of files) multiData.append("files", file);
  const multiResponse = await fetch("/api/uploads", { method: "POST", body: multiData });
  const multiPayload = (await multiResponse.json().catch(() => ({}))) as { url?: string; urls?: string[]; error?: string };
  if (multiResponse.ok) {
    if (multiPayload.urls?.length) return multiPayload.urls;
    if (multiPayload.url) return [multiPayload.url];
  }
  if (files.length === 1 || [400, 401, 429].includes(multiResponse.status)) {
    throw new Error(multiPayload.error ?? "No se pudieron subir las fotos");
  }
  // Si un proxy limita el tamaño de la petición conjunta, se suben una por una.
  const urls: string[] = [];
  for (const file of files) {
    const data = new FormData();
    data.append("file", file);
    const response = await fetch("/api/uploads", { method: "POST", body: data });
    const payload = (await response.json().catch(() => ({}))) as { url?: string; error?: string };
    if (!response.ok || !payload.url) throw new Error(payload.error ?? "No se pudo subir una de las fotos");
    urls.push(payload.url);
  }
  return urls;
}

function PublishModal({ category, defaultOwnerName, onClose, onCreated }: { category: Category; defaultOwnerName: string; onClose: () => void; onCreated: (listing: Listing) => void }) {
  const [activeCategory, setActiveCategory] = useState<Category>(category);
  const [form, setForm] = useState({ title: "", location: "", price: "", description: "", ownerName: defaultOwnerName, ownerWhatsApp: "" });
  const [roomieForm, setRoomieForm] = useState({ bathroom: "Compartido", bed: "1 plaza", furnished: "Sí", services: "Sí" });
  const [stayForm, setStayForm] = useState({ guests: "2", bedrooms: "1", beds: "1", bathrooms: "1" });
  const [stayAmenities, setStayAmenities] = useState<StayAmenity[]>([]);
  const [transportService, setTransportService] = useState("Mudanza");
  const [transportForm, setTransportForm] = useState({ vehicle: "", capacity: "", coverage: "" });
  const [depaForm, setDepaForm] = useState({ address: "", units: "1", areaTotal: "", areaCovered: "", bedroomsMin: "1", bedroomsMax: "1", bathroomsMin: "1", bathroomsMax: "1", delivery: "Disponible ahora", availability: "Contrato de 6 a 12 meses" });
  const [depaPublishFeatures, setDepaPublishFeatures] = useState<DepaFeature[]>([]);
  const [photos, setPhotos] = useState<PublishPhoto[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [publishStep, setPublishStep] = useState<"photos" | "listing" | null>(null);
  const [error, setError] = useState("");
  const photoIdRef = useRef(0);
  const photosRef = useRef<PublishPhoto[]>([]);
  const copy = publishCopy[activeCategory];
  const validPhotos = photos.filter((photo) => !photo.error);

  useEffect(() => {
    photosRef.current = photos;
  }, [photos]);

  useEffect(() => () => {
    for (const photo of photosRef.current) URL.revokeObjectURL(photo.preview);
  }, []);

  function addPhotos(files: FileList | null) {
    if (!files?.length) return;
    let message = "";
    const accepted: PublishPhoto[] = [];
    const rejected: PublishPhoto[] = [];
    let total = photos.length;
    for (const file of Array.from(files)) {
      if (total >= MAX_PUBLISH_PHOTOS) { message = `Puedes subir máximo ${MAX_PUBLISH_PHOTOS} fotos.`; break; }
      photoIdRef.current += 1;
      const preview = URL.createObjectURL(file);
      // Una foto inválida no se descarta en silencio: su casilla se queda en
      // la cuadrícula con el motivo, y las demás fotos válidas sí entran.
      if (!PHOTO_MIME_TYPES.includes(file.type)) {
        rejected.push({ id: photoIdRef.current, file, preview, error: "Formato no válido. Usa JPG, PNG o WebP." });
      } else if (file.size > MAX_PHOTO_BYTES) {
        rejected.push({ id: photoIdRef.current, file, preview, error: "Pesa más de 12 MB. Elige una versión más ligera." });
      } else {
        accepted.push({ id: photoIdRef.current, file, preview });
      }
      total += 1;
    }
    if (accepted.length || rejected.length) {
      // Las válidas van primero (la portada siempre es una foto real) y las
      // marcadas con error quedan al final hasta que el dueño las quite.
      setPhotos((current) => [
        ...current.filter((photo) => !photo.error),
        ...accepted,
        ...current.filter((photo) => photo.error),
        ...rejected,
      ]);
    }
    setError(message);
  }

  function makeCover(id: number) {
    setPhotos((current) => {
      const index = current.findIndex((photo) => photo.id === id);
      if (index <= 0 || current[index].error) return current;
      return [current[index], ...current.slice(0, index), ...current.slice(index + 1)];
    });
  }

  function removePhoto(id: number) {
    setPhotos((current) => {
      const removed = current.find((photo) => photo.id === id);
      if (removed) URL.revokeObjectURL(removed.preview);
      return current.filter((photo) => photo.id !== id);
    });
  }

  function detailsPayload() {
    if (activeCategory === "Depas") {
      return {
        ...depaForm,
        address: depaForm.address || form.location,
        units: Number(depaForm.units),
        bedroomsMin: Number(depaForm.bedroomsMin),
        bedroomsMax: Number(depaForm.bedroomsMax),
        bathroomsMin: Number(depaForm.bathroomsMin),
        bathroomsMax: Number(depaForm.bathroomsMax),
        features: depaPublishFeatures,
      };
    }
    if (activeCategory === "Roomies") {
      return { bathroom: roomieForm.bathroom, bed: roomieForm.bed, furnished: roomieForm.furnished === "Sí", servicesIncluded: roomieForm.services === "Sí" };
    }
    if (activeCategory === "Airbnb") {
      return { guests: Number(stayForm.guests), bedrooms: Number(stayForm.bedrooms), beds: Number(stayForm.beds), bathrooms: Number(stayForm.bathrooms), amenities: stayAmenities };
    }
    return { ...transportForm };
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (validPhotos.length === 0) {
      setError(photos.length > 0
        ? "Las fotos marcadas en rojo no se pueden publicar. Quítalas y agrega al menos una foto válida."
        : "Agrega al menos una foto de tu anuncio.");
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      // Recién aquí se suben las fotos: la vista previa fue 100 % local.
      setPublishStep("photos");
      const gallery = await uploadPublishPhotos(validPhotos.map((photo) => photo.file));
      setPublishStep("listing");
      const response = await fetch("/api/listings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          category: activeCategory,
          price: Number(form.price),
          priceLabel: categoryDetails[activeCategory].priceLabel,
          image: gallery[0],
          gallery,
          service: activeCategory === "Transporte" ? transportService : undefined,
          details: detailsPayload(),
        }),
      });
      const payload = (await response.json()) as { listing?: Listing; error?: string };
      if (!response.ok || !payload.listing) throw new Error(payload.error ?? "No se pudo guardar la publicación");
      onCreated(payload.listing);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Revisa los datos e intenta otra vez.");
    } finally {
      setIsSaving(false);
      setPublishStep(null);
    }
  }

  return (
    <Modal onClose={onClose} className="publish-modal">
      <div className="modal-header"><div><span className="modal-kicker">{copy.kicker}</span><h2>Haz que te encuentren</h2></div><button className="close-button" onClick={onClose} aria-label="Cerrar publicación">×</button></div>
      <p className="modal-lead">Completa los datos esenciales. Tus clientes podrán contactarte directamente.</p>
      <div className="publish-category-switch" role="group" aria-label="Tipo de anuncio">
        {categories.map((option) => (
          <button key={option.id} type="button" className={activeCategory === option.id ? "active" : ""} aria-pressed={activeCategory === option.id} onClick={() => { setActiveCategory(option.id); setError(""); }}>{option.label}</button>
        ))}
      </div>
      <form onSubmit={submit}>
        <div className="form-grid">
          <label>Título<input required maxLength={120} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder={copy.titlePlaceholder} /></label>
          <label>Distrito / zona<input required maxLength={160} value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Ej. Miraflores, Lima" /></label>
          <label>Precio en soles · {categoryDetails[activeCategory].priceLabel}<input required min="1" max="10000000" type="number" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="450" /></label>
          <label>Tu nombre<input required maxLength={80} value={form.ownerName} onChange={(event) => setForm({ ...form, ownerName: event.target.value })} placeholder="Cómo te conocerán" /></label>
          <label>WhatsApp de contacto<input required maxLength={20} inputMode="tel" value={form.ownerWhatsApp} onChange={(event) => setForm({ ...form, ownerWhatsApp: event.target.value })} placeholder="51999888777" /></label>
        </div>
        {activeCategory === "Roomies" && <fieldset className="publish-depa-fields"><legend>Datos de la habitación</legend><div className="form-grid">
          <label>Baño<select value={roomieForm.bathroom} onChange={(event) => setRoomieForm({ ...roomieForm, bathroom: event.target.value })}><option value="Privado">Privado</option><option value="Compartido">Compartido</option></select></label>
          <label>Cama<select value={roomieForm.bed} onChange={(event) => setRoomieForm({ ...roomieForm, bed: event.target.value })}><option value="1 plaza">1 plaza</option><option value="1.5 plazas">1.5 plazas</option><option value="2 plazas">2 plazas</option></select></label>
          <label>Amoblado<select value={roomieForm.furnished} onChange={(event) => setRoomieForm({ ...roomieForm, furnished: event.target.value })}><option value="Sí">Sí</option><option value="No">No</option></select></label>
          <label>Incluye servicios (luz, agua, internet)<select value={roomieForm.services} onChange={(event) => setRoomieForm({ ...roomieForm, services: event.target.value })}><option value="Sí">Sí</option><option value="No">No</option></select></label>
        </div></fieldset>}
        {activeCategory === "Depas" && <fieldset className="publish-depa-fields"><legend>Datos del departamento</legend><div className="form-grid"><label>Dirección exacta<input required value={depaForm.address} onChange={(event) => setDepaForm({ ...depaForm, address: event.target.value })} placeholder="Av., calle y número" /></label><label>Número de unidades<input required min="1" type="number" value={depaForm.units} onChange={(event) => setDepaForm({ ...depaForm, units: event.target.value })} /></label><label>Área total<input required value={depaForm.areaTotal} onChange={(event) => setDepaForm({ ...depaForm, areaTotal: event.target.value })} placeholder="Ej. 53 a 60 m² tot." /></label><label>Área techada<input required value={depaForm.areaCovered} onChange={(event) => setDepaForm({ ...depaForm, areaCovered: event.target.value })} placeholder="Ej. 53 a 60 m² techada" /></label><label>Dormitorios mínimos<input required min="1" max="10" type="number" value={depaForm.bedroomsMin} onChange={(event) => setDepaForm({ ...depaForm, bedroomsMin: event.target.value })} /></label><label>Dormitorios máximos<input required min={depaForm.bedroomsMin || "1"} max="10" type="number" value={depaForm.bedroomsMax} onChange={(event) => setDepaForm({ ...depaForm, bedroomsMax: event.target.value })} /></label><label>Baños mínimos<input required min="1" max="10" type="number" value={depaForm.bathroomsMin} onChange={(event) => setDepaForm({ ...depaForm, bathroomsMin: event.target.value })} /></label><label>Baños máximos<input required min={depaForm.bathroomsMin || "1"} max="10" type="number" value={depaForm.bathroomsMax} onChange={(event) => setDepaForm({ ...depaForm, bathroomsMax: event.target.value })} /></label><label>Entrega<input required value={depaForm.delivery} onChange={(event) => setDepaForm({ ...depaForm, delivery: event.target.value })} /></label><label>Disponibilidad o contrato<input required value={depaForm.availability} onChange={(event) => setDepaForm({ ...depaForm, availability: event.target.value })} /></label></div><span className="publish-feature-label">Características</span><div className="publish-feature-options">{depaFeatureOptions.map((feature) => { const selected = depaPublishFeatures.includes(feature); return <button type="button" key={feature} className={selected ? "selected" : ""} aria-pressed={selected} onClick={() => setDepaPublishFeatures((current) => current.includes(feature) ? current.filter((item) => item !== feature) : [...current, feature])}>{selected ? "✓" : "+"} {feature}</button>; })}</div></fieldset>}
        {activeCategory === "Airbnb" && <fieldset className="publish-depa-fields"><legend>Datos de la estadía</legend><div className="form-grid">
          <label>Huéspedes<input required min="1" max="16" type="number" value={stayForm.guests} onChange={(event) => setStayForm({ ...stayForm, guests: event.target.value })} /></label>
          <label>Habitaciones<input required min="1" max="20" type="number" value={stayForm.bedrooms} onChange={(event) => setStayForm({ ...stayForm, bedrooms: event.target.value })} /></label>
          <label>Camas<input required min="1" max="30" type="number" value={stayForm.beds} onChange={(event) => setStayForm({ ...stayForm, beds: event.target.value })} /></label>
          <label>Baños<input required min="1" max="20" type="number" value={stayForm.bathrooms} onChange={(event) => setStayForm({ ...stayForm, bathrooms: event.target.value })} /></label>
        </div><span className="publish-feature-label">Extras</span><div className="publish-feature-options">{stayAmenityOptions.map((amenity) => { const selected = stayAmenities.includes(amenity); return <button type="button" key={amenity} className={selected ? "selected" : ""} aria-pressed={selected} onClick={() => setStayAmenities((current) => current.includes(amenity) ? current.filter((item) => item !== amenity) : [...current, amenity])}>{selected ? "✓" : "+"} {amenity}</button>; })}</div></fieldset>}
        {activeCategory === "Transporte" && <fieldset className="publish-depa-fields"><legend>Datos del servicio</legend><div className="form-grid">
          <label>Tipo de servicio<select value={transportService} onChange={(event) => setTransportService(event.target.value)}><option value="Mudanza">Mudanza</option><option value="Corporativo">Corporativo</option></select></label>
          <label>Vehículo<input required maxLength={80} value={transportForm.vehicle} onChange={(event) => setTransportForm({ ...transportForm, vehicle: event.target.value })} placeholder="Ej. Camión 3 t o SUV" /></label>
          <label>Capacidad<input required maxLength={80} value={transportForm.capacity} onChange={(event) => setTransportForm({ ...transportForm, capacity: event.target.value })} placeholder="Ej. 12 m³ o 4 pasajeros" /></label>
          <label>Zona de cobertura<input required maxLength={120} value={transportForm.coverage} onChange={(event) => setTransportForm({ ...transportForm, coverage: event.target.value })} placeholder="Ej. Lima y Callao" /></label>
        </div></fieldset>}
        <label>Descripción<small className="field-hint">{copy.helper}</small><textarea required rows={4} maxLength={2000} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder={copy.placeholder} /></label>
        <div className="photo-uploader">
          <div className="photo-uploader-head"><span className="publish-feature-label">Fotos del anuncio</span><span className="photo-counter">{validPhotos.length} / {MAX_PUBLISH_PHOTOS}</span></div>
          <div className="photo-grid">
            {photos.map((photo, index) => (
              <div key={photo.id} className={`photo-thumb ${index === 0 && !photo.error ? "cover" : ""} ${photo.error ? "has-error" : ""}`.trim()}>
                <button type="button" className="photo-cover-button" disabled={Boolean(photo.error)} onClick={() => makeCover(photo.id)} aria-label={photo.error ? `Foto ${index + 1} con error: ${photo.error}` : index === 0 ? `Foto ${index + 1}, es la portada` : `Usar la foto ${index + 1} como portada`}>
                  <img src={photo.preview} alt="" />
                  {index === 0 && !photo.error && <span className="cover-badge">Portada</span>}
                  {photo.error && <span className="photo-error" role="alert">{photo.error}</span>}
                </button>
                <button type="button" className="photo-remove" onClick={() => removePhoto(photo.id)} aria-label={`Quitar la foto ${index + 1}`}>×</button>
              </div>
            ))}
            {photos.length < MAX_PUBLISH_PHOTOS && (
              <label className="photo-add-tile">
                <input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => { addPhotos(event.target.files); event.target.value = ""; }} />
                <span><b>+</b><small>Agregar fotos</small></span>
              </label>
            )}
          </div>
          <small className="photo-hint">De 1 a {MAX_PUBLISH_PHOTOS} fotos JPG, PNG o WebP (máximo 12 MB cada una). Se muestran aquí al instante y se suben recién cuando tocas «Guardar y publicar». La primera es la portada: toca otra foto para hacerla portada.</small>
        </div>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button wide" disabled={isSaving}>{isSaving ? (publishStep === "photos" ? "Preparando fotos…" : "Publicando…") : "Guardar y publicar"}<Icon>→</Icon></button>
      </form>
    </Modal>
  );
}

function categoryLabel(id: string) {
  return categories.find((category) => category.id === id)?.label ?? id;
}

function formatAdminDate(value?: string) {
  if (!value) return "";
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function formatAdminDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(date);
}

function providerLabel(provider?: string | null) {
  return provider === "google" ? "Google" : "Correo y contraseña";
}

function usePanelData<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<PanelStatus>("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    setError("");
    fetch(url, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as T & { error?: string };
        if (!response.ok) throw new Error((payload as { error?: string }).error ?? "No se pudo cargar la información");
        return payload;
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        setData(payload);
        setStatus("ready");
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return;
        setStatus("error");
        setError(requestError instanceof Error ? requestError.message : "No se pudo cargar la información");
      });
    return () => controller.abort();
  }, [url]);

  return { data, status, error };
}

function AdminPanelModal({ onClose, onListingsChanged, notify }: { onClose: () => void; onListingsChanged: () => void; notify: (message: string, tone?: "success" | "error") => void }) {
  const [tab, setTab] = useState<"overview" | "activity" | "listings" | "inquiries" | "users">("overview");
  const tabs = [
    { id: "overview" as const, label: "Resumen" },
    { id: "activity" as const, label: "Actividad" },
    { id: "listings" as const, label: "Anuncios" },
    { id: "inquiries" as const, label: "Consultas" },
    { id: "users" as const, label: "Usuarios" },
  ];

  return (
    <Modal onClose={onClose} className="admin-modal">
      <div className="modal-header"><div><span className="modal-kicker">Administración de {BRAND}</span><h2>Panel de administración</h2></div><button className="close-button" onClick={onClose} aria-label="Cerrar panel de administración">×</button></div>
      <div className="admin-tabs" role="tablist" aria-label="Secciones del panel">
        {tabs.map((item) => <button key={item.id} role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}
      </div>
      {tab === "overview" && <AdminOverviewTab />}
      {tab === "activity" && <AdminActivityTab />}
      {tab === "listings" && <ListingManager mode="admin" onChanged={onListingsChanged} notify={notify} />}
      {tab === "inquiries" && <AdminInquiriesTab />}
      {tab === "users" && <AdminUsersTab />}
    </Modal>
  );
}

function AdminOverviewTab() {
  const { data, status, error } = usePanelData<AdminOverviewData>("/api/admin/overview");
  if (status === "loading") return <p className="panel-note">Cargando resumen…</p>;
  if (status === "error" || !data) return <p className="form-error">{error || "No se pudo cargar el resumen"}</p>;
  const { stats } = data;

  return (
    <div className="admin-section">
      <div className="stat-grid">
        <div className="stat-card"><strong>{stats.listings}</strong><span>Anuncios publicados</span></div>
        <div className="stat-card"><strong>{stats.users}</strong><span>Cuentas registradas</span></div>
        <div className="stat-card"><strong>{stats.inquiries}</strong><span>Contactos totales</span></div>
        <div className="stat-card"><strong>{stats.inquiriesLast7Days}</strong><span>Contactos · 7 días</span></div>
        <div className="stat-card"><strong>{stats.favorites}</strong><span>Favoritos guardados</span></div>
      </div>
      <h3>Anuncios por categoría</h3>
      <ul className="admin-list">
        {categories.map((category) => <li key={category.id}><span>{category.label}</span><b>{stats.byCategory[category.id] ?? 0}</b></li>)}
      </ul>
      {data.topListings.length > 0 && <>
        <h3>Anuncios más contactados</h3>
        <ul className="admin-list">
          {data.topListings.map((listing) => <li key={listing.id}><span>{listing.title} <small>· {categoryLabel(listing.category)}</small></span><b>{listing.total}</b></li>)}
        </ul>
      </>}
      {data.recentListings.length > 0 && <>
        <h3>Publicaciones recientes</h3>
        <ul className="admin-list">
          {data.recentListings.map((listing) => <li key={listing.id}><span>{listing.title} <small>· {categoryLabel(listing.category)} · {formatAdminDate(listing.createdAt)}</small></span><b>{money.format(listing.price)}</b></li>)}
        </ul>
      </>}
    </div>
  );
}

function AdminInquiriesTab() {
  const { data, status, error } = usePanelData<AdminInquiriesData>("/api/admin/inquiries");
  if (status === "loading") return <p className="panel-note">Cargando consultas…</p>;
  if (status === "error" || !data) return <p className="form-error">{error || "No se pudieron cargar las consultas"}</p>;
  if (!data.recent.length) return <p className="panel-note">Todavía no hay consultas registradas.</p>;

  return (
    <div className="admin-section">
      <h3>Anuncios con más consultas</h3>
      <ul className="admin-list">
        {data.byListing.map((row) => <li key={row.id}><span>{row.title} <small>· {categoryLabel(row.category)}</small></span><b>{row.total}</b></li>)}
      </ul>
      <h3>Últimas consultas</h3>
      <ul className="admin-list">
        {data.recent.map((row) => <li key={row.id}><span>{row.title} <small>· {row.channel === "whatsapp" ? "WhatsApp" : "Directo"}</small></span><b>{formatAdminDate(row.createdAt)}</b></li>)}
      </ul>
    </div>
  );
}

function AdminActivityTab() {
  const { data, status, error } = usePanelData<{ events: AdminActivityEvent[] }>("/api/admin/activity");
  if (status === "loading") return <p className="panel-note">Cargando actividad…</p>;
  if (status === "error" || !data) return <p className="form-error">{error || "No se pudo cargar la actividad"}</p>;
  if (!data.events.length) return <p className="panel-note">Todavía no hay actividad registrada.</p>;

  return (
    <div className="admin-section">
      <h3>Actividad reciente</h3>
      <ul className="activity-feed">
        {data.events.map((event) => (
          <li key={event.id} className={event.type === "login" ? "activity-login" : "activity-listing"}>
            <span className="activity-icon" aria-hidden="true">{event.type === "login" ? "→" : "＋"}</span>
            <div>
              {event.type === "login" ? (
                <>
                  <strong>{event.name || event.email} inició sesión</strong>
                  <small>{event.email} · {providerLabel(event.provider)}</small>
                </>
              ) : (
                <>
                  <strong>{event.name || "Alguien"} publicó “{event.title}”</strong>
                  <small>{event.email ? `${event.email} · ` : ""}{categoryLabel(event.category ?? "")}</small>
                </>
              )}
            </div>
            <time>{formatAdminDateTime(event.createdAt)}</time>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AdminUsersTab() {
  const { data, status, error } = usePanelData<{ users: AdminUserRow[]; total?: number }>("/api/admin/users");
  if (status === "loading") return <p className="panel-note">Cargando usuarios…</p>;
  if (status === "error" || !data) return <p className="form-error">{error || "No se pudieron cargar los usuarios"}</p>;
  if (!data.users.length) return <p className="panel-note">Todavía no hay cuentas registradas.</p>;

  return (
    <div className="admin-section">
      <h3>Cuentas registradas ({data.total ?? data.users.length}{(data.total ?? 0) > data.users.length ? ` · mostrando ${data.users.length}` : ""})</h3>
      <ul className="admin-list user-list">
        {data.users.map((user) => {
          const breakdown = Object.entries(user.listingsByCategory ?? {}).filter(([, total]) => total > 0);
          return (
            <li key={user.id}>
              <span>
                {user.name}{user.role === "admin" && <b className="role-chip">Admin</b>}
                <small>{user.email}</small>
                <small>
                  {user.lastLoginAt
                    ? `Último acceso ${formatAdminDateTime(user.lastLoginAt)} · ${providerLabel(user.lastLoginProvider ?? user.authProvider)}`
                    : `Sin accesos registrados · Cuenta ${user.authProvider === "google" ? "Google" : "de correo"}`}
                  {` · Registro ${formatAdminDate(user.createdAt)}`}
                </small>
                {breakdown.length > 0 && (
                  <span className="user-listing-chips">
                    {breakdown.map(([category, total]) => <i key={category}>{categoryLabel(category)} {total}</i>)}
                  </span>
                )}
              </span>
              <b>{user.listings} {user.listings === 1 ? "anuncio" : "anuncios"}</b>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ListingManager({ mode, onChanged, notify }: { mode: "admin" | "mine"; onChanged: () => void; notify: (message: string, tone?: "success" | "error") => void }) {
  const isAdmin = mode === "admin";
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [items, setItems] = useState<OwnedListing[]>([]);
  const [meta, setMeta] = useState<{ total: number; totalPages: number } | null>(null);
  const [status, setStatus] = useState<PanelStatus>("loading");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<OwnedListing | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    setError("");
    const url = isAdmin ? `/api/admin/listings?page=${page}&pageSize=8` : "/api/my/listings";
    fetch(url, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as { listings?: OwnedListing[]; meta?: { total: number; totalPages: number }; error?: string };
        if (!response.ok) throw new Error(payload.error ?? "No se pudieron cargar los anuncios");
        return payload;
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        const listings = payload.listings ?? [];
        const nextMeta = payload.meta ?? null;
        if (nextMeta && listings.length === 0 && nextMeta.total > 0 && page > nextMeta.totalPages) {
          setPage(Math.max(1, nextMeta.totalPages));
          return;
        }
        setItems(listings);
        setMeta(nextMeta);
        setStatus("ready");
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return;
        setStatus("error");
        setError(requestError instanceof Error ? requestError.message : "No se pudieron cargar los anuncios");
      });
    return () => controller.abort();
  }, [isAdmin, page, reload]);

  async function removeListing(listing: OwnedListing) {
    if (!window.confirm(`¿Eliminar “${listing.title}”? Esta acción no se puede deshacer.`)) return;
    setBusyId(listing.id);
    try {
      const response = await fetch(`/api/listings/${listing.id}`, { method: "DELETE" });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "No se pudo eliminar el anuncio");
      notify("Anuncio eliminado");
      setReload((value) => value + 1);
      onChanged();
    } catch (removeError) {
      notify(removeError instanceof Error ? removeError.message : "No se pudo eliminar el anuncio", "error");
    } finally {
      setBusyId(null);
    }
  }

  if (status === "loading" && !items.length) return <p className="panel-note">Cargando anuncios…</p>;
  if (status === "error") return <p className="form-error">{error}</p>;
  if (!items.length) return <p className="panel-note">{isAdmin ? "Todavía no hay anuncios publicados." : "Todavía no publicaste ningún anuncio. Usa “Publicar un anuncio” para crear el primero."}</p>;

  return (
    <div className="admin-section">
      {editing ? (
        <EditListingForm
          listing={editing}
          isAdmin={isAdmin}
          onCancel={() => setEditing(null)}
          onSaved={(updated) => {
            setEditing(null);
            setItems((current) => current.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
            notify("Anuncio actualizado");
            onChanged();
          }}
        />
      ) : (
        <>
          <ul className="manage-list">
            {items.map((listing) => (
              <li key={listing.id}>
                <img src={imageUrl(listing.image, 180)} alt="" loading="lazy" />
                <div>
                  <strong>{listing.title}</strong>
                  <span>{categoryLabel(listing.category)} · {money.format(listing.price)} {listing.priceLabel}</span>
                  <small>
                    {formatAdminDate(listing.createdAt)}
                    {isAdmin && listing.ownerEmail ? ` · ${listing.ownerEmail}` : ""}
                    {typeof listing.inquiries === "number" ? ` · ${listing.inquiries} ${listing.inquiries === 1 ? "contacto" : "contactos"}` : ""}
                    {typeof listing.favorites === "number" ? ` · ${listing.favorites} favoritos` : ""}
                  </small>
                </div>
                <div className="manage-actions">
                  <button className="text-action" onClick={() => setEditing(listing)}>Editar</button>
                  <button className="danger-action" disabled={busyId === listing.id} onClick={() => removeListing(listing)}>{busyId === listing.id ? "Eliminando…" : "Eliminar"}</button>
                </div>
              </li>
            ))}
          </ul>
          {isAdmin && meta && meta.totalPages > 1 && (
            <div className="manage-pagination">
              <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Anterior</button>
              <span>Página {page} de {meta.totalPages}</span>
              <button disabled={page >= meta.totalPages} onClick={() => setPage((value) => value + 1)}>Siguiente</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function EditListingForm({ listing, isAdmin, onCancel, onSaved }: { listing: OwnedListing; isAdmin: boolean; onCancel: () => void; onSaved: (listing: OwnedListing) => void }) {
  const [form, setForm] = useState({
    title: listing.title,
    location: listing.location,
    price: String(listing.price),
    description: listing.description,
    ownerWhatsApp: listing.ownerWhatsApp,
    badge: listing.badge ?? "",
  });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        title: form.title,
        location: form.location,
        price: Number(form.price),
        description: form.description,
        ownerWhatsApp: form.ownerWhatsApp,
      };
      if (isAdmin) body.badge = form.badge;
      const response = await fetch(`/api/listings/${listing.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json()) as { listing?: OwnedListing; error?: string };
      if (!response.ok || !payload.listing) throw new Error(payload.error ?? "No se pudo guardar el cambio");
      onSaved(payload.listing);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "No se pudo guardar el cambio");
      setIsSaving(false);
    }
  }

  return (
    <form className="edit-listing-form" onSubmit={submit}>
      <h3>Editar “{listing.title}”</h3>
      <div className="form-grid">
        <label>Título<input required maxLength={120} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
        <label>Ubicación<input required maxLength={160} value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} /></label>
        <label>Precio en soles<input required min="1" type="number" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} /></label>
        <label>WhatsApp de contacto<input required value={form.ownerWhatsApp} onChange={(event) => setForm({ ...form, ownerWhatsApp: event.target.value })} /></label>
        {isAdmin && <label>Insignia (visible en la tarjeta)<input maxLength={60} value={form.badge} placeholder="Ej. Verificado" onChange={(event) => setForm({ ...form, badge: event.target.value })} /></label>}
      </div>
      <label>Descripción<textarea required rows={3} maxLength={2000} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
      {error && <p className="form-error">{error}</p>}
      <div className="edit-listing-actions">
        <button type="button" className="text-action" onClick={onCancel}>Cancelar</button>
        <button className="dark-button" disabled={isSaving}>{isSaving ? "Guardando…" : "Guardar cambios"}</button>
      </div>
    </form>
  );
}
