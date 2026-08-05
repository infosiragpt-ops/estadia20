import { env } from "cloudflare:workers";

type UploadEnvironment = { UPLOADS?: R2Bucket };

export async function GET(_request: Request, context: { params: Promise<{ date: string; key: string }> }) {
  const bucket = (env as unknown as UploadEnvironment).UPLOADS;
  if (!bucket) return new Response("Storage unavailable", { status: 503 });
  const params = await context.params;
  const object = await bucket.get(`${params.date}/${params.key}`);
  if (!object) return new Response("Image not found", { status: 404 });
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("cache-control", "public, max-age=31536000, immutable");
  return new Response(object.body, { headers });
}
