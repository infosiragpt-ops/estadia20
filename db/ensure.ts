import { getRawDb } from ".";

const listingsTableSql = `CREATE TABLE IF NOT EXISTS listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
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
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)`;

const favoritesTableSql = `CREATE TABLE IF NOT EXISTS favorites (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  visitor_id TEXT NOT NULL,
  listing_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)`;

const inquiriesTableSql = `CREATE TABLE IF NOT EXISTS inquiries (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  visitor_id TEXT NOT NULL,
  listing_id INTEGER NOT NULL,
  channel TEXT NOT NULL DEFAULT 'whatsapp',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)`;

export async function ensureDatabase() {
  const rawDb = getRawDb();
  await rawDb.batch([
    rawDb.prepare(listingsTableSql),
    rawDb.prepare(favoritesTableSql),
    rawDb.prepare(inquiriesTableSql),
    rawDb.prepare("CREATE INDEX IF NOT EXISTS idx_listings_category_created_at ON listings (category, created_at)"),
    rawDb.prepare("CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_visitor_listing ON favorites (visitor_id, listing_id)"),
    rawDb.prepare("CREATE INDEX IF NOT EXISTS idx_inquiries_listing_created_at ON inquiries (listing_id, created_at)"),
  ]);
  const listingColumns = await rawDb.prepare("PRAGMA table_info(listings)").all<{ name: string }>();
  if (!listingColumns.results.some((column: { name: string }) => column.name === "details_json")) {
    await rawDb.prepare("ALTER TABLE listings ADD COLUMN details_json TEXT NOT NULL DEFAULT '{}'").run();
  }
  await rawDb.prepare("PRAGMA optimize").run();
}
