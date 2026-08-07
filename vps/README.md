# Despliegue VPS de roomies20

Esta variante conserva el frontend de `roomies20` y lo ejecuta en un VPS Ubuntu sin depender de Cloudflare. Incluye:

- frontend React compilado con Vite;
- API HTTP en Python 3.10 con el verificador oficial de Google incluido en cada despliegue;
- base de datos SQLite persistente;
- inicio de sesión con Google, cuentas de respaldo con PBKDF2-SHA256 y sesiones seguras;
- anuncios, imágenes, favoritos y consultas por WhatsApp;
- servicio `systemd`, proxy Nginx y HTTPS con Certbot.

## Construcción

```bash
npm run build:vps
python3 -m pip install --requirement vps/requirements-google.txt \
  --target vps/public/.server_vendor
python3 -m py_compile vps/server.py
```

La compilación se guarda en `vps/public`.

El cliente OAuth web de Google debe autorizar `https://llaves365.com` y
`https://www.llaves365.com`. El identificador público se configura mediante
`GOOGLE_CLIENT_ID`; la cuenta administradora se controla con
`LLAVES365_OWNER_EMAIL` (con compatibilidad para `ROOMIES20_OWNER_EMAIL`) y por
defecto es `infosiragpt@gmail.com`.

## Rutas de producción

- aplicación: `/opt/estadia20`;
- base de datos: `/var/lib/estadia20/estadia20.sqlite3`;
- imágenes: `/var/lib/estadia20/uploads`;
- servicio: `/etc/systemd/system/estadia20.service`;
- Nginx: `/etc/nginx/sites-available/estadia20.conf`.

Después de instalar los archivos, habilita los servicios y valida la configuración:

```bash
systemctl daemon-reload
systemctl enable --now estadia20.service
nginx -t
systemctl reload nginx
certbot --nginx --cert-name estadia20.com \
  -d llaves365.com -d www.llaves365.com \
  -d estadia20.com -d www.estadia20.com \
  --expand --redirect
```

El endpoint `GET /api/health` confirma que la API y la base de datos están disponibles.

## Despliegue automático desde GitHub

El workflow `.github/workflows/deploy-production.yml` despliega automáticamente cada cambio que llega a la rama `main`. También se puede ejecutar manualmente desde GitHub Actions.

El servidor usa un usuario SSH exclusivo y sin acceso general a `sudo`. Ese usuario solo puede ejecutar:

```bash
sudo /usr/local/sbin/estadia20-deploy /tmp/estadia20-release.tgz
```

Instala `vps/deploy-release.sh` en `/usr/local/sbin/estadia20-deploy`, propiedad de `root` y con permisos `0755`. El script valida el paquete, activa la nueva versión, comprueba la API y restaura automáticamente la versión anterior si algo falla.

Configura estos secretos en el repositorio de GitHub:

- `VPS_HOST`: dirección del VPS;
- `VPS_PORT`: puerto SSH, normalmente `22`;
- `VPS_USER`: usuario SSH limitado de despliegue;
- `VPS_SSH_KEY`: clave privada exclusiva de GitHub Actions;
- `VPS_KNOWN_HOSTS`: huella SSH obtenida de forma confiable.
