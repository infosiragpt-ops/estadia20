/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";

import {
  demoListings,
  depaFeatureOptions,
  type Category,
  type DepaDetails,
  type DepaFeature,
  type Listing,
} from "./data";

const categories: Array<{ id: Category; label: string; short: string }> = [
  { id: "Roomies", label: "Roomes", short: "Habitaciones" },
  { id: "Depas", label: "Depas", short: "Alquiler mensual" },
  { id: "Airbnb", label: "Arbnb", short: "Por noche" },
  { id: "Transporte", label: "Transporte", short: "Mudanzas y premium" },
];

const categoryDetails: Record<Category, { noun: string; date: string; guests: string; priceLabel: string }> = {
  Roomies: { noun: "habitaciones", date: "Desde un mes", guests: "1 roomie", priceLabel: "por mes" },
  Depas: { noun: "departamentos", date: "6–12 meses", guests: "2 personas", priceLabel: "por mes" },
  Airbnb: { noun: "alojamientos", date: "9–14 de ago", guests: "2 huéspedes", priceLabel: "por noche" },
  Transporte: { noun: "servicios", date: "Cuando quieras", guests: "Carga o pasajeros", priceLabel: "por servicio" },
};

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

type AuthUser = {
  id: number;
  name: string;
  email: string;
  avatarUrl: string;
  authProvider: "google" | "password";
  role: "admin" | "user";
};

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
    `Hola ${listing.ownerName}, vi “${listing.title}” en roomies20 y me gustaría consultar disponibilidad${stayDetails}.`,
  );
  return `https://wa.me/${listing.ownerWhatsApp}?text=${message}`;
}

function listingImages(listing: Listing) {
  return Array.from(new Set([listing.image, ...(listing.gallery ?? [])].filter(Boolean)));
}

