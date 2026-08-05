# Despliegue VPS de Estadia20

Esta variante conserva el frontend de `roomies20` y lo ejecuta en un VPS Ubuntu sin depender de Cloudflare. Incluye:

- frontend React compilado con Vite;
- API HTTP en Python 3.10 sin dependencias externas;
- base de datos SQLite persistente;
- cuentas con contraseñas PBKDF2-SHA256 y sesiones seguras;
- anuncios, imágenes, favoritos y consultas por WhatsApp;
- servicio `systemd`, proxy Nginx y HTTPS con Certbot.

## Construcción

```bash
npm run build:vps
python3 -m py_compile vps/server.py
```

La compilación se guarda en `vps/public`.

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
certbot --nginx -d estadia20.com -d www.estadia20.com --redirect
```

El endpoint `GET /api/health` confirma que la API y la base de datos están disponibles.
