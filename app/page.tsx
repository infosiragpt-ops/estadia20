"use client";

import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { demoListings, type Category, type Listing } from "./data";

const categories: Array<{
  id: Category;
  label: string;
  icon: string;
  description: string;
}> = [
  { id: "Roomies", label: "Roomies", icon: "⌂", description: "Habitaciones compartidas" },
  { id: "Depas", label: "Depas", icon: "▥", description: "Contratos de 6 a 12 meses" },
  { id: "Airbnb", label: "Airbnb", icon: "✦", description: "Estancias por noche" },
  { id: "Transporte", label: "Transporte", icon: "▱", description: "Mudanzas y corporativo" },
];

const categoryCopy: Record<Category, { kicker: string; title: string; body: string; search: string }> = {
  Roomies: {
    kicker: "Vive acompañado, vive mejor",
    title: "Tu próxima habitación está más cerca de lo que crees.",
    body: "Encuentra espacios compartidos con gente compatible y habla directo con quien arrienda.",
    search: "¿En qué ciudad quieres vivir?",
  },
  Depas: {
    kicker: "Tu espacio, tus reglas",
    title: "Departamentos para quedarte y sentirte en casa.",
    body: "Alquileres mensuales con contratos claros de 6 a 12 meses y contacto directo.",
    search: "¿Dónde quieres encontrar tu depa?",
  },
  Airbnb: {
    kicker: "Escapadas que se sienten tuyas",
    title: "Quédate en lugares que cuentan una historia.",
    body: "Hospedajes por día o noche, con filtros simples y reservas conversadas con el propietario.",
    search: "¿A dónde vas?",
  },
  Transporte: {
    kicker: "Muévete con respaldo",
    title: "El vehículo indicado para cada traslado.",
    body: "Mudanzas por tonelaje y vehículos corporativos premium verificados, directo con el afiliado.",
    search: "¿Desde dónde necesitas moverte?",
  },
};

const plans = [
  { name: "Roomie", price: "S/ 25", detail: "por habitación / año", icon: "⌂", tone: "lavender" },
  { name: "Depa", price: "S/ 50", detail: "por departamento / año", icon: "▥", tone: "peach" },
  { name: "Airbnb", price: "S/ 100", detail: "por anuncio / año", icon: "✦", tone: "mint" },
  { name: "Transporte", price: "S/ 50", detail: "por servicio / año", icon: "▱", tone: "blue" },
];

const money = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
  maximumFractionDigits: 0,
});

function whatsappLink(listing: Listing) {
  const message = encodeURIComponent(
    `Hola ${listing.ownerName}, vi “${listing.title}” en depitass y me gustaría recibir más información.`,
  );
  return `https://wa.me/${listing.ownerWhatsApp}?text=${message}`;
}

function Icon({ name }: { name: string }) {
  return <span className="icon-glyph" aria-hidden="true">{name}</span>;
}

