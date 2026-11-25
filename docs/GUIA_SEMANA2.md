# GeoETL — Semana 2: ejecución y evidencias

La actualización se instala **sobre el proyecto que ya funciona en la Semana 1**. No elimina `.env`, PostgreSQL, Bronze ni archivos creados por el usuario.

## 1. Instalación (Windows + Git Bash)

1. Descarga y descomprime `GeoETL_Semana2_Actualizacion.zip` dentro de la carpeta principal `geoetl`, de modo que exista `geoetl/GeoETL_Semana2_Actualizacion/instalar_semana2.sh`.
2. Abre Git Bash en la carpeta **raíz** `geoetl` y ejecuta:

```bash
bash GeoETL_Semana2_Actualizacion/instalar_semana2.sh .
make iniciar
make semana2-instalar
make semana2-test
```

El instalador hace una copia de seguridad de archivos reemplazados en `.backup_semana2_...` y nunca toca `.env`, `datos/`, ni los volúmenes Docker. El script añade `duckdb>=1.4,<2` a `requirements.txt`, y `-include Makefile.semana2` al Makefile original. Mantiene los comandos de la Semana 1.

**Atención:** `make semana2-instalar` requiere que `db` ya esté healthy. Solo crea la nueva fuente y tipo de fenómeno, sin truncar ni borrar datos previos. Si modificaste manualmente la web/API, consulta la copia de seguridad antes de conservar los archivos reemplazados.

## 2. Segunda fuente ambiental

La segunda fuente es **FIRMS** si el archivo `.env` contiene `FIRMS_MAP_KEY=<clave_válida>`. En ausencia de clave, **Open-Meteo** es el sustituto documentado y funcionará sin credenciales en uso no comercial sujeto a sus condiciones de servicio.

```bash
# Selección automática: FIRMS si hay clave, Open-Meteo si no la hay.
make semana2-fuente FUENTE=auto DIAS=2

# Forzar alternativa sin clave:
make semana2-fuente FUENTE=openmeteo DIAS=3 CIUDAD=la_paz ATRASO=10

# Otras ciudades:
make semana2-fuente FUENTE=openmeteo DIAS=3 CIUDAD=cochabamba
make semana2-fuente FUENTE=openmeteo DIAS=3 CIUDAD=santa_cruz
```

Open-Meteo consulta **Historical Weather API** (`archive-api.open-meteo.com`), excluyendo los 10 días más recientes por defecto, para mayor estabilidad de la serie archivada. Los datos representan **productos meteorológicos modelados/reanálisis**; no son alertas ni mediciones de estaciones. El identificador de observación es `OM-<ciudad>-<hora_UTC>`.

FIRMS utiliza la API `/api/area/csv/` con VIIRS_SNPP_NRT, bbox `-70,-24,-57,-9` y ventana de 1 a 5 días. Un punto de calor FIRMS **no significa incendio confirmado**. Si falla FIRMS en modo `auto`, se registra la ejecución fallida y se activa Open-Meteo. La `MAP_KEY` nunca se registra en las tablas, la consola ni la API propia; queda en el archivo `.env` local.

## 3. Generar Silver y Core sin descargar de nuevo

```bash
# Lee TODOS los archivos Bronze pendientes (incluido USGS S1) y procesa por lote.
make semana2-procesar
make semana2-resumen

# Ejecutar las pruebas, ahora con DuckDB/Parquet real:
make semana2-test

# Levantar interfaz de monitoreo con endpoints de solo lectura:
make semana2-web
```

El pipeline realiza lo siguiente para cada ejecución pendiente:

1. Consulta el registro de `ops.archivo_crudo` y verifica que el SHA-256 coincida con los bytes en disco.
2. Interpreta el archivo por fuente (USGS GeoJSON, FIRMS CSV u Open-Meteo JSON).
3. Valida las fechas y coordenadas, conserva métricas específicas y reporta los registros rechazados a `ops.registro_calidad`.
4. Deduplica el lote por clave estable y escribe `datos/silver/<fuente>/AAAA/MM/DD/<uuid>.parquet` usando DuckDB.
5. Inserta o actualiza en `core.observacion_ambiental` y `core.medicion_observacion` con claves únicas, referencias al Bronze y geometría `Point(4326)`.
6. Registra cuántos registros se cargaron, repitieron o rechazaron, y pone `registros_pendientes=0`.

No crea tablas `dw` ni el mapa real. Ambos corresponden a la Semana 3.

## 4. Probar idempotencia SIN volver a llamar a las APIs

Primero consulta los UUID de ejecución:

```bash
make consultar
```

Elige un UUID (de USGS o de la segunda fuente) y reprodúcelo:

```bash
make semana2-reprocesar ID=PEGA_AQUI_UUID_DE_LA_EJECUCION
make semana2-resumen
```

**Resultado esperado:** el número de observaciones y mediciones consolidadas de Core **no aumenta** al repetir el mismo lote. El resultado del reprocesamiento mostrará las observaciones coincidentes como `duplicados`. Los contadores de esa ejecución en `ops` se recalculan sobre el estado actual, por lo que pueden diferir respecto de la primera carga; las tablas consolidadas no deben duplicarse.

## 5. Consultar los resultados

- Página: http://localhost:5173/ (Inicio, Procesamiento ETL, Fuentes y calidad).
- Estado de API: http://localhost:8000/health
- Swagger/OpenAPI: http://localhost:8000/docs
- API de ejecuciones: http://localhost:8000/api/v1/etl/ejecuciones
- API de fuentes: http://localhost:8000/api/v1/fuentes/estado
- Resumen Core provisional: http://localhost:8000/api/v1/indicadores/core

### Consultas SQL para capturas y revisión

Ejecuta en Git Bash:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) AS total_observaciones FROM core.observacion_ambiental;"'

docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) AS total_mediciones FROM core.medicion_observacion;"'

docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT regla, count(*) FROM ops.registro_calidad GROUP BY regla ORDER BY regla;"'
```

### Entregables de aceptación de Semana 2

- Dos fuentes efectivas con datos Bronze originales: USGS + FIRMS o Open-Meteo.
- Carpeta Silver con archivos `.parquet` de ambas fuentes.
- Datos Core trazables y sin duplicados por `(id_fuente, clave_origen)`.
- Pruebas de validación y un reprocesamiento que no duplique registros.
- Web con estado de fuentes y ejecuciones reales (sin datos simulados).

## Problemas habituales

- `relation ops.fuente_datos does not exist`: ejecutar primero la migración 001 de S1 (`make iniciar-bd`).
- `source OPEN_METEO not configured`: ejecutar `make semana2-instalar`.
- `No module named duckdb`: reconstruir contenedor con `make semana2-instalar`.
- `No hay extracciones pendientes`: ya se procesaron o la ingesta falló; mirar `make consultar`.
- `FIRMS HTTP 403`: revisar MAP_KEY; usar `FUENTE=openmeteo` para la contingencia.
- `checksum no coincide`: no editar originales; restaurarlos o volver a extraer, preservando historial.
- Puntos sobre países vecinos: el bbox es rectangular e incluye Bolivia y alrededores; el recorte político queda fuera del MVP.
- `make` no está instalado: puedes ejecutar los comandos equivalentes `docker compose` del archivo `Makefile.semana2`.

**Seguridad:** la versión local utiliza aún el usuario PostgreSQL del entorno de desarrollo. Antes de publicar en Internet debe separarse el rol de lectura de la API, proteger credenciales y configurar CORS; forma parte del cierre del MVP.
