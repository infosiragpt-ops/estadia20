import { and, asc, eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { ensureDatabase } from "../../../db/ensure";
import { favorites } from "../../../db/schema";
import { attachVisitorCookie, getVisitor } from "../visitor";

export async function GET(request: Request) {
  try {
    const visitor = getVisitor(request);
    await ensureDatabase();
    const rows = await getDb().select({ listingId: favorites.listingId }).from(favorites).where(eq(favorites.visitorId, visitor.visitorId)).orderBy(asc(favorites.createdAt));
    return attachVisitorCookie(Response.json({ favorites: rows.map((row) => row.listingId) }), visitor.visitorId, visitor.isNew);
  } catch {
    return Response.json({ error: "No se pudieron leer tus favoritos." }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const visitor = getVisitor(request);
    const payload = await request.json() as { listingId?: number };
    const listingId = Number(payload.listingId);
    if (!Number.isInteger(listingId) || listingId <= 0) return Response.json({ error: "Publicación inválida." }, { status: 400 });
    await ensureDatabase();
    await getDb().insert(favorites).values({ visitorId: visitor.visitorId, listingId }).onConflictDoNothing();
    return attachVisitorCookie(Response.json({ saved: true }), visitor.visitorId, visitor.isNew);
  } catch {
    return Response.json({ error: "No se pudo guardar el favorito." }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const visitor = getVisitor(request);
    const payload = await request.json() as { listingId?: number };
    const listingId = Number(payload.listingId);
    if (!Number.isInteger(listingId) || listingId <= 0) return Response.json({ error: "Publicación inválida." }, { status: 400 });
    await ensureDatabase();
    await getDb().delete(favorites).where(and(eq(favorites.visitorId, visitor.visitorId), eq(favorites.listingId, listingId)));
    return attachVisitorCookie(Response.json({ saved: false }), visitor.visitorId, visitor.isNew);
  } catch {
    return Response.json({ error: "No se pudo actualizar el favorito." }, { status: 500 });
  }
}
