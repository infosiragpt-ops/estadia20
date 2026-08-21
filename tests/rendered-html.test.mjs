import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("ships the finished estadia20 marketplace", async () => {
  const [page, layout, styles, packageJson] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/layout.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
    readFile(new URL("package.json", root), "utf8"),
  ]);

  assert.match(layout, /Llaves365 — encuentra tu próximo lugar/);
  assert.match(page, /Roomies/);
  assert.match(page, /Depas/);
  assert.match(page, /Estadías/);
  assert.match(page, /Transporte/);
  assert.match(page, /Iniciar sesión/);
  assert.match(page, /AdminPanelModal/);
  assert.match(page, /api\/admin\/overview/);
  assert.match(page, /api\/my\/listings/);
  assert.match(page, /Ver planes/);
  assert.match(page, /https:\/\/wa\.me\//);
  assert.match(page, /results-toolbar/);
  assert.match(page, /ListingSkeleton/);
  assert.match(page, /If-None-Match/);
  assert.match(page, /useDeferredValue/);
  assert.match(page, /aria-live="polite"/);
  assert.match(page, /SwipeGallery/);
  assert.match(page, /detail-swipe-gallery/);
  // La cabecera es para el acceso: «Iniciar sesión» con la G de Google para
  // visitantes y la cuenta activa con sesión. Publicar vive en el menú
  // (hamburguesa) y en el pie.
  assert.match(page, /className="host-link login-link" onClick={openLogin} aria-label="Iniciar sesión"/);
  assert.match(page, /login-google-badge/);
  assert.match(page, /className="login-label"/);
  assert.match(page, /className="host-link account-link" onClick={openLogin}/);
  assert.doesNotMatch(page, /className="host-link" onClick={requestPublish}/);
  assert.match(page, /onClick={requestPublish}>Publicar un anuncio</);
  // «Mis favoritos» abre una lista real con los anuncios guardados.
  assert.match(page, /favorites-modal/);
  assert.match(page, /api\/favorites\/listings/);
  assert.match(page, /Todavía no guardaste favoritos\. Toca el corazón en un anuncio para guardarlo\./);
  assert.match(page, /Entra con Google para no perderlos en otro teléfono\./);
  assert.doesNotMatch(page, /favoritos guardados`\)/);
  assert.match(page, /footer-publish-card/);
  assert.match(page, /footer-publish-primary/);
  assert.match(page, /llaves365-google-nudge/);
  assert.match(page, /google-nudge-banner/);
  assert.match(page, /Entra con Google para guardar favoritos y publicar\./);
  assert.match(page, /Inicia sesión con Google para no perder tus favoritos\./);
  // Las fotos del anuncio se previsualizan en local y se suben al guardar.
  assert.match(page, /Preparando fotos…/);
  assert.match(page, /photo-error/);
  // La vista previa local usa data: URLs (FileReader), que la CSP ya permite;
  // los blob: de createObjectURL podían quedar en blanco en el teléfono.
  assert.match(page, /readAsDataURL/);
  assert.doesNotMatch(page, /URL\.createObjectURL/);
  // El detalle abierto vive en la URL (?listing=ID) y se puede compartir;
  // atrás/adelante lo cierran y reabren por historial.
  assert.match(page, /parameters\.set\("listing", String\(listing\.id\)\)/);
  assert.match(page, /window\.addEventListener\("popstate"/);
  assert.match(page, /\/api\/listings\/\$\{id\}/);
  // La pestaña pública «Estadías» se comparte con ese nombre en la URL.
  assert.match(page, /categoryUrlAliases/);
  // Los anuncios sembrados se muestran como «Ejemplo»: sin valoraciones
  // inventadas y sin botón real de WhatsApp.
  assert.match(page, /demo-badge/);
  assert.match(page, /whatsapp-demo/);
  assert.match(page, /Anuncio de ejemplo/);
  assert.match(styles, /\.listing-badge\.demo-badge/);
  assert.match(styles, /\.rating-note/);
  assert.match(styles, /\.whatsapp-card\.whatsapp-demo/);
  assert.match(styles, /\.host-link/);
  assert.match(styles, /\.login-google-badge/);
  // Chip de cabecera compacto (no crece con clamp) y avatar acotado al
  // botón de cuenta, para que el retrato del modal no lo agrande.
  assert.match(styles, /\.host-link \{[^}]*height: 40px;/);
  assert.match(styles, /\.host-link \{[^}]*font-size: 13\.5px;/);
  assert.doesNotMatch(styles, /\.host-link \{[^}]*font-size: clamp\(/);
  assert.match(styles, /\.menu-trigger \{[^}]*height: 40px;/);
  assert.doesNotMatch(styles, /\.menu-trigger \{[^}]*clamp\(48px/);
  assert.match(styles, /\.account-link \.account-avatar, \.account-link \.account-initial \{ width: 30px; height: 30px;/);
  assert.match(styles, /\.login-modal > \.account-avatar \{ width: 64px; height: 64px;/);
  assert.doesNotMatch(styles, /\.account-avatar \{ width: 58px;/);
  assert.match(styles, /\.google-cta \{ width: 100%; height: 40px;/);
  assert.match(styles, /\.google-cta-button \{[^}]*font-size: 14px;/);
  assert.match(styles, /\.login-modal \.primary-button \{ font-size: 14px; \}/);
  assert.match(styles, /\.account-name \{ display: none; \}/);
  assert.match(styles, /\.login-label \{ display: none; \}/);
  assert.match(styles, /\.favorite-row/);
  assert.match(styles, /\.favorites-empty/);
  assert.match(styles, /\.footer-publish-card/);
  assert.match(styles, /\.google-nudge-banner/);
  assert.match(styles, /\.photo-error/);
  assert.match(styles, /\.results-error/);
  assert.match(styles, /prefers-reduced-motion/);
  assert.match(styles, /\.listing-grid/);
  assert.match(styles, /scroll-snap-type: x mandatory/);
  assert.doesNotMatch(page, /traffic-banner/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);

  await assert.rejects(access(new URL("app/_sites-preview", root)));
});

test("enlaza el Facebook oficial y el contacto por WhatsApp del administrador", async () => {
  const [page, styles] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
  ]);

  // La página oficial de Facebook, con nombre accesible en español.
  assert.match(page, /https:\/\/www\.facebook\.com\/profile\.php\?id=61592602154789/);
  assert.match(page, /Facebook de \$\{BRAND\}/);
  // «Contacto» abre el WhatsApp del administrador (celular de Perú), no un
  // aviso pasajero ni un correo.
  assert.match(page, /https:\/\/wa\.me\/51918714054/);
  assert.match(page, /Hola, les escribo desde llaves365\.com/);
  assert.doesNotMatch(page, /onClick=\{\(\) => flashNotice\(`Soporte: \$\{SUPPORT_EMAIL\}`\)\}>Contacto</);
  // Ambos enlaces abren en pestaña nueva sin filtrar el opener.
  assert.match(page, /href=\{FACEBOOK_PAGE_URL\} target="_blank" rel="noopener noreferrer"/);
  assert.match(page, /href=\{CONTACT_WHATSAPP_URL\} target="_blank" rel="noopener noreferrer"/);
  assert.match(styles, /\.footer-social/);
  assert.match(styles, /\.social-link \{ min-height: 44px;/);

  // Y en el bundle de producción ya compilado que sirve el VPS.
  const html = await readFile(new URL("vps/public/index.html", root), "utf8");
  const scriptPath = html.match(/assets\/index-[\w-]+\.js/)?.[0];
  assert.ok(scriptPath, "vps/public/index.html debe referenciar el bundle JS");
  const bundle = await readFile(new URL(`vps/public/${scriptPath}`, root), "utf8");
  assert.ok(bundle.includes("https://www.facebook.com/profile.php?id=61592602154789"));
  assert.ok(bundle.includes("https://wa.me/51918714054"));
  const cssPath = html.match(/assets\/index-[\w-]+\.css/)?.[0];
  assert.ok(cssPath, "vps/public/index.html debe referenciar el bundle CSS");
  const css = await readFile(new URL(`vps/public/${cssPath}`, root), "utf8");
  assert.ok(css.includes(".account-link .account-avatar"), "el chip de cuenta debe acotar el avatar");
  assert.ok(css.includes(".login-modal>.account-avatar") || css.includes(".login-modal > .account-avatar"), "el avatar del modal no debe filtrarse a la cabecera");
  assert.ok(!css.includes("font-size:clamp(14px, 1vw, 20px)"));
});

test("keeps database, uploads, favorites, and inquiries deployable", async () => {
  const [hosting, schema, listings, favorites, inquiries, uploads] = await Promise.all([
    readFile(new URL(".openai/hosting.json", root), "utf8"),
    readFile(new URL("db/schema.ts", root), "utf8"),
    readFile(new URL("app/api/listings/route.ts", root), "utf8"),
    readFile(new URL("app/api/favorites/route.ts", root), "utf8"),
    readFile(new URL("app/api/inquiries/route.ts", root), "utf8"),
    readFile(new URL("app/api/uploads/route.ts", root), "utf8"),
  ]);

  assert.match(hosting, /"d1": "DB"/);
  assert.match(hosting, /"r2": "UPLOADS"/);
  assert.match(schema, /sqliteTable\("listings"/);
  assert.match(schema, /sqliteTable\("favorites"/);
  assert.match(schema, /sqliteTable\("inquiries"/);
  assert.match(listings, /export async function POST/);
  assert.match(favorites, /export async function POST/);
  assert.match(inquiries, /export async function POST/);
  assert.match(uploads, /UPLOADS/);
});

test("ola 1: compartir, legal, HEIC, WhatsApp protegido y ciclo de vida", async () => {
  const [page, styles, server, nginx, indexHtml, workflow, packageJson] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
    readFile(new URL("vps/server.py", root), "utf8"),
    readFile(new URL("vps/estadia20.nginx", root), "utf8"),
    readFile(new URL("vps/index.html", root), "utf8"),
    readFile(new URL(".github/workflows/deploy-production.yml", root), "utf8"),
    readFile(new URL("package.json", root), "utf8"),
  ]);

  // A. Compartir: Web Share API, copiar enlace y diálogo de Facebook.
  assert.match(page, /navigator\.share/);
  assert.match(page, /Copiar enlace/);
  assert.match(page, /facebook\.com\/sharer\/sharer\.php/);
  assert.match(page, /share-row/);
  assert.match(styles, /\.share-row/);

  // B. Legal: contenido real, aviso de cookies (Ley 29733) y sin correo
  // estadia20 visible para el visitante.
  assert.match(page, /Quiénes somos/);
  assert.match(page, /Centro de ayuda/);
  assert.match(page, /llaves365-cookie-consent/);
  assert.match(page, /Ley N\.º 29733/);
  assert.match(styles, /\.cookie-notice/);
  assert.doesNotMatch(page, /hola@estadia20\.com/);
  assert.doesNotMatch(page, /SUPPORT_EMAIL/);
  assert.match(page, /wa\.me\/51918714054/);

  // C. Fotos: HEIC/HEIF aceptados y casilla con `capture` para la cámara.
  assert.match(page, /image\/heic/);
  assert.match(page, /capture="environment"/);
  assert.match(server, /pillow_heif/);
  assert.match(server, /HEIC_MESSAGE/);

  // D. Filtros reales: fechas y huéspedes al servidor, filtros de Roomies y
  // comodidades de Estadías; sin fechas inventadas en las tarjetas.
  assert.doesNotMatch(page, /9–14 de ago/);
  assert.match(page, /Baño privado/);
  assert.match(page, /Servicios incluidos/);
  assert.match(page, /parameters\.set\("amenities"/);
  assert.match(server, /json_each\(details_json, '\$\.amenities'\)/);
  assert.match(server, /json_extract\(details_json, '\$\.bathroom'\)/);

  // E. El número del anunciante viaja enmascarado y se revela al consultar.
  assert.match(page, /revealWhatsApp/);
  assert.doesNotMatch(page, /wa\.me\/\$\{listing\.ownerWhatsApp\}/);
  assert.match(server, /masked_whatsapp/);
  assert.match(server, /ownerWhatsAppMasked/);

  // F. SEO: sitemap y robots reales, redirecciones 301 y JSON-LD con el
  // Facebook oficial (sin redes inventadas).
  assert.match(server, /def serve_sitemap/);
  assert.match(server, /def serve_robots/);
  assert.match(nginx, /return 301 https:\/\/llaves365\.com\$request_uri;/);
  assert.match(nginx, /www\.llaves365\.com estadia20\.com www\.estadia20\.com/);
  assert.match(indexHtml, /application\/ld\+json/);
  assert.match(indexHtml, /"sameAs": \["https:\/\/www\.facebook\.com\/profile\.php\?id=61592602154789"\]/);
  assert.doesNotMatch(indexHtml, /twitter\.com|instagram\.com/);

  // G. Cuentas: recuperar contraseña, cerrar sesión en todos los equipos y
  // Google ya no borra la contraseña.
  assert.match(page, /¿Olvidaste tu contraseña\?/);
  assert.match(page, /Cerrar sesión en todos los equipos/);
  assert.match(server, /password_resets/);
  assert.match(server, /logout_all_sessions/);
  assert.doesNotMatch(server, /password_hash = ''\n/);

  // H. Ciclo de vida del anuncio y panel.
  assert.match(page, /listingStatusLabels/);
  assert.match(page, /En revisión/);
  assert.match(server, /LISTING_STATUSES/);
  assert.match(server, /"published" if is_admin else "pending"/);

  // I/J/K. Fotos ligadas a la cuenta, reportes, validación peruana y salud.
  assert.match(server, /cleanup_orphan_uploads/);
  assert.match(server, /delete_upload_files/);
  assert.match(page, /Reportar anuncio/);
  assert.match(server, /def create_report/);
  assert.match(server, /normalize_peru_whatsapp/);
  assert.match(server, /uploadsFreeBytes/);

  // El control falso de idioma/moneda ya no existe.
  assert.doesNotMatch(page, /GlobeIcon/);

  // Las pruebas nuevas corren en el despliegue y en npm test.
  assert.match(workflow, /tests\.test_wave1_api/);
  assert.match(packageJson, /tests\.test_wave1_api/);
});

test("hardens the VPS marketplace API", async () => {
  const [server, nginx, workflow] = await Promise.all([
    readFile(new URL("vps/server.py", root), "utf8"),
    readFile(new URL("vps/estadia20.nginx", root), "utf8"),
    readFile(new URL(".github/workflows/deploy-production.yml", root), "utf8"),
  ]);

  assert.match(server, /def listings_query/);
  // Aliases públicos: ?category=Estadías y ?sort=price siguen funcionando.
  assert.match(server, /CATEGORY_ALIASES/);
  assert.match(server, /LISTING_SORT_ALIASES/);
  assert.match(server, /def get_listing/);
  assert.match(server, /isDemo/);
  assert.match(server, /search_matches/);
  assert.match(server, /RATE_LIMIT_RULES/);
  assert.match(server, /image_extension_from_content/);
  assert.match(server, /listing_not_found/);
  assert.match(server, /\/api\/favorites\/listings/);
  assert.match(server, /stale-while-revalidate/);
  assert.match(server, /carrerajorge874@gmail\.com/);
  assert.match(server, /def require_admin/);
  assert.match(workflow, /tests\.test_admin_api/);
  assert.match(nginx, /Content-Security-Policy/);
  // img-src permite blob: además de data: para las vistas previas locales.
  assert.match(nginx, /img-src 'self' data: blob:/);
  assert.match(workflow, /tests\.test_marketplace_api/);
});

test("el acceso con Google conserva la sesión del sitio y no cierra Google", async () => {
  const [page, server, html] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("vps/server.py", root), "utf8"),
    readFile(new URL("vps/public/index.html", root), "utf8"),
  ]);

  // Cerrar sesión de Llaves365 solo borra la cookie del sitio. disableAutoSelect
  // + FedCM y revoke sacan a Luis de su cuenta de Google en el navegador.
  assert.doesNotMatch(page, /disableAutoSelect/);
  assert.doesNotMatch(page, /accounts\.id\.revoke/);
  assert.doesNotMatch(page, /google\.accounts\.id\.prompt\s*\(/);
  assert.doesNotMatch(page, /accounts\.google\.com\/Logout/);
  assert.match(page, /fetch\("\/api\/auth\/me", \{ credentials: "include" \}/);
  assert.match(page, /credentials: "include"/);
  assert.match(page, /\/api\/auth\/logout/);
  assert.match(page, /function startGoogleOAuthRedirect/);
  assert.match(page, /Accept: "application\/json"/);
  assert.match(page, /authorizeUrl/);
  assert.match(page, /accounts\.google\.com\/o\/oauth2\/v2\/auth\?/);

  assert.doesNotMatch(server, /["']prompt["']:\s*["'](select_account|consent|login)["']/);
  assert.doesNotMatch(server, /oauth2\/revoke/);
  assert.doesNotMatch(server, /accounts\.google\.com\/Logout/);
  assert.match(server, /def send_auth_bridge/);
  assert.match(server, /def cleared_session_cookie_headers/);
  assert.match(server, /SameSite=None/);

  const scriptPath = html.match(/assets\/index-[\w-]+\.js/)?.[0];
  assert.ok(scriptPath, "vps/public/index.html debe referenciar el bundle JS");
  const bundle = await readFile(new URL(`vps/public/${scriptPath}`, root), "utf8");
  assert.equal(bundle.includes("disableAutoSelect"), false);
  assert.equal(bundle.includes("accounts.id.revoke"), false);
});
