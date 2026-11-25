# GeoETL 2.0

**Inicio y operación actualizados:** [Guía v2](docs/GUIA_V2.md). El contenido siguiente documenta la versión histórica 1.0; sus restricciones de solo CLI y dos fuentes se sustituyen por la guía v2.

# GeoETL v1.0 — Plataforma web de Ingeniería de Datos ambientales

**Entrega unificada de las semanas 1, 2, 3 y 4** del perfil técnico de GeoETL. Se construye sobre el proyecto previo: no requiere empezar desde cero ni eliminar tus datos.

> **Alcance:** integración de observaciones USGS y NASA FIRMS; sin `FIRMS_MAP_KEY` funciona Open-Meteo como segunda fuente documentada. No hay predicción ni alertas oficiales. Las observaciones de FIRMS son detecciones térmicas, **no incendios confirmados**.

## 1. Requisitos

- Docker Desktop + Docker Compose v2 (Windows Git Bash, macOS o Linux).
- GNU Make para atajos (`make --version`). Si no existe, revisa las órdenes Docker del Makefile.
- Acceso a Internet para construir las imágenes, descargar datos y mostrar tiles OpenStreetMap.
- Puertos libres **5433** (solo localhost), **8000** (API) y **5173** (React).
- Recursos de Docker recomendados: al menos 4 GB de RAM; las pruebas E2E descargan una imagen de navegador pesada.

## 2. Instalación sobre tu GeoETL anterior

1. **Haz una copia de seguridad antes de reemplazar archivos de código.** Para PostgreSQL en marcha:

   ```bash
   docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > geoetl_backup.dump
   ```

   Guarda también `datos/`, de forma privada. Esto es especialmente importante si modificaste archivos respecto a las entregas anteriores.

2. Extrae el ZIP en el directorio **padre** de tu carpeta `geoetl/`, de modo que reemplace el código de esa misma carpeta. **El ZIP no contiene `.env`, archivos Bronze reales, Parquet reales ni volúmenes PostgreSQL.** Las migraciones 001 y 002 son las del proyecto anterior.

3. Desde Git Bash, dentro de `geoetl/`, añade la variable nueva `API_DB_PASSWORD` a tu **`.env` existente**; no debes reemplazarlo. Elige una contraseña distinta de `POSTGRES_PASSWORD`:

   ```dotenv
   API_DB_PASSWORD=una_clave_distinta_y_segura
   ```

   Si instalas desde cero, utiliza `make preparar`, edita `.env` y cambia **ambas** contraseñas de ejemplo. La clave FIRMS puede quedar vacía.

4. Ejecuta:

   ```bash
   make iniciar
   make pipeline FUENTE=auto DIAS=7 DIAS_SEGUNDA=2
   make verificar
   make pruebas
   ```

5. Abre:

   - **Web:** http://localhost:5173/
   - **API Swagger:** http://localhost:8000/docs
   - **Salud API y BD:** http://localhost:8000/ready

6. Si el historial USGS previo sigue en Bronze y no estaba procesado, `make pipeline` lo consolidará. No se fabrican datos para la web.

**IMPORTANTE:** No ejecutes `docker compose down -v` ni `docker volume prune`: perderías el volumen de PostgreSQL. `make detener` lo conserva.

## 3. Comandos principales

| Comando | Comportamiento |
|---|---|
| `make ayuda` | Todos los atajos |
| `make iniciar` | Subir DB, aplicar migraciones, crear lector SQL, iniciar API y web |
| `make pipeline` | USGS y segunda fuente → Bronze → Silver/Core → Gold |
| `make usgs DIAS=7` | Solo ingesta USGS |
| `make segunda FUENTE=auto DIAS_SEGUNDA=2` | FIRMS si hay clave, Open-Meteo si no |
| `make silver` | Procesar los Bronze pendientes |
| `make gold` | Actualizar dimensiones y hechos idempotentemente |
| `make historico DESDE=2026-09-01 HASTA=2026-10-01` | Carga histórica USGS; `HASTA` exclusivo |
| `make reprocesar ID=<uuid>` | Recuperar Silver/Core desde un lote Bronze y actualizar Gold |
| `make verificar` | Resumen ops/Core/Gold |
| `make integridad` | Comprobar SHA-256 de los últimos 100 archivos Bronze |
| `make programador` | Activar planificación periódica opcional |
| `make programador-logs` | Verificar ejecución programada y posibles errores |
| `make programador-parar` | Detener el programador |
| `make detener` | Detener sin borrar volúmenes |

## 4. Pruebas

