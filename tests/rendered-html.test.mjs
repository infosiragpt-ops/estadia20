import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("ships the finished roomies20 marketplace", async () => {
  const [page, layout, styles, packageJson] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/layout.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
    readFile(new URL("package.json", root), "utf8"),
  ]);

  assert.match(layout, /roomies20 — encuentra tu próximo lugar/);
  assert.match(page, /Roomes/);
  assert.match(page, /Depas/);
  assert.match(page, /Arbnb/);
  assert.match(page, /Transporte/);
  assert.match(page, /Iniciar sesión/);
  assert.match(page, /Ver planes/);
  assert.match(page, /https:\/\/wa\.me\//);
  assert.match(styles, /\.listing-grid/);
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
