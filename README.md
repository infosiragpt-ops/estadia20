# roomies20 marketplace

Marketplace full stack para publicar y encontrar Roomies, departamentos, estadías por noche y servicios de transporte. Incluye contacto directo por WhatsApp, favoritos, consultas, publicación de anuncios y carga de imágenes.

## Tecnología

- React 19 + Next/Vinext
- Cloudflare Workers
- D1 + Drizzle ORM para datos persistentes
- R2 para fotografías y archivos

## Ejecutar en local

Requiere Node.js `>=22.13.0`.

```bash
npm ci
npm run dev
```

La aplicación se abre en la dirección local que muestra el servidor.

## Validar antes de desplegar

```bash
npm run build
npm test
```

## Base de datos y archivos

Los recursos lógicos están declarados en `.openai/hosting.json`:

- `DB`: base de datos D1.
- `UPLOADS`: almacenamiento R2.

El esquema está en `db/schema.ts` y las migraciones versionadas están en `drizzle/`. La aplicación inicializa las tablas requeridas de forma segura cuando recibe solicitudes.

## Despliegue

Importa este repositorio en un entorno compatible con Vinext y Cloudflare Workers. Conserva los bindings `DB` y `UPLOADS`, instala las dependencias y ejecuta `npm run build`.

No se incluyen contraseñas, tokens ni archivos `.env` en el repositorio.
