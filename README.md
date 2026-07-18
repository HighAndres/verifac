# Verifac — Validación y conciliación de CFDI 4.0

Sistema interno que valida facturas CFDI 4.0 de proveedores de servicios (profesores)
y las **concilia contra un layout de montos mensual** antes de autorizar su pago.
Las facturas llegan por correo (XML + PDF) o se suben manualmente; cada una pasa por
reglas fiscales del SAT y por el cotejo obligatorio contra los montos esperados del mes.

## Arquitectura

| Componente | Stack | Puerto |
|------------|-------|--------|
| Backend    | FastAPI + SQLAlchemy + Alembic (Python 3.11, [uv](https://docs.astral.sh/uv/)) | 8001 |
| Frontend   | Next.js 14 + TypeScript + Tailwind | 3000 |
| Base de datos | PostgreSQL | 5432 |
| Correo     | Watcher IMAP (Gmail / Google Workspace con App Password) | — |

## Puesta en marcha (desarrollo)

Requisitos: PostgreSQL corriendo, `uv`, Node 18+.

### 1. Base de datos

```bash
createdb bbva_interno
```

### 2. Backend

```bash
cd backend
cp .env.example .env   # editar valores (ver tabla abajo)
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Variables del `.env`:

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | `postgresql://usuario:password@localhost:5432/bbva_interno` |
| `SECRET_KEY` | Llave para firmar JWT (generar una aleatoria larga) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Vida de la sesión (default 480 = 8 h) |
| `RFC_RECEPTOR` / `NOMBRE_RECEPTOR` | Receptor de las facturas a validar (la empresa pagadora) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` | Usuario superadmin inicial (hash bcrypt) |
| `IMAP_HOST` / `IMAP_PORT` / `IMAP_USER` / `IMAP_PASSWORD` | Buzón del que se leen facturas. `IMAP_PASSWORD` es un **App Password** de Google; mientras tenga el placeholder, el watcher queda inactivo |
| `IMAP_POLL_MINUTES` | Semilla del intervalo de revisión (después se edita desde la UI) |

Generar el hash del admin: `uv run python -c "from app.core.security import hash_password; print(hash_password('TU_PASSWORD'))"`

### 3. Frontend

```bash
cd frontend
echo 'NEXT_PUBLIC_API_URL=http://localhost:8001' > .env.local
npm install
npm run dev
```

App en http://localhost:3000 — login con el usuario admin del `.env`.

## Flujo de operación

**Configuración (una vez):** dar de alta profesores (RFC + régimen fiscal 612/626/603)
y el catálogo de claves SAT.

**Cada mes:**
1. **Montos del mes** — subir el layout `.xlsx` con los montos esperados por profesor
   (plantilla descargable en la propia página; incluir columnas RFC/Mes/Año activa el
   cotejo de periodo).
2. Las facturas llegan solas por **Correo** (o botón "Revisar ahora", o carga manual
   en **Subir XML / Excel**).
3. **Facturas** — revisar aprobadas/rechazadas; el detalle muestra cada cotejo.
   Tras cargar un layout tardío, **↻ Revalidar mes** reprocesa las facturas del periodo.

**Reglas clave:** una factura de un emisor registrado **nunca se aprueba sin conciliar**
contra el layout de su mes; sin layout → rechazada. Retenciones por régimen:
626 RESICO (ISR 1.25 %), 612 (ISR 10 %), ambos IVA ret. 2/3 del IVA; 603 sin retenciones.

**Correo seguro:** en *Config. correo* (superadmin) se definen **remitentes permitidos**
y se enciende la revisión automática. Recomendado: configurar remitentes **antes** de
activar, para no procesar correos ajenos.

## Pruebas

```bash
cd backend && uv run pytest        # requiere la BD migrada
cd frontend && npx tsc --noEmit
```

## Despliegue (VPS)

Guía corta; adaptar rutas/usuarios:

1. **Servicios**: correr backend con `uvicorn app.main:app --host 127.0.0.1 --port 8001`
   (sin `--reload`) y frontend con `npm run build && npm run start`, ambos como
   unidades systemd para reinicio automático.
2. **nginx + HTTPS**: proxy inverso — `/` → 3000, `/api` → 8001 — con certbot para TLS.
3. **`.env` de producción**: `SECRET_KEY` nueva, `FRONTEND_URL` con el dominio real
   (CORS), y el App Password real de IMAP.
4. **Respaldo de BD** (obligatorio — es información de pagos):
   `pg_dump bbva_interno | gzip > backup_$(date +%F).sql.gz` en un cron diario,
   copiado fuera del servidor.
5. Cambios al `.env` requieren **reiniciar el backend** (no hay hot-reload de entorno).

## Estructura

```
backend/
  app/api/v1/endpoints/   # auth, facturas, montos, watcher, profesores, usuarios…
  app/services/           # cfdi_parser, validador, conciliación, imap_watcher,
                          # pdf_cotejo, revalidacion, config_correo
  app/models/             # SQLAlchemy: factura, profesor, monto_mensual…
  alembic/versions/       # migraciones
  tests/                  # pytest (transacciones con rollback)
frontend/
  app/                    # páginas Next.js (App Router)
  components/             # Sidebar, Toast, IdleTimeout…
  lib/api.ts              # cliente del API
```
