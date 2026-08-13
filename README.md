# Estadia20 marketplace

Marketplace full stack (estadia20.com) para publicar y encontrar Roomies, departamentos, estadías por noche y servicios de transporte. Incluye contacto directo por WhatsApp, favoritos, consultas, publicación de anuncios, carga de imágenes, gestión de anuncios propios y un panel de administración.

La cuenta administradora es `carrerajorge874@gmail.com` (configurable con la variable `ESTADIA20_OWNER_EMAIL` en el VPS). Al iniciar sesión con Google con ese correo, la cuenta recibe el rol `admin` y puede abrir el panel de administración desde el menú o desde "Mi cuenta".

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
