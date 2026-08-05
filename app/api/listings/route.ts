import { desc, eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { ensureDatabase } from "../../../db/ensure";
import { listings } from "../../../db/schema";
import { demoListings, type Category } from "../../data";

const categories = new Set<Category>(["Roomies", "Depas", "Airbnb", "Transporte"]);

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
    await ensureDatabase();
    const db = getDb();
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
      image: string;
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
    const image = payload.image?.trim() || "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c";
    if (!category || !categories.has(category) || !title || !location || !description || !ownerName || ownerWhatsApp.length < 8 || !Number.isFinite(price) || price <= 0) {
      return Response.json({ error: "Completa todos los campos obligatorios." }, { status: 400 });
    }
    if (!image.startsWith("/api/uploads/") && !image.startsWith("https://images.unsplash.com/")) {
      return Response.json({ error: "La fotografía no es válida." }, { status: 400 });
    }
    await ensureDatabase();
    const db = getDb();
    const [created] = await db.insert(listings).values({ category, title, location, description, image, gallery: JSON.stringify([image]), price: Math.round(price), priceLabel: payload.priceLabel?.trim() || "por servicio", rating: 5, reviews: 0, meta: "Publicación nueva · Contacto directo", ownerName, ownerWhatsApp }).returning();
    return Response.json({ listing: serializeListing(created) }, { status: 201 });
  } catch (error) {
    return Response.json({ error: routeError(error) }, { status: 500 });
  }
}
