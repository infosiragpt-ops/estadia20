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

## Configuración del cliente OAuth de Google

Se usa el cliente OAuth web existente (`GOOGLE_CLIENT_ID`); no hay que crear
uno nuevo ni configurar un secreto. En Google Cloud Console → APIs y
servicios → Credenciales → el cliente OAuth web, marca **los cuatro orígenes
y las cuatro URI de redirección**:

**Authorized JavaScript origins** (para el botón oficial de Google Identity
Services):

- `https://llaves365.com`
- `https://www.llaves365.com`
- `https://estadia20.com`
- `https://www.estadia20.com`

**Authorized redirect URIs** (para el acceso por redirección cuando el iframe
de GIS no carga, p. ej. Safari móvil o FedCM bloqueado):

- `https://llaves365.com/api/auth/google/callback`
- `https://www.llaves365.com/api/auth/google/callback`
- `https://estadia20.com/api/auth/google/callback`
- `https://www.estadia20.com/api/auth/google/callback`

El flujo de redirección lo inicia `GET /api/auth/google/start`
(`response_type=id_token`, `response_mode=form_post`, con `state` y `nonce`
verificados en el servidor); Google devuelve el `id_token` con un POST a
`/api/auth/google/callback`, que lo valida igual que `POST /api/auth/google`,
crea la cookie de sesión y vuelve a la portada. Los dominios aceptados para
el retorno se controlan con `ESTADIA20_OAUTH_HOSTS` (por defecto los cuatro
dominios anteriores).

Las cuentas administradoras se controlan con `ESTADIA20_OWNER_EMAIL`
(acepta varios correos separados por comas, con compatibilidad para
`LLAVES365_OWNER_EMAIL` y `ROOMIES20_OWNER_EMAIL`) y por defecto son
`carrerajorge874@gmail.com` e `infosiragpt@gmail.com`. Solo se promueven al
iniciar sesión con Google (correo verificado); esos correos no pueden
registrarse con contraseña. Al arrancar, el servidor sincroniza el rol
`admin` con esos correos y lo retira de cualquier otra cuenta.

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

## Panel de administración

Al iniciar sesión con Google con el correo administrador, el menú y "Mi
cuenta" muestran el "Panel de administración": resumen con métricas
(anuncios, cuentas, contactos, favoritos), gestión de anuncios (editar,
insignia, eliminar), consultas registradas y lista de usuarios. Todos los
usuarios con sesión pueden gestionar sus propios anuncios desde "Mis
anuncios".

## Datos de demostración

Los anuncios de ejemplo ya no se insertan automáticamente: solo se siembran
si el servicio arranca con `ESTADIA20_SEED_DEMO=1`. Así, los anuncios de
demostración eliminados desde el panel no reaparecen al reiniciar. La base de
producción existente conserva los suyos hasta que el administrador los borre.

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
