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
  assert.match(page, /className="host-link login-link" onClick={openLogin}/);
  assert.match(page, /login-google-badge/);
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
