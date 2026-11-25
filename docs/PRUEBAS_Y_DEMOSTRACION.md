# Plan de pruebas y demostración GeoETL v1.0

## 1. Antes de probar

`make iniciar` aplica las migraciones y configura el usuario API de lectura. Luego `make pipeline` ingesta dos fuentes, normaliza datos, actualiza Core y sincroniza Gold.

No entregamos datos falsos en el sistema real: las fixtures de prueba están identificadas como sintéticas y se ejecutan solo sobre almacenamiento temporal o una base `geoetl_test`.

## 2. Categorías

| Tipo | Comando | Evidencia |
|---|---|---|
| Unitarias | `make test-unit` | Checksum, parámetros USGS, normalizadores, backfill, validación bbox |
| API | `make test-api` | Rutas, HTTP GET, límites y esquema OpenAPI |
| Features / BDD | `make test-features` | Escenarios Gherkin de ingesta, errores y Silver |
| Integración PostGIS | `make test-integration` | Prueba Core/Gold, idempotencia, GeoJSON, rol de lectura y resiliencia |
| Rendimiento SQL | `make test-performance` | Mil observaciones sintéticas, consulta bbox y carga Gold |
| E2E | `make test-e2e` | Cinco secciones, mapa, filtros, móvil Chromium |
| Completa | `make test-all` | Ejecuta todas las categorías anteriores |

La base aislada está en el servicio `testdb` con nombre **geoetl_test**, sin puertos externos. Los tests que realizan `TRUNCATE` comprueban primero que el nombre de DB sea exactamente `geoetl_test`, para no borrar información del usuario.

## 3. Guion de demostración (orden sugerido)

1. `make estado`: servicios activos, DB healthy.
2. `make verificar`: concordancia Core y DW; vistas diarias.
3. `make consultar` y `make bronze`: registros, IDs, archivos.
4. `make integridad`: igualdad de SHA-256.
5. `make pruebas` y `make test-integration`: suite de calidad e idempotencia.
6. Abrir `/docs`: consultas REST y GeoJSON filtrado por bbox.
7. Abrir web: Inicio, mapa, Analítica, ETL, Fuentes/Calidad. Cambiar un filtro y acercar el mapa.
8. `make programador` y `make programador-logs`: observar al menos una ejecución programada real; después `make programador-parar`.
9. Capturar evidencias y registrar fecha, comandos, salida y resultado.

## 4. Prueba de reprocesamiento idempotente

1. Copiar un `id_ejecucion` existente desde `make consultar`.
2. Consultar `SELECT count(*) FROM core.observacion_ambiental` y `SELECT count(*) FROM dw.hecho_observacion`.
3. `make reprocesar ID=<UUID>`.
4. Repetir ambos conteos: deben permanecer iguales si no hubo nuevos cambios en el mismo lote.
5. `make integridad` confirma que el Bronze original no se modificó.

## 5. Prueba de fallos y límites

- Simular HTTP 503 usando `httpx.MockTransport` en pruebas (no depender de romper Internet manualmente).
- Intentar bbox invertido y un `limit` excesivo: debe responder HTTP 422.
- Verificar que la API no acepte POST ni pueda INSERT en PostgreSQL.
- Detener temporalmente la API y comprobar que la web muestre mensaje de fallo, no números inventados.
- En el mapa, cuando se alcanza el límite de puntos, aparece aviso de truncamiento.

## 6. Decisiones sobre rendimiento

El test de rendimiento con 1.000 observaciones es **orientativo y local**; no constituye prueba de escalabilidad a millones de registros ni SLA de producción. Para ello serían necesarias mediciones adicionales, `EXPLAIN ANALYZE`, índices apropiados y potencialmente agregación/clustering o vector tiles.

## 7. Evidencias de aceptación

Registrar capturas de los contenedores, el archivo Bronze, SHA, tabla `ops.ejecucion_ingesta`, archivos Parquet, tabla Core, tablas DW, Swagger, mapa con puntos reales, páginas responsive, tests y planificador. Las pruebas sintéticas no deben confundirse con los datos USGS/FIRMS reales.
