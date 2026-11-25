# Informe de validación de entrega y limitaciones conocidas

## Lo verificado en el entorno de construcción del ZIP

- Se descomprimieron ambos ZIP proporcionados y se integró la actualización S2 sobre S1.
- Se generaron migraciones Gold, roles SQL, orquestación, API, frontend, tests e instrucciones.
- Se verificó sintaxis Python mediante `compileall`.
- Se verificó sintaxis de JSX y JavaScript mediante el parser TypeScript disponible localmente.
- Se validó sintaxis de targets Make mediante `make -n` (no se ejecutaron contra Docker).
- Se ejecutaron los tests heredados que no necesitan PostgreSQL ni DuckDB: **15 aprobados, 1 omitido** (DuckDB ausente).

## No verificado aún

- `docker compose up` y migraciones reales con PostGIS, porque este entorno no dispone de Docker.
- `pytest-bdd` features, `duckdb` Parquet y conexión `psycopg` porque no se pudieron descargar dependencias externas aquí.
- Integración API/Postgres, compilación completa Vite con dependencias reales y E2E Playwright con navegador.
- Extracción real de FIRMS/Open-Meteo y scheduler operativo en un host persistente.
- Validación de rendimiento en tu computadora y desplegado en nube.

No corresponde marcar esos puntos como **superados** hasta ejecutarlos en el equipo del usuario. El proyecto es una entrega integrada de código con pruebas reproducibles, pendiente de aceptación real.

## Limitaciones técnicas conscientes del MVP

1. No se prueba escala de millones de puntos; mapa GeoJSON limita 2.000 por consulta. Para mayores volúmenes considerar clustering/agregación o tiles.
2. Bronze/Silver están en un volumen local, no en almacenamiento de objetos; se necesitan copias de seguridad para un servidor público.
3. No hay transacciones distribuidas entre Parquet en filesystem y PostgreSQL; reprocesar desde Bronze recupera inconsistencias.
4. `make pipeline` realiza consultas nuevas con ventanas acotadas; el histórico USGS se obtiene con `make historico` y después `make silver && make gold`.
5. El programador es un servicio de intervalos, no un orquestador completo tipo Airflow; su intervalo se cuenta desde el último ciclo, no desde una hora fija de calendario.
6. La precisión de datos geográficos es la declarada por la fuente; el bbox de Bolivia incluye regiones vecinas.
7. El endpoint `/health` verifica proceso API, mientras `/ready` sí verifica la conexión SQL.
8. El contador de cargas de `ops.ejecucion_ingesta` es por lote; no es el número de observaciones únicas actuales, que debe consultarse en Core/Gold.

## Antes del despliegue público

Revisar y ejecutar `make test-all`, comprobar claves secretas fuera de Git, establecer respaldos y restauración, ajustar HTTPS y proxy inverso, limitar CORS/requests, revisar licencias de los tiles base y configurar almacenamiento persistente fuera del ciclo de vida de los contenedores.
