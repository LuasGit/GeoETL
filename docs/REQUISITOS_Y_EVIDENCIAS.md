# Matriz de implementación — GeoETL RF-01…RF-20

**Estado:** indica que existe implementación en código, **NO** acredita que se haya ejecutado exitosamente en el equipo del usuario. Los comandos de validación son el contrato de aceptación.

| ID | Módulo | Funcionalidad implementada | Evidencia / prueba a realizar |
|---|---|---|---|
| RF-01 | M1 | Extractor USGS con HTTP, fecha y bbox | `make usgs DIAS=7`, `tests/test_usgs.py` |
| RF-02 | M1 | NASA FIRMS o contingencia Open-Meteo documentada | `make segunda FUENTE=auto`, `tests/test_semana2.py` |
| RF-03 | M1 | Bronze exacto y checksum SHA-256 | `make integridad`, `tests/test_bronze.py` |
| RF-04 | M1 | Historial de ingesta, duración, contadores y errores | `make consultar`, `GET /api/v1/etl/ejecuciones` |
| RF-05 | M2 | Fechas UTC, normalización coordenadas, Point(4326) en Core | `tests/test_semana2.py`, integración PostGIS |
| RF-06 | M2 | Nulos, rangos y tipos inválidos | `tests/test_semana2.py` y escenarios feature |
| RF-07 | M2 | Claves estables por fuente y Core sin duplicados | `make reprocesar ID=...`, test integración |
| RF-08 | M2 | Rechazos en `ops.registro_calidad`; Silver Parquet reproducible | `make silver`, tests features e integración |
| RF-09 | M3 | Observaciones/métricas con integridad referencial | `001_base.sql`, `make verificar`, tests SQL |
| RF-10 | M3 | Dimensión fecha, fuente, fenómeno y hecho observación | `003_gold.sql`, `make gold`, tests integración |
| RF-11 | M3 | Índice GiST, consulta bbox filtrada | API GeoJSON; `test_consulta_espacial_con_mil_observaciones` |
| RF-12 | M4 | CLI manual y planificador periódico | `make pipeline`, `make programador`, logs |
| RF-13 | M4 | Última carga, frescura y métricas por fuente | `GET /api/v1/fuentes/estado`, pantalla Fuentes |
| RF-14 | M4 | Reprocesamiento Bronze sin duplicar | `make reprocesar ID=...`, test integración |
| RF-15 | M5 | API observaciones y GeoJSON de solo lectura | Swagger `/docs`, tests API/integración |
| RF-16 | M5 | Inicio con KPIs Gold | Web Inicio + `/indicadores/resumen` |
| RF-17 | M5 | Mapa Leaflet, filtros fecha/tipo, popup métricas | E2E Playwright desktop/mobile |
| RF-18 | M5 | Analítica con series y agregados Gold | Web Analítica, `/indicadores/serie` |
| RF-19 | M5 | ETL y Fuentes/Calidad en solo lectura | Web, rutas `/etl/ejecuciones` y `/calidad/resumen` |
| RF-20 | M5 | Interfaz responsive | CSS media queries y E2E viewport móvil |

## Requisitos no funcionales

| ID | Característica | Medidas implementadas / validación |
|---|---|---|
| RNF-01 | Idempotencia | Claves únicas y `UPSERT` Core/Gold; test de doble reprocesamiento |
| RNF-02 | Trazabilidad | Gold → Core → archivo original → ejecución; detalle expone checksum e ID de ejecución, no ruta física |
| RNF-03 | Calidad | Funciones de validación y rechazos; pruebas con datos inválidos |
| RNF-04 | Seguridad | Dos cuentas separadas, API `SELECT`, endpoint HTTP solo GET; verificar prueba `geoetl_reader` |
| RNF-05 | Disponibilidad | Datos anteriores no se borran si falla una fuente; test de resiliencia |
| RNF-06 | Rendimiento | GiST, bbox, `limit<=2000` y test SQL con 1.000 observaciones sintéticas aisladas |
| RNF-07 | Portabilidad | Docker Compose, `.env.example`, Makefile y migraciones reutilizables |
| RNF-08 | Observabilidad | Fecha inicio/fin, estado, contadores, intentos, logs programador, resumen Core/Gold |
| RNF-09 | Responsive | Estilos móviles y Playwright Pixel 5 |
| RNF-10 | Semántica | Se distinguen sismos, puntos de calor y meteorología modelada; no se ofrecen alertas oficiales |

**Para declarar un requisito como “Cumplido / validado”** se debe aportar el resultado del comando indicado o una captura real de la aplicación. Este documento no reemplaza esa comprobación.
