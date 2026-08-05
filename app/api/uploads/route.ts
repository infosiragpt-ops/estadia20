import { env } from "cloudflare:workers";

type UploadEnvironment = { UPLOADS?: R2Bucket };

export async function POST(request: Request) {
  try {
    const bucket = (env as unknown as UploadEnvironment).UPLOADS;
    if (!bucket) return Response.json({ error: "El almacenamiento de fotografías no está disponible." }, { status: 503 });
    const formData = await request.formData();
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) return Response.json({ error: "Selecciona una fotografía." }, { status: 400 });
    if (!file.type.startsWith("image/")) return Response.json({ error: "El archivo debe ser una imagen." }, { status: 400 });
    if (file.size > 8 * 1024 * 1024) return Response.json({ error: "La imagen debe pesar menos de 8 MB." }, { status: 400 });

    const extension = file.type.split("/")[1]?.replace(/[^a-z0-9]/gi, "") || "jpg";
    const key = `${new Date().toISOString().slice(0, 10)}/${crypto.randomUUID()}.${extension}`;
    await bucket.put(key, await file.arrayBuffer(), {
      httpMetadata: { contentType: file.type, cacheControl: "public, max-age=31536000, immutable" },
    });
    return Response.json({ url: `/api/uploads/${key.split("/").map(encodeURIComponent).join("/")}` }, { status: 201 });
  } catch {
    return Response.json({ error: "No se pudo subir la fotografía." }, { status: 500 });
  }
}