```bash
make pruebas             # S1/S2 + unitarios nuevos + API + escenarios feature
make test-integration    # Base PostGIS aislada geoetl_test (NUNCA producción)
make test-performance    # Datos sintéticos solamente en geoetl_test
make test-e2e            # Playwright Chromium escritorio y móvil
make test-all            # Todos los anteriores
```

`make test-e2e` usa la imagen oficial de Playwright y puede tardar la primera vez porque necesita descargarla. **Primero debes ejecutar `make iniciar`** y preferiblemente `make pipeline`; las pruebas también verifican la navegación cuando aún no hay datos.

Los tests de integración eliminan y recrean datos **solo en `geoetl_test`**; existe una protección explícita que falla si el nombre de la base es diferente. No se usan datos sintéticos en tu base de desarrollo.

En el entorno de creación del ZIP se verificaron sintaxis Python, JSX, sintaxis de Makefile y **15 pruebas originales exitosas con 1 omitida** (DuckDB ausente). **No se ha comprobado aquí la ejecución integral Docker/PostGIS/Playwright**. Lee [`docs/VALIDACION_Y_LIMITACIONES.md`](docs/VALIDACION_Y_LIMITACIONES.md).

## 5. Arquitectura

```text
USGS (JSON) ─┐
              ├─ Python / httpx → Bronze JSON/CSV original + SHA-256
FIRMS (CSV) ─┤                       │
Open-Meteo ──┘ [contingencia]         ↓
                               Silver DuckDB + Parquet
                                        ↓
                               Core PostgreSQL/PostGIS
                                        ↓
                               Gold: Data Warehouse
                                        ↓
                               FastAPI (solo lectura)
                                        ↓
                        React + Vite + Leaflet (5 vistas)
```

- **Bronze:** bytes exactos de la API, checksum, origen, ejecución y parámetros.
- **Silver:** `datos/silver`, Parquet con columnas normalizadas UTC/WGS84, validación y deduplicación.
- **Core:** observaciones con geometría `Point(4326)` y métricas por fenómeno.
- **Gold:** esquema estrella `dw.dim_fecha`, `dw.dim_fuente`, `dw.dim_fenomeno`, `dw.hecho_observacion`.
- **Consumo:** consultas filtradas/limitadas, GeoJSON, gráficos de conteos y estados de calidad.

El procesamiento se ejecuta mediante CLI o scheduler, **nunca a través de la API pública**.

## 6. API de solo lectura

- `GET /health` y `GET /ready`
- `GET /api/v1/observaciones?fuente=USGS&limit=50&offset=0`
- `GET /api/v1/observaciones/{id}`
- `GET /api/v1/mapa/observaciones?bbox=-70,-24,-57,-9&limit=500`
- `GET /api/v1/indicadores/resumen`
- `GET /api/v1/indicadores/serie`
- `GET /api/v1/fuentes/estado`
- `GET /api/v1/etl/ejecuciones`
- `GET /api/v1/calidad/resumen`

Para el mapa se permite bbox válida de oeste,sur,este,norte; las consultas están limitadas a 2.000 puntos por respuesta. Al acercar el mapa, Leaflet recalcula el área visible. Se informa cuando el resultado ha sido truncado. No hay endpoints POST/PUT/DELETE.

## 7. Estructura del repositorio

```text
apps/api/           FastAPI + rutas y filtros
apps/web/           React, Leaflet, diseño responsive y Playwright
pipelines/          USGS, fuente secundaria, transformadores, Core, Gold, scheduler
sql/migraciones/    001_base.sql, 002_semana2.sql, 003_gold.sql
sql/vistas/         consultas de verificación analítica
sql/semillas/       catálogos de fuente y fenómeno
tests/              unitarias, API, features, integración, rendimiento
datos/bronze/       originales persistentes (fuera de Git)
datos/silver/       datasets Parquet (fuera de Git)
docs/               arquitectura, pruebas, requisitos, decisiones y limitaciones
```

## 8. Criterio de terminación antes de desplegar

- Las dos fuentes han sido **consultadas realmente** o se ha documentado la contingencia.
- `make pipeline` concluye sin errores y Core/Gold tienen datos coherentes.
- `make integridad` confirma checksums.
- Reprocesar un lote no duplica Core ni Gold.
- `make test-all` supera las pruebas críticas en tu equipo.
- Se comprueba una ejecución real del scheduler mediante `make programador-logs`.
- Las cinco páginas usan API real y el mapa muestra puntos cuando existen datos.

Solo tras esas comprobaciones pasaremos al despliegue público. Para proteger producción, no reutilizar la contraseña administrativa, no publicar el puerto de DB y revisar las condiciones de uso de los proveedores de datos/mapas.