export default function Home() {
  const [activeCategory, setActiveCategory] = useState<Category>("Roomies");
  const [search, setSearch] = useState("");
  const [service, setService] = useState("Todos");
  const [maxPrice, setMaxPrice] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showPlans, setShowPlans] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [favorites, setFavorites] = useState<number[]>([]);
  const [listingsFromDb, setListingsFromDb] = useState<Listing[]>([]);
  const [notice, setNotice] = useState("");
  const [loadedCategory, setLoadedCategory] = useState<Category | null>(null);

  const currentCategory = categoryCopy[activeCategory];

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

  const isLoading = loadedCategory !== activeCategory;

  const baseListings = listingsFromDb.length
    ? listingsFromDb
    : demoListings.filter((listing) => listing.category === activeCategory);

  const visibleListings = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const parsedMax = Number(maxPrice);
    return baseListings.filter((listing) => {
      const matchesSearch = !normalizedSearch ||
        [listing.title, listing.location, listing.meta, listing.description]
          .join(" ")
          .toLowerCase()
          .includes(normalizedSearch);
      const matchesService = activeCategory !== "Transporte" || service === "Todos" || listing.service === service;
      const matchesPrice = !maxPrice || listing.price <= parsedMax;
      return matchesSearch && matchesService && matchesPrice;
    });
  }, [activeCategory, baseListings, maxPrice, search, service]);

  function changeCategory(category: Category) {
    setActiveCategory(category);
    setService("Todos");
    setSearch("");
    setShowMenu(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function toggleFavorite(id: number) {
    setFavorites((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
    setNotice(favorites.includes(id) ? "Quitado de tus favoritos" : "Guardado en tus favoritos");
    window.setTimeout(() => setNotice(""), 2200);
  }

  function openPlans() {
    setShowMenu(false);
    setShowPlans(true);
  }

  return (
    <main className="site-shell">
      <header className="topbar">
        <button className="brand" onClick={() => changeCategory("Roomies")} aria-label="Ir al inicio">
          <span className="brand-mark"><Icon name="⌂" /></span>
          <span>depitass</span>
        </button>

        <nav className="category-nav" aria-label="Categorías principales">
          {categories.map((category) => (
            <button
              key={category.id}
              className={`category-tab ${activeCategory === category.id ? "active" : ""}`}
              onClick={() => changeCategory(category.id)}
            >
              <span className={`category-icon ${category.id.toLowerCase()}`}><Icon name={category.icon} /></span>
              <span className="category-tab-copy">
                <strong>{category.label}</strong>
                <small>{category.description}</small>
              </span>
            </button>
          ))}
        </nav>

        <div className="top-actions">
          <button className="announce-link" onClick={() => setShowPublish(true)}>Anuncia</button>
          <button className="round-utility" aria-label="Cambiar idioma">◎</button>
          <button
            className="menu-trigger"
            aria-label="Abrir menú"
            aria-expanded={showMenu}
            onClick={() => setShowMenu((open) => !open)}
          >
            <span /><span /><span />
          </button>
        </div>

        {showMenu && (
          <div className="menu-popover">
            <div className="menu-profile">
              <span className="avatar">D</span>
              <div><strong>Bienvenido a depitass</strong><small>Encuentra o publica sin comisiones</small></div>
            </div>
            <button onClick={() => { setShowLogin(true); setShowMenu(false); }}><Icon name="↗" /> Iniciar sesión</button>
            <button onClick={openPlans}><Icon name="▣" /> Ver planes para publicar</button>
            <button onClick={() => { setShowPublish(true); setShowMenu(false); }}><Icon name="＋" /> Publicar un espacio</button>
            <button onClick={() => { setNotice(`${favorites.length} favoritos guardados en este dispositivo`); setShowMenu(false); }}><Icon name="♡" /> Mis favoritos <span className="menu-count">{favorites.length}</span></button>
            <div className="menu-divider" />
            <button onClick={() => setNotice("Te ayudamos por WhatsApp: +51 999 888 777")}><Icon name="?" /> Centro de ayuda</button>
          </div>
        )}
      </header>

      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-dot" /> {currentCategory.kicker}</div>
          <h1>{currentCategory.title}</h1>
          <p>{currentCategory.body}</p>
          <div className="trust-row"><span>✓ Propietarios verificados</span><span>✓ Trato directo</span><span>✓ Sin comisiones extras</span></div>
        </div>

        <div className="hero-art" aria-label="Collage de espacios y transporte">
          <div className="hero-note"><span>✦</span><strong>Tu lugar<br />empieza aquí</strong></div>
          <div className="art-main"><img src="https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=900&q=85" alt="Sala luminosa" /></div>
          <div className="art-small"><img src="https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=500&q=85" alt="Habitación acogedora" /></div>
          <div className="art-sticker">directo<br /><em>al dueño</em></div>
        </div>

        <div className="search-panel" role="search">
          <label className="search-field search-location">
            <span className="search-icon"><Icon name="⌖" /></span>
            <span><small>Ubicación</small><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={currentCategory.search} /></span>
          </label>
          <label className="search-field">
            <span className="search-icon"><Icon name="◷" /></span>
            <span><small>{activeCategory === "Airbnb" ? "Fechas" : activeCategory === "Transporte" ? "Servicio" : "Duración"}</small><input readOnly value={activeCategory === "Airbnb" ? "19 – 20 ago" : activeCategory === "Transporte" ? "Para hoy o cuando quieras" : "Desde un mes"} /></span>
          </label>
          <label className="search-field search-guests">
            <span className="search-icon"><Icon name="♧" /></span>
            <span><small>{activeCategory === "Transporte" ? "Carga / pasajeros" : "Personas"}</small><input readOnly value={activeCategory === "Transporte" ? "Seleccionar tipo" : "2 huéspedes"} /></span>
          </label>
          <button className="search-submit" onClick={() => document.getElementById("explore")?.scrollIntoView({ behavior: "smooth" })} aria-label="Buscar"><Icon name="⌕" /></button>
        </div>
      </section>

      <section className="content-wrap" id="explore">
        <div className="section-heading">
          <div>
            <span className="section-kicker">Explora {activeCategory.toLowerCase()}</span>
            <h2>{activeCategory === "Transporte" ? "Servicios listos para moverse contigo" : "Lugares que podrían gustarte"}</h2>
          </div>
          <button className="filter-button" onClick={() => setShowFilters(true)}><Icon name="≡" /> Filtros <span className="filter-dot" /></button>
        </div>

        {activeCategory === "Transporte" && (
          <div className="service-switcher" aria-label="Filtrar transporte">
            {["Todos", "Mudanza", "Corporativo"].map((item) => <button key={item} className={service === item ? "selected" : ""} onClick={() => setService(item)}>{item === "Todos" ? "Todos los servicios" : item}</button>)}
          </div>
        )}

        <div className="result-line"><span>{isLoading ? "Buscando opciones…" : `${visibleListings.length} opciones encontradas`}</span><button onClick={() => setNotice("Ordenado por recomendados")}>Recomendados <Icon name="⌄" /></button></div>

        {visibleListings.length > 0 ? (
          <div className="listing-grid">
            {visibleListings.map((listing) => (
              <article key={listing.id} className="listing-card" onClick={() => setSelectedListing(listing)}>
                <div className="listing-image-wrap">
                  <img src={`${listing.image}?auto=format&fit=crop&w=900&q=85`} alt={listing.title} className="listing-image" />
                  {listing.badge && <span className="listing-badge">{listing.badge}</span>}
                  <button className={`favorite-button ${favorites.includes(listing.id) ? "is-favorite" : ""}`} onClick={(event) => { event.stopPropagation(); toggleFavorite(listing.id); }} aria-label={favorites.includes(listing.id) ? "Quitar de favoritos" : "Guardar en favoritos"}>{favorites.includes(listing.id) ? "♥" : "♡"}</button>
                  {listing.gallery?.length > 1 && <div className="image-dots"><span className="active" /><span /><span /><span /></div>}
                </div>
                <div className="listing-content">
                  <div className="listing-title-row"><h3>{listing.title}</h3><span className="rating">★ {listing.rating.toFixed(1)} <small>({listing.reviews})</small></span></div>
                  <p className="listing-location">{listing.location}</p>
                  <p className="listing-meta">{listing.meta}</p>
                  <div className="listing-bottom"><div><strong>{money.format(listing.price)}</strong> <span>{listing.priceLabel}</span></div><a className="whatsapp-button" href={whatsappLink(listing)} onClick={(event) => event.stopPropagation()} target="_blank" rel="noreferrer" aria-label={`Contactar a ${listing.ownerName} por WhatsApp`}><span>◔</span><small>WhatsApp</small></a></div>
                  <div className="direct-note">Contacto directo con {listing.ownerName} · sin comisiones extras</div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state"><span>⌂</span><h3>No encontramos resultados con esos filtros.</h3><p>Prueba con otra ubicación o amplía tu presupuesto.</p><button className="primary-button" onClick={() => { setSearch(""); setMaxPrice(""); setService("Todos"); }}>Limpiar filtros</button></div>
        )}
      </section>

      <section className="owner-cta">
        <div className="owner-cta-copy"><span className="eyebrow light"><span className="eyebrow-dot" /> Para propietarios y afiliados</span><h2>Publica una vez.<br /><em>Nosotros llevamos el tráfico.</em></h2><p>Tu anuncio aparece frente a personas que sí están buscando. Tú conversas, decides y cierras directo.</p><button className="light-button" onClick={() => setShowPublish(true)}>Quiero publicar <span>→</span></button></div>
        <div className="owner-cta-visual"><div className="cta-orbit orbit-one" /><div className="cta-orbit orbit-two" /><div className="cta-card"><span className="cta-card-icon">✦</span><strong>Sin comisiones<br />por reserva</strong><small>Solo un plan anual simple</small></div><div className="cta-mini">más clientes<br /><strong>+ directo</strong></div></div>
      </section>

      <section className="plans-section" id="planes">
        <div className="plans-intro"><span className="section-kicker">Planes para anunciar</span><h2>Tu anuncio merece<br /><em>ser encontrado.</em></h2><p>Una tarifa anual clara por publicación. Sin cobros ocultos, sin comisiones por cada contacto.</p><button className="text-button" onClick={() => setShowPlans(true)}>Ver todos los beneficios <span>→</span></button></div>
        <div className="plans-grid">{plans.map((plan) => <button key={plan.name} className="plan-card" onClick={() => setShowPlans(true)}><span className={`plan-icon ${plan.tone}`}>{plan.icon}</span><span className="plan-name">{plan.name}</span><strong>{plan.price}</strong><span className="plan-detail">{plan.detail}</span><span className="plan-arrow">↗</span></button>)}</div>
      </section>

      <footer className="footer"><div className="footer-brand"><span className="brand-mark"><Icon name="⌂" /></span><span><strong>depitass</strong><small>Un lugar para cada historia.</small></span></div><div className="footer-links"><span>© 2026 depitass</span><button onClick={() => setNotice("Próximamente: términos y privacidad")}>Términos y privacidad</button><button onClick={() => setNotice("Soporte directo: hola@depitass.com")}>Contacto</button></div><div className="footer-social"><span>ig</span><span>fb</span><span>wa</span></div></footer>

      {notice && <div className="toast" role="status"><span>✓</span>{notice}</div>}

      {showFilters && <div className="modal-backdrop" onClick={() => setShowFilters(false)}><div className="modal filters-modal" onClick={(event) => event.stopPropagation()}><div className="modal-header"><div><span className="section-kicker">Personaliza tu búsqueda</span><h2>Filtros</h2></div><button className="close-button" onClick={() => setShowFilters(false)} aria-label="Cerrar filtros">×</button></div><label className="modal-label">Presupuesto máximo <div className="price-input"><span>S/</span><input type="number" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} placeholder="Sin límite" /></div></label><div className="modal-label">Zona o palabra clave<input className="full-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Ej. Miraflores, equipado…" /></div>{activeCategory === "Transporte" && <div className="modal-label">Tipo de servicio<div className="modal-options">{["Todos", "Mudanza", "Corporativo"].map((item) => <button key={item} className={service === item ? "selected" : ""} onClick={() => setService(item)}>{item}</button>)}</div></div>}<button className="primary-button wide" onClick={() => setShowFilters(false)}>Ver resultados</button></div></div>}

      {showPlans && <div className="modal-backdrop" onClick={() => setShowPlans(false)}><div className="modal plans-modal" onClick={(event) => event.stopPropagation()}><div className="modal-header"><div><span className="section-kicker">Publica con depitass</span><h2>Planes simples, alcance real.</h2></div><button className="close-button" onClick={() => setShowPlans(false)} aria-label="Cerrar planes">×</button></div><p className="modal-lead">Nosotros llevamos tráfico a la plataforma. Tú recibes consultas y tratas directamente con el cliente, sin comisiones extras.</p><div className="plans-modal-grid">{plans.map((plan) => <div key={plan.name} className={`modal-plan ${plan.tone}`}><span className="plan-icon">{plan.icon}</span><div><strong>{plan.name}</strong><p>{plan.detail}</p></div><b>{plan.price}</b></div>)}</div><div className="benefit-list"><span>✓ Publicación durante 12 meses</span><span>✓ Visibilidad frente a nuevos clientes</span><span>✓ Contacto directo con el propietario</span><span>✓ Sin comisión por reserva o contacto</span></div><button className="primary-button wide" onClick={() => { setShowPlans(false); setShowPublish(true); }}>Elegir un plan y publicar</button></div></div>}

      {showLogin && <div className="modal-backdrop" onClick={() => setShowLogin(false)}><div className="modal login-modal" onClick={(event) => event.stopPropagation()}><button className="close-button" onClick={() => setShowLogin(false)} aria-label="Cerrar inicio de sesión">×</button><div className="login-mark"><Icon name="⌂" /></div><span className="section-kicker">Tu cuenta depitass</span><h2>Guarda tus favoritos y publica tus espacios.</h2><p>Inicia sesión de forma segura para gestionar anuncios y consultas desde un solo lugar.</p><a className="primary-button wide" href="/signin-with-chatgpt?return_to=%2F">Iniciar sesión con ChatGPT <span>→</span></a><small className="login-footnote">Al continuar aceptas nuestros términos de uso.</small></div></div>}

      {showPublish && <PublishModal category={activeCategory} onClose={() => setShowPublish(false)} onCreated={(listing) => { setListingsFromDb((current) => [listing, ...current]); setActiveCategory(listing.category); setShowPublish(false); setNotice("Tu publicación fue guardada. ¡Ya puedes compartirla!"); }} />}

      {selectedListing && <div className="modal-backdrop" onClick={() => setSelectedListing(null)}><div className="modal detail-modal" onClick={(event) => event.stopPropagation()}><button className="close-button detail-close" onClick={() => setSelectedListing(null)} aria-label="Cerrar detalle">×</button><img src={`${selectedListing.image}?auto=format&fit=crop&w=1200&q=90`} alt={selectedListing.title} /><div className="detail-body"><div className="listing-title-row"><div><span className="section-kicker">{selectedListing.category}</span><h2>{selectedListing.title}</h2></div><span className="rating">★ {selectedListing.rating.toFixed(1)} ({selectedListing.reviews})</span></div><p className="listing-location">{selectedListing.location}</p><p className="detail-description">{selectedListing.description}</p><div className="detail-pills"><span>✓ Publicación verificada</span><span>✓ Trato directo</span><span>✓ Sin comisiones extras</span></div><div className="detail-contact"><div><small>Desde</small><strong>{money.format(selectedListing.price)} <em>{selectedListing.priceLabel}</em></strong></div><a className="primary-button" href={whatsappLink(selectedListing)} target="_blank" rel="noreferrer">Contactar por WhatsApp <span>↗</span></a></div></div></div></div>}
    </main>
  );
}

function PublishModal({ category, onClose, onCreated }: { category: Category; onClose: () => void; onCreated: (listing: Listing) => void }) {
  const [form, setForm] = useState({ title: "", location: "", price: "", description: "", ownerName: "", ownerWhatsApp: "" });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    try {
      const response = await fetch("/api/listings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, category, price: Number(form.price), priceLabel: category === "Airbnb" ? "por noche" : category === "Transporte" ? "por servicio" : "por mes" }) });
      const payload = (await response.json()) as { listing?: Listing; error?: string };
      if (!response.ok || !payload.listing) throw new Error(payload.error ?? "No se pudo guardar la publicación");
      onCreated(payload.listing);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Revisa los datos e intenta otra vez.");
    } finally {
      setIsSaving(false);
    }
  }

  return <div className="modal-backdrop" onClick={onClose}><div className="modal publish-modal" onClick={(event) => event.stopPropagation()}><div className="modal-header"><div><span className="section-kicker">Publicar {category.toLowerCase()}</span><h2>Haz que te encuentren.</h2></div><button className="close-button" onClick={onClose} aria-label="Cerrar publicación">×</button></div><p className="modal-lead">Completa los datos esenciales. Después podrás coordinar directamente con cada cliente.</p><form onSubmit={submit}><div className="form-grid"><label>Título<input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ej. Habitación luminosa en Barranco" /></label><label>Ubicación<input required value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Distrito, ciudad" /></label><label>Precio en soles<input required min="1" type="number" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="450" /></label><label>Tu nombre<input required value={form.ownerName} onChange={(event) => setForm({ ...form, ownerName: event.target.value })} placeholder="Cómo te conocerán" /></label></div><label>Descripción<textarea required rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Cuenta lo que hace especial a tu espacio o servicio…" /></label><label>WhatsApp de contacto<input required value={form.ownerWhatsApp} onChange={(event) => setForm({ ...form, ownerWhatsApp: event.target.value })} placeholder="51999888777" /></label>{error && <p className="form-error">{error}</p>}<button className="primary-button wide" disabled={isSaving}>{isSaving ? "Guardando publicación…" : "Guardar y publicar"}<span>→</span></button><small className="form-footnote">Al publicar, tu anuncio queda listo para ser revisado y recibir tráfico.</small></form></div></div>;
}
