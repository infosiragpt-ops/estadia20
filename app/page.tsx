/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { demoListings, type Category, type Listing } from "./data";

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

const money = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
  maximumFractionDigits: 0,
});

function whatsappLink(listing: Listing) {
  const message = encodeURIComponent(
    `Hola ${listing.ownerName}, vi “${listing.title}” en roomies20 y me gustaría recibir más información.`,
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

function BrandHomeIcon() {
  return <svg aria-hidden="true" viewBox="0 0 48 48"><path d="M5 23.2 24 6l19 17.2-4.2 4.6-2.8-2.5V42H12V25.3l-2.8 2.5L5 23.2Z" fill="currentColor" /><path d="M20 42V29h8v13" fill="#ffbd00" /></svg>;
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

function GlobeIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.7" /><path d="M3.5 12h17M12 3c3.5 3.6 3.5 14.4 0 18M12 3c-3.5 3.6-3.5 14.4 0 18" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>;
}

function LocationIcon() {
  return <svg aria-hidden="true" viewBox="0 0 48 48"><path d="M8 17 24 6l16 11v25H8z" fill="#eeeeea" stroke="#7c7c75" strokeWidth="1.5" /><path d="M6 18 24 5l18 13" fill="none" stroke="#373737" strokeWidth="2.3" strokeLinecap="round" /><rect x="19" y="22" width="12" height="20" rx="1" fill="#ec315d" /><circle cx="28" cy="32" r="1.2" fill="#fff" /><path d="M7 42h34" stroke="#373737" strokeWidth="2" /></svg>;
}

function WhatsappIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M20.5 11.7a8.5 8.5 0 0 1-12.6 7.5L3 20.5l1.3-4.7a8.5 8.5 0 1 1 16.2-4.1Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M8.1 7.7c.3-.7.7-.7 1.1-.7.2 0 .5 0 .7.5l1 2c.2.4 0 .7-.2 1l-.7.8c.8 1.7 2 2.8 3.8 3.6l.8-1c.3-.3.6-.4 1-.2l2 .9c.4.2.5.5.4.9-.2 1.3-1.1 2.2-2.4 2.4-2.3.3-5.2-1.2-7.3-3.3-2-2-3.2-4.7-2.8-6.5.2-.8.9-1.3 1.6-1.4" fill="currentColor" /></svg>;
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short" })
    .format(new Date(`${value}T12:00:00`));
}

function formatDateRange(from: string, to: string) {
  const first = new Date(`${from}T12:00:00`);
  const last = new Date(`${to}T12:00:00`);
  const month = new Intl.DateTimeFormat("es-PE", { month: "short" }).format(last).replace(".", "").toLowerCase();
  return `${first.getDate()} – ${last.getDate()} de ${month}`;
}

export default function Home() {
  const [activeCategory, setActiveCategory] = useState<Category>("Roomies");
  const [search, setSearch] = useState("");
  const [service, setService] = useState("Todos");
  const [maxPrice, setMaxPrice] = useState("");
  const [checkIn, setCheckIn] = useState("2026-08-19");
  const [checkOut, setCheckOut] = useState("2026-08-20");
  const [guestCount, setGuestCount] = useState(2);
  const [showSearchOptions, setShowSearchOptions] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showPlans, setShowPlans] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [galleryIndexes, setGalleryIndexes] = useState<Record<number, number>>({});
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [favorites, setFavorites] = useState<number[]>([]);
  const [listingsFromDb, setListingsFromDb] = useState<Listing[]>([]);
  const [loadedCategory, setLoadedCategory] = useState<Category | null>(null);
  const [notice, setNotice] = useState("");

  const detail = categoryDetails[activeCategory];
  const searchDateLabel = activeCategory === "Transporte" ? detail.date : formatDateRange(checkIn, checkOut);
  const dateLabel = activeCategory === "Airbnb"
    ? `${formatShortDate(checkIn)} – ${formatShortDate(checkOut)}`
    : detail.date;

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
    const normalizedSearch = search.trim().toLowerCase();
    const parsedMax = Number(maxPrice);
    return categoryListings.filter((listing) => {
      const haystack = [listing.title, listing.location, listing.meta, listing.description].join(" ").toLowerCase();
      if (normalizedSearch && !haystack.includes(normalizedSearch)) return false;
      if (activeCategory === "Transporte" && service !== "Todos" && listing.service !== service) return false;
      if (maxPrice && listing.price > parsedMax) return false;
      return true;
    });
  }, [activeCategory, categoryListings, maxPrice, search, service]);

  const selectedGallery = selectedListing ? listingImages(selectedListing) : [];
  const safeSelectedImageIndex = selectedGallery.length
    ? Math.min(selectedImageIndex, selectedGallery.length - 1)
    : 0;

  function changeCategory(category: Category) {
    setActiveCategory(category);
    setService("Todos");
    setMaxPrice("");
    setShowMenu(false);
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
    setMaxPrice("");
    setService("Todos");
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
            <span className="brand-symbol"><BrandHomeIcon /></span>
            <span>roomies20</span>
          </button>

          <nav className="service-nav" aria-label="Servicios de roomies20">
            {categories.map((category) => (
              <button key={category.id} className={`service-tab ${activeCategory === category.id ? "active" : ""}`} onClick={() => changeCategory(category.id)}>
                <span className={`service-icon service-icon-${category.id.toLowerCase()}`}><ServiceIcon category={category.id} /></span>
                <span><strong>{category.label}</strong><small>{category.short}</small></span>
              </button>
            ))}
          </nav>

          <div className="header-actions">
            <button className="host-link" onClick={() => setShowPublish(true)}>Anuncia</button>
            <button className="globe-button" aria-label="Idioma y moneda"><GlobeIcon /></button>
            <button className="menu-trigger" aria-label="Abrir menú" aria-expanded={showMenu} onClick={() => setShowMenu((open) => !open)}>
              <span className="hamburger"><i /><i /><i /></span>
            </button>
          </div>
        </div>

        <div className="search-row">
          <div className="compact-search" role="search">
            <label className="compact-field location-field">
              <span className="location-icon"><LocationIcon /></span>
              <input aria-label="Ubicación" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Alojamientos en Santa Cruz de la Sierra" />
            </label>
            <button className="compact-field date-field" onClick={() => setShowSearchOptions((open) => !open)}>
              <strong>{searchDateLabel}</strong>
            </button>
            <button className="compact-field guest-field" onClick={() => setShowSearchOptions((open) => !open)}>
              <strong>{activeCategory === "Transporte" ? detail.guests : `${guestCount} ${guestCount === 1 ? "huésped" : "huéspedes"}`}</strong>
            </button>
            <button className="search-button" onClick={() => { setShowSearchOptions(false); document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }); }} aria-label="Buscar">
              <SearchIcon />
            </button>
          </div>
        </div>

        {showSearchOptions && (
          <div className="search-options-popover">
            <div className="date-controls"><label>Llegada<input type="date" value={checkIn} onChange={(event) => setCheckIn(event.target.value)} /></label><label>Salida<input type="date" min={checkIn} value={checkOut} onChange={(event) => setCheckOut(event.target.value)} /></label></div>
            <div className="guest-control"><span><strong>Viajeros</strong><small>¿Cuántas personas van?</small></span><div><button onClick={() => setGuestCount((count) => Math.max(1, count - 1))} aria-label="Quitar huésped">−</button><b>{guestCount}</b><button onClick={() => setGuestCount((count) => Math.min(16, count + 1))} aria-label="Agregar huésped">＋</button></div></div>
            <button className="apply-search" onClick={() => setShowSearchOptions(false)}>Aplicar búsqueda</button>
          </div>
        )}

        {showMenu && (
          <div className="menu-popover">
            <button className="menu-strong" onClick={() => { setShowLogin(true); setShowMenu(false); }}>Iniciar sesión</button>
            <button onClick={() => { setShowPlans(true); setShowMenu(false); }}>Ver planes para publicar</button>
            <button onClick={() => { setShowFilters(true); setShowMenu(false); }}>Filtros de búsqueda</button>
            <div className="menu-divider" />
            <button onClick={() => { setShowPublish(true); setShowMenu(false); }}>Publicar un anuncio</button>
            <button onClick={() => { flashNotice(`${favorites.length} favoritos guardados`); setShowMenu(false); }}>Mis favoritos <span>{favorites.length}</span></button>
            <button onClick={() => { flashNotice("Soporte directo: hola@roomies20.com"); setShowMenu(false); }}>Centro de ayuda</button>
          </div>
        )}
      </header>

      <main className="results-layout" id="results">
        <section className="list-panel">
          <h1 className="sr-only">{loadedCategory !== activeCategory ? "Buscando opciones…" : `${visibleListings.length} ${detail.noun} en ${search || "Santa Cruz de la Sierra"}`}</h1>

          {visibleListings.length > 0 ? (
            <div className="listing-grid">
              {visibleListings.map((listing) => {
                const images = listingImages(listing);
                const imageIndex = Math.min(galleryIndexes[listing.id] ?? 0, images.length - 1);
                return (
                <article key={listing.id} className="listing-card" onClick={() => openListing(listing)}>
                  <div className="listing-image-wrap">
                    <img src={imageUrl(images[imageIndex] ?? listing.image, 900)} alt={`${listing.title}, fotografía ${imageIndex + 1}`} className="listing-image" />
                    {listing.badge && <span className="listing-badge">{listing.badge}</span>}
                    <button className={`favorite-button ${favorites.includes(listing.id) ? "is-favorite" : ""}`} onClick={(event) => { event.stopPropagation(); toggleFavorite(listing.id); }} aria-label={favorites.includes(listing.id) ? "Quitar de favoritos" : "Guardar en favoritos"}>{favorites.includes(listing.id) ? "♥" : "♡"}</button>
                    <button className="carousel-arrow" disabled={images.length < 2} onClick={(event) => { event.stopPropagation(); moveGallery(listing, 1); }} aria-label={`Siguiente fotografía de ${listing.title}`}>›</button>
                    {images.length > 1 && <div className="image-dots" aria-label={`Fotografía ${imageIndex + 1} de ${images.length}`}>
                      {images.map((_, index) => <button key={`${listing.id}-${index}`} className={index === imageIndex ? "active" : ""} onClick={(event) => { event.stopPropagation(); setGalleryIndexes((current) => ({ ...current, [listing.id]: index })); }} aria-label={`Ver fotografía ${index + 1}`} aria-current={index === imageIndex ? "true" : undefined} />)}
                    </div>}
                  </div>
                  <div className="listing-copy">
                    <div className="card-title-row"><h2>{listing.title}</h2><span>★ {listing.rating.toFixed(2).replace(/0$/, "")} <small>({listing.reviews})</small></span></div>
                    <p className="listing-location">{listing.location}</p>
                    <p className="listing-meta">{listing.meta}</p>
                    <p className="listing-dates">{dateLabel}</p>
                    <div className="price-row">
                      <div><p><strong>{money.format(listing.price)}</strong> <span>{listing.priceLabel}</span></p><span className="cancellation-tag">Contacto directo</span></div>
                      <a className="whatsapp-card" href={whatsappLink(listing)} onClick={(event) => { event.stopPropagation(); trackInquiry(listing.id); }} target="_blank" rel="noreferrer" aria-label={`Contactar a ${listing.ownerName} por WhatsApp`}><WhatsappIcon /></a>
                    </div>
                  </div>
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
          <div><strong>Publica</strong><button onClick={() => setShowPublish(true)}>Anuncia tu espacio</button><button onClick={() => setShowPlans(true)}>Planes anuales</button></div>
          <div><strong>roomies20</strong><button onClick={() => flashNotice("Muy pronto: conoce al equipo roomies20")}>Quiénes somos</button><button onClick={() => flashNotice("Soporte: hola@roomies20.com")}>Contacto</button></div>
        </div>
        <div className="footer-bottom"><span>© 2026 roomies20 · Privacidad · Términos</span><span>Español (PE) · S/ PEN</span></div>
      </footer>

      {notice && <div className="toast" role="status"><span>✓</span>{notice}</div>}

      {showFilters && (
        <Modal onClose={() => setShowFilters(false)} className="filters-modal">
          <div className="modal-header"><div><span className="modal-kicker">Personaliza tu búsqueda</span><h2>Filtros</h2></div><button className="close-button" onClick={() => setShowFilters(false)} aria-label="Cerrar filtros">×</button></div>
          <div className="filter-section"><h3>Presupuesto máximo</h3><div className="price-input"><span>S/</span><input type="number" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} placeholder="Sin límite" /></div></div>
          <div className="filter-section"><h3>Ubicación</h3><input className="full-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Distrito o ciudad" /></div>
          {activeCategory === "Transporte" && <div className="filter-section"><h3>Tipo de servicio</h3><div className="modal-options">{["Todos", "Mudanza", "Corporativo"].map((item) => <button key={item} className={service === item ? "selected" : ""} onClick={() => setService(item)}>{item}</button>)}</div></div>}
          <div className="modal-footer"><button className="text-action" onClick={resetFilters}>Limpiar todo</button><button className="dark-button" onClick={() => setShowFilters(false)}>Mostrar {visibleListings.length} resultados</button></div>
        </Modal>
      )}

      {showPlans && (
        <Modal onClose={() => setShowPlans(false)} className="plans-modal">
          <div className="modal-header"><div><span className="modal-kicker">Anuncia en roomies20</span><h2>Un pago anual. Cero comisiones extras.</h2></div><button className="close-button" onClick={() => setShowPlans(false)} aria-label="Cerrar planes">×</button></div>
          <p className="modal-lead">Nosotros llevamos tráfico a la plataforma y cada consulta llega directamente a ti.</p>
          <div className="plans-list">{plans.map((plan) => <button key={plan.name} onClick={() => { setShowPlans(false); setShowPublish(true); }}><span className="plan-icon"><Icon>{plan.icon}</Icon></span><span><strong>{plan.name}</strong><small>{plan.detail}</small></span><b>{plan.price}</b><Icon>›</Icon></button>)}</div>
          <div className="benefits"><span>✓ 12 meses publicado</span><span>✓ Contacto directo</span><span>✓ Sin comisión por reserva</span></div>
        </Modal>
      )}

      {showLogin && (
        <Modal onClose={() => setShowLogin(false)} className="login-modal">
          <button className="close-button login-close" onClick={() => setShowLogin(false)} aria-label="Cerrar inicio de sesión">×</button>
          <span className="login-logo"><Icon>⌂</Icon></span><span className="modal-kicker">Tu cuenta roomies20</span><h2>Inicia sesión para continuar</h2><p>Guarda favoritos, publica anuncios y gestiona tus consultas desde un solo lugar.</p>
          <a className="primary-button" href="/signin-with-chatgpt?return_to=%2F">Continuar con ChatGPT <Icon>→</Icon></a><small>Al continuar aceptas nuestros términos de uso.</small>
        </Modal>
      )}

      {showPublish && <PublishModal category={activeCategory} onClose={() => setShowPublish(false)} onCreated={(listing) => { setListingsFromDb((current) => [listing, ...current]); setActiveCategory(listing.category); setShowPublish(false); flashNotice("Tu publicación fue guardada"); }} />}

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
          <div className="detail-body"><div className="detail-title"><div><span className="modal-kicker">{selectedListing.category}</span><h2>{selectedListing.title}</h2></div><strong>★ {selectedListing.rating.toFixed(1)} ({selectedListing.reviews})</strong></div><p className="detail-location">{selectedListing.location}</p><p className="detail-description">{selectedListing.description}</p><div className="detail-benefits"><span>✓ Publicación verificada</span><span>✓ Trato directo</span><span>✓ Sin comisiones</span></div><div className="detail-footer"><div><small>Precio</small><strong>{money.format(selectedListing.price)} <em>{selectedListing.priceLabel}</em></strong></div><a className="primary-button" href={whatsappLink(selectedListing)} onClick={() => trackInquiry(selectedListing.id)} target="_blank" rel="noreferrer">Contactar por WhatsApp <Icon>↗</Icon></a></div></div>
        </Modal>
      )}
    </div>
  );
}

function Modal({ children, onClose, className = "" }: { children: React.ReactNode; onClose: () => void; className?: string }) {
  return <div className="modal-backdrop" onClick={onClose}><div className={`modal ${className}`} role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>{children}</div></div>;
}

function PublishModal({ category, onClose, onCreated }: { category: Category; onClose: () => void; onCreated: (listing: Listing) => void }) {
  const [form, setForm] = useState({ title: "", location: "", price: "", description: "", ownerName: "", ownerWhatsApp: "" });
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
        body: JSON.stringify({ ...form, image, category, price: Number(form.price), priceLabel: categoryDetails[category].priceLabel }),
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
        <label>Descripción<textarea required rows={4} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Cuenta qué hace especial a tu anuncio…" /></label>
        <label className="image-upload">Fotografía principal<input type="file" accept="image/jpeg,image/png,image/webp,image/avif" onChange={(event) => setImageFile(event.target.files?.[0] ?? null)} /><span>{imageFile ? `✓ ${imageFile.name}` : "Seleccionar imagen · máximo 8 MB"}</span></label>
        <label>WhatsApp de contacto<input required value={form.ownerWhatsApp} onChange={(event) => setForm({ ...form, ownerWhatsApp: event.target.value })} placeholder="51999888777" /></label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button wide" disabled={isSaving}>{isSaving ? "Guardando…" : "Guardar y publicar"}<Icon>→</Icon></button>
      </form>
    </Modal>
  );
}
