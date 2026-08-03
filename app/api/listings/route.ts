import { desc, eq } from "drizzle-orm";
import { getDb, getRawDb } from "../../../db";
import { listings } from "../../../db/schema";
import { demoListings, type Category } from "../../data";

const categories = new Set<Category>(["Roomies", "Depas", "Airbnb", "Transporte"]);

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
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)`;

async function getListingsDb() {
  const rawDb = getRawDb();
  await rawDb.prepare(listingsTableSql).run();
  await rawDb.prepare("CREATE INDEX IF NOT EXISTS idx_listings_category_created_at ON listings (category, created_at)").run();
  return getDb();
}

function serializeListing(row: typeof listings.$inferSelect) {
  let gallery: string[] = [];
  try {
    gallery = JSON.parse(row.gallery) as string[];
  } catch {
    gallery = [];
  }
  return { ...row, gallery };
}

function routeError(error: unknown) {
  const message = error instanceof Error ? error.message : "Unexpected error";
  if (message.includes("no such table")) return "La base está configurada, pero falta aplicar la migración de publicaciones.";
  return "No pudimos conectar con la base de publicaciones.";
}

export async function GET(request: Request) {
  const categoryParam = new URL(request.url).searchParams.get("category");
  const category = categories.has(categoryParam as Category) ? categoryParam as Category : null;
  try {
    const db = await getListingsDb();
    const rows = await db.select().from(listings).where(category ? eq(listings.category, category) : undefined).orderBy(desc(listings.createdAt), desc(listings.id)).limit(48);
    const result = rows.length ? rows.map(serializeListing) : demoListings.filter((listing) => !category || listing.category === category);
    return Response.json({ listings: result, source: rows.length ? "database" : "demo" });
  } catch (error) {
    return Response.json({ listings: demoListings.filter((listing) => !category || listing.category === category), source: "demo", warning: routeError(error) });
  }
}

export async function POST(request: Request) {
  try {
    const payload = await request.json() as Partial<{
      category: Category;
      title: string;
      location: string;
      description: string;
      price: number;
      priceLabel: string;
      ownerName: string;
      ownerWhatsApp: string;
    }>;
    const category = payload.category;
    const title = payload.title?.trim() ?? "";
    const location = payload.location?.trim() ?? "";
    const description = payload.description?.trim() ?? "";
    const ownerName = payload.ownerName?.trim() ?? "";
    const ownerWhatsApp = payload.ownerWhatsApp?.replace(/[^\d]/g, "") ?? "";
    const price = Number(payload.price);
    if (!category || !categories.has(category) || !title || !location || !description || !ownerName || !ownerWhatsApp || !Number.isFinite(price) || price <= 0) {
      return Response.json({ error: "Completa todos los campos obligatorios." }, { status: 400 });
    }
    const db = await getListingsDb();
    const [created] = await db.insert(listings).values({ category, title, location, description, image: "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c", gallery: "[]", price: Math.round(price), priceLabel: payload.priceLabel?.trim() || "por servicio", rating: 5, reviews: 0, meta: "Publicación nueva · Contacto directo", ownerName, ownerWhatsApp }).returning();
    return Response.json({ listing: serializeListing(created) }, { status: 201 });
  } catch (error) {
    return Response.json({ error: routeError(error) }, { status: 500 });
  }
}
