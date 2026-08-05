import { getDb } from "../../../db";
import { ensureDatabase } from "../../../db/ensure";
import { inquiries } from "../../../db/schema";
import { attachVisitorCookie, getVisitor } from "../visitor";

export async function POST(request: Request) {
  try {
    const visitor = getVisitor(request);
    const payload = await request.json() as { listingId?: number; channel?: string };
    const listingId = Number(payload.listingId);
    if (!Number.isInteger(listingId) || listingId <= 0) return Response.json({ error: "Publicación inválida." }, { status: 400 });
    await ensureDatabase();
    await getDb().insert(inquiries).values({ visitorId: visitor.visitorId, listingId, channel: payload.channel === "whatsapp" ? "whatsapp" : "direct" });
    return attachVisitorCookie(Response.json({ recorded: true }, { status: 201 }), visitor.visitorId, visitor.isNew);
  } catch {
    return Response.json({ error: "No se pudo registrar el contacto." }, { status: 500 });
  }
}
