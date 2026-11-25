# GeoETL 2.0 — instalación y operación

Esta versión amplía explícitamente el perfil de cuatro semanas: 4 fuentes, 6 módulos y 6 vistas. La API pública conserva sus GET y el rol lector. El servicio operador usa el entorno ETL (credenciales de escritura) y no publica puerto; Vite reenvía únicamente peticiones `/operador` autenticadas. No publicar Vite ni este servicio en Internet. Para producción faltan autenticación por usuario, HTTPS, roles, auditoría persistente de tareas y un worker durable.

## Inicio local (WSL / Git Bash)

1. En instalación nueva: `make preparar`; en actualización: conserva `.env`, `datos/` y el volumen `geoetl_postgres_data`. Antes de actualizar, respalda PostgreSQL y los archivos originales; nunca ejecutes `docker compose down -v`.
2. Edita `.env`: establece `POSTGRES_PASSWORD` (mantén la existente si actualizas), `API_DB_PASSWORD` y `OPERATOR_TOKEN` (24 caracteres aleatorios como mínimo; puedes generar uno con `openssl rand -hex 24`). Opcional: `FIRMS_MAP_KEY` de https://firms.modaps.eosdis.nasa.gov/api/. Sin clave no selecciones FIRMS.
3. `make iniciar` (incluye migración 004, permisos y servicio operador). Abre http://localhost:5173.
4. En Procesamiento ETL, ingresa el token, pulsa Conectar. Selecciona USGS, Open-Meteo y NASA POWER; el valor inicial es 14 días y 10 días de atraso histórico (POWER aplica un mínimo de 14). Para FIRMS se consultan tres productos y como máximo 5 días recientes.
5. Extraer → Limpiar → Publicar → Mostrar en el mapa, o Ejecutar todo. Consulta el historial y el estado por paso; un resultado parcial no significa que todas las fuentes funcionaron. El mapa consulta Core, los indicadores consultan Gold.
6. En Radar térmico utiliza el intervalo predeterminado de 60 días, umbral de 30 °C y 3 días consecutivos. Puedes ajustar el criterio según la ciudad; un umbral de prueba no certifica una ola real. Compara fechas comunes y cobertura, no estaciones directas. Los datos horarios Open-Meteo deben tener 24 temperaturas por día UTC; NASA POWER usa máximas diarias UTC. Los episodios pueden estar recortados por el intervalo y los datos no son tiempo real.
7. En Mapa SIG filtra por fenómeno, fuente y fechas, cambia la capa base y exporta GeoJSON visible. El límite es 1200 observaciones por consulta web; puntos idénticos del mismo fenómeno y fuente se agrupan en la interfaz, no se eliminan del GeoJSON. El radar dispone de su propio mapa de episodios.

## Pruebas y límites

- `make pruebas`, `make test-integration`, `make test-e2e`; `make verificar` para Core/Gold. Prueba un segundo clic mientras el pipeline corre, sin token y con token incorrecto. Comprueba la fuente NASA POWER y Open-Meteo por separado, datos válidos y fechas coincidentes.
- Validación de esta entrega: 22 pruebas locales correctas y 1 omitida (DuckDB ausente); compilación sintáctica Python y análisis JSX sin errores. No se pudo ejecutar Docker, PostGIS, pruebas completas (psycopg ausente), build npm (DNS EAI_AGAIN), ni ingesta viva en este entorno. No se incluyen datos ambientales inventados.
- La cola web mantiene una tarea en memoria por proceso; su estado se pierde al reiniciar. Los registros de ingesta permanecen en PostgreSQL. El servicio y el scheduler comparten el mismo bloqueo; no ejecutar CLI de etapas simultáneamente con la web. El reprocesamiento individual sigue en CLI y un lote en cuarentena exige revisión humana.
- Si FIRMS responde CSV válido sin filas, es un resultado legítimo; ampliar la ventana o elegir otro período requiere una nueva consulta. No equivale a ausencia de incendios. El ZIP no contiene la base de datos anterior ni los Bronze históricos.
- Uso académico local; revisar las condiciones de uso de las fuentes y teselas antes de cualquier uso comercial. Las APIs públicas no garantizan disponibilidad ni datos para todas las fechas.

## Fuentes
- USGS: https://earthquake.usgs.gov/fdsnws/event/1/
- FIRMS: https://firms.modaps.eosdis.nasa.gov/api/area/
- Open-Meteo: https://open-meteo.com/en/docs/historical-weather-api
- NASA POWER: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
