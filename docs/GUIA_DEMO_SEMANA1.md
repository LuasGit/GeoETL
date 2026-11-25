# GeoETL — Guía de demostración E1 (Semana 1)

## Antes de presentar

1. Abrir **Docker Desktop** y esperar a que el motor esté activo.
2. Abrir **Git Bash** en la raíz `geoetl/`.
3. Ejecutar `make iniciar` y `make estado`.
4. Ejecutar `make demo` (solo consulta: **no descarga un nuevo lote**).
5. Abrir http://localhost:5173/ y http://localhost:8000/health.

## Secuencia sugerida de demostración (5 a 8 min)

**1. Contexto.** GeoETL integra observaciones de fuentes ambientales bajo arquitectura Medallón. En E1 demostramos la extracción real de USGS a Bronze y la trazabilidad en `ops`.

**2. Extracción.** Mostrar `make usgs DIAS=7` *solo si se desea una nueva extracción*. La cantidad de sismos depende del período y del rectángulo geográfico `(-70,-24,-57,-9)`, que incluye territorio vecino a Bolivia.

**3. Bronze.** `make bronze` enumera el GeoJSON y sus observaciones. Un archivo puede contener varias observaciones; en una ejecución previa se obtuvieron 3.

**4. Integridad y procedencia.** `make consultar` muestra el UUID de ejecución, registros recibidos, ruta y SHA-256. `make integridad` recalcula el hash del archivo y contrasta con PostgreSQL.

**5. Pruebas.** `make pruebas` ejecuta la suite sin acceder a USGS real. El resultado esperado en el proyecto base es 6 pruebas aprobadas.

**6. Web.** Abrir `http://localhost:5173/`: tiene cinco vistas navegables, pero en E1 no grafica sismos reales; la API de consumo solo implementa `GET /health`.

## Arquitectura real en la primera entrega

`USGS → httpx → validación de respuesta → Bronze (.geojson intacto + SHA-256) → PostgreSQL ops (ejecución + archivo)`. En paralelo, React consulta `/health` a través del proxy Vite que envía la petición a FastAPI.

La capa Silver (DuckDB/Parquet), Core poblado, Gold, los endpoints geoespaciales y Leaflet se implementarán en las semanas siguientes, no están concluidos en E1.

## Cómo explicar cada archivo principal

- `docker-compose.yml`: configura los servicios `db`, `api`, `web`, `etl`, puertos, redes, variables y volúmenes.
- `Dockerfile.python`: instala dependencias e incorpora extractores, API y tests a las imágenes Python.
- `sql/migraciones/001_base.sql`: crea PostGIS, esquemas `ops`/`core`, tablas y restricciones; Core está vacío inicialmente.
- `sql/semillas/001_catalogos.sql`: registra las fuentes USGS/FIRMS y los tipos de fenómeno iniciales.
- `pipelines/extractores/usgs.py`: realiza la consulta real, reintentos y validación mínima GeoJSON sin alterar bytes.
- `pipelines/comun/almacenamiento.py`: crea el archivo Bronze con una ruta por fecha de extracción UTC/UUID y checksum SHA-256.
- `pipelines/comun/bd.py`: crea conexiones PostgreSQL por variables de entorno.
- `pipelines/cli.py`: orquesta la ejecución: abre registro en `ops`, descarga, persiste Bronze, registra hash y marca estado final.
- `sql/vista_verificacion.sql`: consulta el historial y prueba la trazabilidad.
- `apps/api/main.py`: FastAPI con endpoint `/health`.
- `apps/web/src/main.jsx`: navegación React y llamada a `/health`.
- `apps/web/src/style.css`: diseño responsivo de la interfaz.
- `apps/web/vite.config.js`: proxy `/health` del servidor web al servicio `api:8000`.
- `tests/test_*.py`: aseguran comportamiento de los componentes sin depender de la API externa.
- `.env`: parámetros sensibles locales; no publicarlo. `.env.example`: plantilla sin credenciales reales.
- `datos/bronze`: archivos reales versionados por fecha/ejecución; no se borran cuando se detienen contenedores de forma normal.

## Preguntas frecuentes de la presentación

**¿Por qué tres observaciones?** Porque la consulta piloto solo encontró tres objetos en ese rango de fechas y rectángulo. Eso no representa el total histórico. Más adelante se hará backfill por ventanas controladas y cargas incrementales.

**¿Por qué conservar el JSON original?** Para auditar procedencia, comprobar integridad mediante SHA-256 y poder regenerar Silver sin volver a consultar la API.

**¿Qué hace el checksum?** Detecta cambios en los bytes almacenados. No es una firma digital ni una garantía de autenticidad de la fuente.

**¿Por qué la API y el mapa no muestran ya esos sismos?** Los puntos todavía no han atravesado Silver, Core y Gold. En la siguiente fase se normalizarán a UTC/WGS84 y después podrán consultarse en PostGIS.

**¿Por qué hay tablas Core si están vacías?** La migración deja listo el modelo contractual para el siguiente paso, pero E1 no finge que el pipeline ya carga esos datos.

**¿Qué significa EXITO en la tabla de ingesta ahora?** Descarga y preservación Bronze confirmadas, no procesamiento hasta Gold. Los registros se encuentran pendientes (`registros_pendientes`).

**¿Qué sucede si detengo Docker?** `make detener` conserva el volumen de PostgreSQL y la carpeta `datos/`. Evita `docker compose down -v`, porque elimina el volumen de base de datos.
