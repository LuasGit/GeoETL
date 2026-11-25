# Arquitectura GeoETL v1.0 y decisiones de ingeniería

## 1. Responsabilidades

| Capa | Código principal | Entrada → salida |
|---|---|---|
| Extractores | `pipelines/extractores/usgs.py`, `fuente_segunda.py` | HTTPS → bytes y metadatos |
| Bronze | `pipelines/comun/almacenamiento.py` | Bytes → archivo inmutable, SHA-256 |
| Silver | `pipelines/transformaciones/normalizar.py`, `parquet.py` | Bytes validados → Parquet |
| Core | `pipelines/semana2.py`, `sql/migraciones/001_base.sql` | Registros normalizados → `core.observacion_ambiental` y `core.medicion_observacion` |
| Gold | `pipelines/cargas/gold.py`, `sql/migraciones/003_gold.sql` | Core → dimensiones, hecho y vistas |
| Operación | `ops.*`, `pipelines/orquestador.py`, `scheduler.py` | Ejecutar, comprobar, registrar, informar |
| API | `apps/api/*` | Consultas SQL parametrizadas → JSON/GeoJSON |
| Web | `apps/web/src/*` | Endpoints → cinco vistas y mapa |

## 2. Transacciones e idempotencia

- Bronze usa un UUID por ejecución, archiva el cuerpo original y registra su hash.
- Silver calcula la identidad de observación por fuente: ID USGS cuando existe; FIRMS por sensores, fecha/hora y coordenadas; Open-Meteo por ubicación/hora.
- Core tiene `UNIQUE (id_fuente,clave_origen)` y métricas únicas por observación/código.
- El reprocesamiento de un lote existente verifica primero su checksum Bronze y no requiere acceso a la API.
- Gold resuelve las dimensiones y usa `ON CONFLICT (id_observacion_origen) DO UPDATE`; nunca duplica hechos.
- El orquestador usa un lock consultivo PostgreSQL de sesión para impedir dos ejecuciones completas simultáneas. Gold usa un lock transaccional distinto.

**Limitación conocida:** el archivo Parquet se publica junto al proceso SQL pero sin una transacción distribuida entre sistema de archivos y PostgreSQL. Si el proceso cae después de escribir Parquet y antes de confirmar SQL, debe reprocesarse el mismo Bronze; la carga idempotente repara esa situación.

## 3. Cómo se calculan indicadores

- Core conserva el detalle (magnitud, profundidad, FRP, precipitación, etc.).
- Gold tiene una fila de hecho por **observación consolidada** con `cantidad_observaciones=1`.
- Las series temporales y agregaciones por fuente/fenómeno se calculan desde Gold.
- Se evita comparar o promediar magnitud sísmica con FRP, puesto que son unidades incompatibles.

## 4. Modelo espacial

- `core.observacion_ambiental.geometria` usa PostGIS `GEOMETRY(Point,4326)`.
- Índice GiST para geofiltros; consulta con `ST_Intersects(..., ST_MakeEnvelope(...))`.
- Los límites de bbox iniciales cubren **Bolivia y territorio vecino**, no una frontera política exacta.
- La API impone límite de resultados; la web informa de truncamiento y permite acercarse para mejorar granularidad.

## 5. Datos y permisos

- ETL y migraciones utilizan la cuenta administradora de desarrollo configurada en `.env`.
- API utiliza `geoetl_reader` con permisos de `SELECT` solamente y transacciones de solo lectura.
- Los secretos no están dentro del frontend ni se envían a respuestas de API.
- La clave FIRMS queda exclusivamente en el contenedor ETL/scheduler.
- La base se vincula a `127.0.0.1` durante desarrollo; su publicación remota está fuera de esta entrega.

## 6. Interpretación del estado

- `ops.ejecucion_ingesta.estado=EXITO` refleja la ingesta y/o el procesamiento del lote; revisar los contadores `pendientes/cargados/rechazados` para entender su fase efectiva.
- `ops.vw_estado_fuentes` deriva la última extracción exitosa y la compara con la frecuencia objetivo. Es un indicador operacional simple, no una garantía de actualización oficial.
- Las observaciones meteorológicas de Open-Meteo provienen de una serie modelada/histórica en puntos de referencia, no de sensores puntuales en tiempo real.

## 7. Requisitos de despliegue posterior

Para un despliegue público habrá que definir almacenamiento persistente, DNS/TLS, proxies inversos, respaldo/restauración, rotación de secretos, límites CORS y de tasa, monitoreo y política de uso de tiles OSM. Esta entrega se prueba primero en Docker local.
