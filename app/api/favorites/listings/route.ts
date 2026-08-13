import { asc, eq } from "drizzle-orm";
import { getDb } from "../../../../db";
import { ensureDatabase } from "../../../../db/ensure";
import { favorites, listings } from "../../../../db/schema";
import type { DepaDetails } from "../../../data";
import { attachVisitorCookie, getVisitor } from "../../visitor";

function serializeListing(row: typeof listings.$inferSelect) {
  let gallery: string[] = [];
  let details: DepaDetails | undefined;
  try {
    gallery = JSON.parse(row.gallery) as string[];
  } catch {
    gallery = [];
  }
  try {
    details = JSON.parse(row.detailsJson) as DepaDetails;
  } catch {
    details = undefined;
  }
  const { detailsJson: _detailsJson, ...listing } = row;
  void _detailsJson;
  return { ...listing, gallery, details };
}

// Anuncios completos de los favoritos del visitante (cookie), en el orden en
// que se guardaron: alimenta la hoja «Mis favoritos» sin depender de qué
// categoría esté cargada en la portada.
export async function GET(request: Request) {
  try {
    const visitor = getVisitor(request);
    await ensureDatabase();
    const rows = await getDb()
      .select({ listing: listings })
      .from(favorites)
      .innerJoin(listings, eq(listings.id, favorites.listingId))
      .where(eq(favorites.visitorId, visitor.visitorId))
      .orderBy(asc(favorites.createdAt), asc(favorites.listingId));
    return attachVisitorCookie(
      Response.json({ listings: rows.map((row) => serializeListing(row.listing)) }),
      visitor.visitorId,
      visitor.isNew,
    );
  } catch {
    return Response.json({ error: "No se pudieron leer tus favoritos." }, { status: 500 });
  }
}
