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
  assert.match(server, /search_matches/);
  assert.match(server, /RATE_LIMIT_RULES/);
  assert.match(server, /image_extension_from_content/);
  assert.match(server, /listing_not_found/);
  assert.match(server, /stale-while-revalidate/);
  assert.match(server, /carrerajorge874@gmail\.com/);
  assert.match(server, /def require_admin/);
  assert.match(workflow, /tests\.test_admin_api/);
  assert.match(nginx, /Content-Security-Policy/);
  assert.match(workflow, /tests\.test_marketplace_api/);
});