function imageUrl(source: string, width: number) {
  return `${source}${source.includes("?") ? "&" : "?"}auto=format&fit=crop&w=${width}&q=90`;
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
    { value: listing.details?.features.join(" ") ?? "", weight: 6 },
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
  if (listing.details) return listing.details;
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

export default function Home() {
  const [activeCategory, setActiveCategory] = useState<Category>("Roomies");
  const [search, setSearch] = useState("");
  const [service, setService] = useState("Todos");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [bedrooms, setBedrooms] = useState<BedroomFilter>("Todos");
  const [selectedDepaFeatures, setSelectedDepaFeatures] = useState<DepaFeature[]>([]);
  const [checkIn, setCheckIn] = useState(() => dateValue(addDays(new Date(), 14)));
  const [checkOut, setCheckOut] = useState(() => dateValue(addDays(new Date(), 15)));
  const [guestCount, setGuestCount] = useState(2);
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
  const [publishAfterLogin, setPublishAfterLogin] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authLoaded, setAuthLoaded] = useState(false);
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [galleryIndexes, setGalleryIndexes] = useState<Record<number, number>>({});
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [favorites, setFavorites] = useState<number[]>([]);
  const [listingsFromDb, setListingsFromDb] = useState<Listing[]>([]);
  const [loadedCategory, setLoadedCategory] = useState<Category | null>(null);
  const [notice, setNotice] = useState("");

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
    let cancelled = false;
    fetch(`/api/listings?category=${encodeURIComponent(activeCategory)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("No se pudo leer la base de datos");
        return (await response.json()) as { listings?: Listing[] };
      })
      .then((payload) => {
        if (!cancelled) {
          setListingsFromDb(payload.listings ?? []);
          setLoadedCategory(activeCategory);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setListingsFromDb([]);
          setLoadedCategory(activeCategory);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeCategory]);

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

  const categoryListings = (listingsFromDb.length ? listingsFromDb : demoListings)
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

    if (!search.trim()) return filteredListings;
    return filteredListings
      .map((listing) => ({ listing, score: listingSearchScore(listing, search) }))
      .filter((result) => result.score >= 0)
      .sort((left, right) => right.score - left.score)
      .map((result) => result.listing);
  }, [activeCategory, bedrooms, categoryListings, maxPrice, minPrice, search, selectedDepaFeatures, service]);

  const selectedGallery = selectedListing ? listingImages(selectedListing) : [];
  const safeSelectedImageIndex = selectedGallery.length
    ? Math.min(selectedImageIndex, selectedGallery.length - 1)
    : 0;

  function changeCategory(category: Category) {
    setActiveCategory(category);
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
    setShowSearchOptions(false);
    setShowAirbnbCalendar(false);
    setShowAirbnbGuests(false);
    setShowDepaFilters(true);
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
    const alreadyFavorite = favorites.includes(id);
    setFavorites((current) => alreadyFavorite
      ? current.filter((favoriteId) => favoriteId !== id)
      : [...current, id]);
    try {
      const response = await fetch("/api/favorites", {
        method: alreadyFavorite ? "DELETE" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listingId: id }),
      });
      if (!response.ok) throw new Error("No se pudo guardar");
      flashNotice(alreadyFavorite ? "Quitado de tus favoritos" : "Guardado en tus favoritos");
    } catch {
      setFavorites((current) => alreadyFavorite
        ? [...current, id]
        : current.filter((favoriteId) => favoriteId !== id));
      flashNotice("No pudimos actualizar tus favoritos");
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

  function flashNotice(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2400);
  }

  function resetFilters() {
    setSearch("");
    setMinPrice("");
    setMaxPrice("");
    setService("Todos");
    setBedrooms("Todos");
    setSelectedDepaFeatures([]);
  }

  function requestPublish() {
    if (!currentUser) {
      setPublishAfterLogin(true);
      setShowLogin(true);
      flashNotice(authLoaded ? "Inicia sesión para publicar" : "Verificando tu sesión…");
      return;
    }
    setPublishAfterLogin(false);
    setShowPublish(true);
  }

  function authenticated(user: AuthUser) {
    setCurrentUser(user);
    setShowLogin(false);
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
      const currentIndex = current[listing.id] ?? 0;
      return { ...current, [listing.id]: (currentIndex + direction + images.length) % images.length };
    });
  }

  function openListing(listing: Listing) {
    setSelectedImageIndex(galleryIndexes[listing.id] ?? 0);
    setSelectedListing(listing);
  }

  return (
    <div className="app-shell">
      <header className="market-header">
        <div className="services-top">
          <button className="brand" onClick={() => changeCategory("Roomies")} aria-label="Ir al inicio de roomies20">
            <span className="brand-symbol"><BrandKeysIcon /></span>
            <span>roomies20</span>
          </button>

          <nav className="service-nav" aria-label="Servicios de roomies20">
            {categories.map((category) => (
              <button key={category.id} className={`service-tab ${activeCategory === category.id ? "active" : ""}`} aria-current={activeCategory === category.id ? "page" : undefined} onClick={() => changeCategory(category.id)}>
                <span className={`service-icon service-icon-${category.id.toLowerCase()}`}><ServiceIcon category={category.id} /></span>
                <span><strong>{category.label}</strong><small>{category.short}</small></span>
              </button>
            ))}
          </nav>

          <div className="header-actions">
            <button className="host-link" onClick={() => setShowLogin(true)}>{currentUser ? "Mi cuenta" : "Iniciar sesión"}</button>
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
            <button className="menu-strong" onClick={() => { setShowLogin(true); setShowMenu(false); }}>{currentUser ? `Mi cuenta · ${currentUser.name}` : "Iniciar sesión"}</button>
            <button onClick={() => { setShowPlans(true); setShowMenu(false); }}>Ver planes para publicar</button>
            <button onClick={() => { setShowFilters(true); setShowMenu(false); }}>Filtros de búsqueda</button>
            <div className="menu-divider" />
            <button onClick={() => { requestPublish(); setShowMenu(false); }}>Publicar un anuncio</button>
            <button onClick={() => { flashNotice(`${favorites.length} favoritos guardados`); setShowMenu(false); }}>Mis favoritos <span>{favorites.length}</span></button>
            <button onClick={() => { flashNotice("Soporte directo: hola@roomies20.com"); setShowMenu(false); }}>Centro de ayuda</button>
          </div>
        )}
      </header>

      <main className="results-layout" id="results">
        <section className="list-panel">
          {activeCategory === "Depas" ? (
            <div className="depa-results-heading">
              <div><h1>{search ? `Departamentos en ${search}` : "Departamentos en Lima"}</h1><p>{loadedCategory !== activeCategory ? "Buscando opciones…" : `${visibleListings.length} ${visibleListings.length === 1 ? "proyecto disponible" : "proyectos disponibles"} · Alquiler mensual con contacto directo`}</p></div>
              <button onClick={openDepaFilters}><FilterIcon /><span>Filtros</span>{activeDepaFilterCount > 0 && <b>{activeDepaFilterCount}</b>}</button>
            </div>
          ) : <h1 className="sr-only">{loadedCategory !== activeCategory ? "Buscando opciones…" : `${visibleListings.length} ${detail.noun}${search ? ` para ${search}` : " disponibles"}`}</h1>}

          {visibleListings.length > 0 ? (
            <div className={`listing-grid ${activeCategory === "Depas" ? "depa-listing-grid" : ""}`}>
              {visibleListings.map((listing) => {
                const images = listingImages(listing);
                const imageIndex = Math.min(galleryIndexes[listing.id] ?? 0, images.length - 1);
                return (
                <article key={listing.id} className={`listing-card ${activeCategory === "Depas" ? "depa-card" : ""}`} onClick={() => openListing(listing)}>
                  <div className="listing-image-wrap">
                    <img src={imageUrl(images[imageIndex] ?? listing.image, 900)} alt={`${listing.title}, fotografía ${imageIndex + 1}`} className="listing-image" />
                    {listing.badge && <span className="listing-badge">{listing.badge}</span>}
                    <button className={`favorite-button ${favorites.includes(listing.id) ? "is-favorite" : ""}`} onClick={(event) => { event.stopPropagation(); toggleFavorite(listing.id); }} aria-label={favorites.includes(listing.id) ? "Quitar de favoritos" : "Guardar en favoritos"}>{favorites.includes(listing.id) ? "♥" : "♡"}</button>
                    <button className="carousel-arrow" disabled={images.length < 2} onClick={(event) => { event.stopPropagation(); moveGallery(listing, 1); }} aria-label={`Siguiente fotografía de ${listing.title}`}>›</button>
                    {images.length > 1 && <div className="image-dots" aria-label={`Fotografía ${imageIndex + 1} de ${images.length}`}>
                      {images.map((_, index) => <button key={`${listing.id}-${index}`} className={index === imageIndex ? "active" : ""} onClick={(event) => { event.stopPropagation(); setGalleryIndexes((current) => ({ ...current, [listing.id]: index })); }} aria-label={`Ver fotografía ${index + 1}`} aria-current={index === imageIndex ? "true" : undefined} />)}
                    </div>}
                  </div>
                  {activeCategory === "Depas" ? (() => {
                    const details = depaDetails(listing);
                    return <div className="listing-copy depa-copy">
                      <div className="depa-title-row"><h2>{listing.title}</h2><span>★ {listing.rating.toFixed(2).replace(/0$/, "")} <small>({listing.reviews})</small></span></div>
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
                        <a className="whatsapp-card" href={whatsappLink(listing)} onClick={(event) => { event.stopPropagation(); trackInquiry(listing.id); }} target="_blank" rel="noreferrer" aria-label={`Contactar a ${listing.ownerName} por WhatsApp`} title={`Chatear con ${listing.ownerName} en WhatsApp`}><WhatsappIcon /></a>
                      </div>
                    </div>;
                  })() : <div className="listing-copy">
                      <div className="card-title-row"><h2>{listing.title}</h2><span>★ {listing.rating.toFixed(2).replace(/0$/, "")} <small>({listing.reviews})</small></span></div>
                      <p className="listing-location">{listing.location}</p>
                      <p className="listing-meta">{listing.meta}</p>
                      <p className="listing-dates">{dateLabel}</p>
                      <div className="price-row">
                        <div><p><strong>{money.format(listing.price)}</strong> <span>{listing.priceLabel}</span></p><span className="cancellation-tag">Contacto directo</span></div>
                        <a className="whatsapp-card" href={whatsappLink(listing)} onClick={(event) => { event.stopPropagation(); trackInquiry(listing.id); }} target="_blank" rel="noreferrer" aria-label={`Contactar a ${listing.ownerName} por WhatsApp`} title={`Chatear con ${listing.ownerName} en WhatsApp`}><WhatsappIcon /></a>
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

        </section>
      </main>

      <footer className="footer">
        <div className="footer-top">
          <div><strong>Asistencia</strong><button onClick={() => flashNotice("Soporte: hola@roomies20.com")}>Centro de ayuda</button><button onClick={() => flashNotice("Próximamente: seguridad y confianza")}>Seguridad</button></div>
          <div><strong>Publica</strong><button onClick={requestPublish}>Anuncia tu espacio</button><button onClick={() => setShowPlans(true)}>Planes anuales</button></div>
          <div><strong>roomies20</strong><button onClick={() => flashNotice("Muy pronto: conoce al equipo roomies20")}>Quiénes somos</button><button onClick={() => flashNotice("Soporte: hola@roomies20.com")}>Contacto</button></div>
        </div>
        <div className="footer-bottom"><span>© 2026 roomies20 · Privacidad · Términos</span><span>Español (PE) · S/ PEN</span></div>
      </footer>

      {notice && <div className="toast" role="status"><span>✓</span>{notice}</div>}

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
          <div className="modal-header"><div><span className="modal-kicker">Anuncia en roomies20</span><h2>Un pago anual. Cero comisiones extras.</h2></div><button className="close-button" onClick={() => setShowPlans(false)} aria-label="Cerrar planes">×</button></div>
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
        />
      )}

      {showPublish && currentUser && <PublishModal category={activeCategory} defaultOwnerName={currentUser.name} onClose={() => setShowPublish(false)} onCreated={(listing) => { setListingsFromDb((current) => [listing, ...current]); setActiveCategory(listing.category); setShowPublish(false); flashNotice("Tu publicación fue guardada"); }} />}

      {selectedListing && (
        <Modal onClose={() => setSelectedListing(null)} className="detail-modal">
          <button className="close-button detail-close" onClick={() => setSelectedListing(null)} aria-label="Cerrar detalle">×</button>
          <div className="detail-image">
            <img src={imageUrl(selectedGallery[safeSelectedImageIndex] ?? selectedListing.image, 1200)} alt={`${selectedListing.title}, fotografía ${safeSelectedImageIndex + 1}`} />
            {selectedListing.badge && <span>{selectedListing.badge}</span>}
            {selectedGallery.length > 1 && <>
              <button className="detail-gallery-arrow previous" onClick={() => setSelectedImageIndex((current) => (current - 1 + selectedGallery.length) % selectedGallery.length)} aria-label="Fotografía anterior">‹</button>
              <button className="detail-gallery-arrow next" onClick={() => setSelectedImageIndex((current) => (current + 1) % selectedGallery.length)} aria-label="Siguiente fotografía">›</button>
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
            <div className="detail-benefits"><span>✓ Publicación verificada</span><span>✓ Trato directo</span><span>✓ Sin comisiones</span></div>
            <div className="detail-footer"><div><small>{selectedListing.category === "Depas" ? "Alquiler desde" : selectedListing.category === "Airbnb" ? `Total por ${airbnbNights} ${airbnbNights === 1 ? "noche" : "noches"}` : "Precio"}</small><strong>{selectedListing.category === "Airbnb" ? money.format(selectedListing.price * airbnbNights) : money.format(selectedListing.price)} {selectedListing.category !== "Airbnb" && <em>{selectedListing.priceLabel}</em>}</strong></div><a className="primary-button" href={whatsappLink(selectedListing, { checkIn, checkOut, guests: guestCount })} onClick={() => trackInquiry(selectedListing.id)} target="_blank" rel="noreferrer">{selectedListing.category === "Airbnb" ? "Consultar disponibilidad" : "Contactar por WhatsApp"} <Icon>↗</Icon></a></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Modal({ children, onClose, className = "" }: { children: React.ReactNode; onClose: () => void; className?: string }) {
  return <div className="modal-backdrop" onClick={onClose}><div className={`modal ${className}`} role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>{children}</div></div>;
}

function AuthModal({ user, onClose, onAuthenticated, onLoggedOut }: { user: AuthUser | null; onClose: () => void; onAuthenticated: (user: AuthUser) => void; onLoggedOut: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [showPasswordAccess, setShowPasswordAccess] = useState(false);
  const [googleStatus, setGoogleStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [googleMessage, setGoogleMessage] = useState("");
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const authenticatedRef = useRef(onAuthenticated);

  useEffect(() => {
    authenticatedRef.current = onAuthenticated;
  }, [onAuthenticated]);

  useEffect(() => {
    if (user) return;
    let cancelled = false;

    async function configureGoogle() {
      try {
        const response = await fetch("/api/auth/config");
        const config = (await response.json()) as { googleEnabled?: boolean; googleClientId?: string };
        if (!response.ok || !config.googleEnabled || !config.googleClientId) {
          throw new Error("El acceso con Google está terminando de configurarse.");
        }
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
        });
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "rectangular",
          text: "continue_with",
          logo_alignment: "left",
          width: Math.max(200, Math.min(344, Math.floor(googleButtonRef.current.getBoundingClientRect().width))),
        });
        if (!cancelled) setGoogleStatus("ready");
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
    };
  }, [user]);

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
      <span className="modal-kicker">{user?.role === "admin" ? "Cuenta administradora" : "Tu cuenta roomies20"}</span>
      {user ? (
        <div className="account-summary">
          <h2>Hola, {user.name}</h2>
          <p>Tu sesión está activa y ya puedes publicar anuncios con tu cuenta.</p>
          <span>{user.email}{user.role === "admin" && <b>Administrador</b>}</span>
          {error && <p className="form-error">{error}</p>}
          <button className="primary-button account-button" onClick={onClose}>Continuar <Icon>→</Icon></button>
          <button className="text-action account-logout" disabled={isSaving} onClick={logout}>{isSaving ? "Cerrando…" : "Cerrar sesión"}</button>
        </div>
      ) : (
        <>
          <h2>Inicia sesión para continuar</h2>
          <p>Accede con Google para guardar favoritos, publicar anuncios y gestionar tus consultas de forma segura.</p>
          <div className={`google-auth-panel ${isSaving ? "busy" : ""}`}>
            <div className="google-button-shell">
              <div ref={googleButtonRef} className="google-button-target" aria-label="Continuar con Google" />
              {googleStatus === "loading" && <span className="google-loading">Preparando acceso con Google…</span>}
              {googleStatus === "unavailable" && <span className="google-unavailable">{googleMessage}</span>}
            </div>
            <small>Google confirma tu identidad; roomies20 crea una sesión segura en este dispositivo.</small>
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

function PublishModal({ category, defaultOwnerName, onClose, onCreated }: { category: Category; defaultOwnerName: string; onClose: () => void; onCreated: (listing: Listing) => void }) {
  const [form, setForm] = useState({ title: "", location: "", price: "", description: "", ownerName: defaultOwnerName, ownerWhatsApp: "" });
  const [depaForm, setDepaForm] = useState({ address: "", units: "1", areaTotal: "", areaCovered: "", bedroomsMin: "1", bedroomsMax: "1", bathroomsMin: "1", bathroomsMax: "1", delivery: "Disponible ahora", availability: "Contrato de 6 a 12 meses" });
  const [depaPublishFeatures, setDepaPublishFeatures] = useState<DepaFeature[]>([]);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    try {
      let image: string | undefined;
      if (imageFile) {
        const imageData = new FormData();
        imageData.append("file", imageFile);
        const uploadResponse = await fetch("/api/uploads", { method: "POST", body: imageData });
        const uploadPayload = (await uploadResponse.json()) as { url?: string; error?: string };
        if (!uploadResponse.ok || !uploadPayload.url) throw new Error(uploadPayload.error ?? "No se pudo subir la fotografía");
        image = uploadPayload.url;
      }
      const response = await fetch("/api/listings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          image,
          category,
          price: Number(form.price),
          priceLabel: categoryDetails[category].priceLabel,
          details: category === "Depas" ? {
            ...depaForm,
            address: depaForm.address || form.location,
            units: Number(depaForm.units),
            bedroomsMin: Number(depaForm.bedroomsMin),
            bedroomsMax: Number(depaForm.bedroomsMax),
            bathroomsMin: Number(depaForm.bathroomsMin),
            bathroomsMax: Number(depaForm.bathroomsMax),
            features: depaPublishFeatures,
          } : undefined,
        }),
      });
      const payload = (await response.json()) as { listing?: Listing; error?: string };
      if (!response.ok || !payload.listing) throw new Error(payload.error ?? "No se pudo guardar la publicación");
      onCreated(payload.listing);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Revisa los datos e intenta otra vez.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal onClose={onClose} className="publish-modal">
      <div className="modal-header"><div><span className="modal-kicker">Publicar {category.toLowerCase()}</span><h2>Haz que te encuentren</h2></div><button className="close-button" onClick={onClose} aria-label="Cerrar publicación">×</button></div>
      <p className="modal-lead">Completa los datos esenciales. Tus clientes podrán contactarte directamente.</p>
      <form onSubmit={submit}>
        <div className="form-grid"><label>Título<input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ej. Depa luminoso en Barranco" /></label><label>Ubicación<input required value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Distrito, ciudad" /></label><label>Precio en soles<input required min="1" type="number" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="450" /></label><label>Tu nombre<input required value={form.ownerName} onChange={(event) => setForm({ ...form, ownerName: event.target.value })} placeholder="Cómo te conocerán" /></label></div>
        {category === "Depas" && <fieldset className="publish-depa-fields"><legend>Datos del departamento</legend><div className="form-grid"><label>Dirección exacta<input required value={depaForm.address} onChange={(event) => setDepaForm({ ...depaForm, address: event.target.value })} placeholder="Av., calle y número" /></label><label>Número de unidades<input required min="1" type="number" value={depaForm.units} onChange={(event) => setDepaForm({ ...depaForm, units: event.target.value })} /></label><label>Área total<input required value={depaForm.areaTotal} onChange={(event) => setDepaForm({ ...depaForm, areaTotal: event.target.value })} placeholder="Ej. 53 a 60 m² tot." /></label><label>Área techada<input required value={depaForm.areaCovered} onChange={(event) => setDepaForm({ ...depaForm, areaCovered: event.target.value })} placeholder="Ej. 53 a 60 m² techada" /></label><label>Dormitorios mínimos<input required min="1" max="10" type="number" value={depaForm.bedroomsMin} onChange={(event) => setDepaForm({ ...depaForm, bedroomsMin: event.target.value })} /></label><label>Dormitorios máximos<input required min={depaForm.bedroomsMin || "1"} max="10" type="number" value={depaForm.bedroomsMax} onChange={(event) => setDepaForm({ ...depaForm, bedroomsMax: event.target.value })} /></label><label>Baños mínimos<input required min="1" max="10" type="number" value={depaForm.bathroomsMin} onChange={(event) => setDepaForm({ ...depaForm, bathroomsMin: event.target.value })} /></label><label>Baños máximos<input required min={depaForm.bathroomsMin || "1"} max="10" type="number" value={depaForm.bathroomsMax} onChange={(event) => setDepaForm({ ...depaForm, bathroomsMax: event.target.value })} /></label><label>Entrega<input required value={depaForm.delivery} onChange={(event) => setDepaForm({ ...depaForm, delivery: event.target.value })} /></label><label>Disponibilidad o contrato<input required value={depaForm.availability} onChange={(event) => setDepaForm({ ...depaForm, availability: event.target.value })} /></label></div><span className="publish-feature-label">Características</span><div className="publish-feature-options">{depaFeatureOptions.map((feature) => { const selected = depaPublishFeatures.includes(feature); return <button type="button" key={feature} className={selected ? "selected" : ""} aria-pressed={selected} onClick={() => setDepaPublishFeatures((current) => current.includes(feature) ? current.filter((item) => item !== feature) : [...current, feature])}>{selected ? "✓" : "+"} {feature}</button>; })}</div></fieldset>}
        <label>Descripción<textarea required rows={4} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Cuenta qué hace especial a tu anuncio…" /></label>
        <label className="image-upload">Fotografía principal<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setImageFile(event.target.files?.[0] ?? null)} /><span>{imageFile ? `✓ ${imageFile.name}` : "Seleccionar imagen · máximo 8 MB"}</span></label>
        <label>WhatsApp de contacto<input required value={form.ownerWhatsApp} onChange={(event) => setForm({ ...form, ownerWhatsApp: event.target.value })} placeholder="51999888777" /></label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button wide" disabled={isSaving}>{isSaving ? "Guardando…" : "Guardar y publicar"}<Icon>→</Icon></button>
      </form>
    </Modal>
  );
}
