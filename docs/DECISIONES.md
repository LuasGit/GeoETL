# Decisiones de implementación, Semana 1

**Fuente:** GeoETL_Perfil_Tecnico_4_Semanas(1).pdf, apartados 5-10.

1. **Solo E1**: la extracción registra únicamente originales en Bronze y `ops`, sin insertar observaciones Core ni Gold artificialmente. `EXITO` en S1 significa extracción y persistencia Bronze confirmadas.
2. **Contadores consistentes**: `registros_pendientes` se agrega a `ops.ejecucion_ingesta` y conserva `recibidos = cargados + duplicados + rechazados + pendientes`. Semana 2 procesará esos pendientes, de forma transaccional, hacia Silver/Core.
3. **Metadatos de consulta**: `parametros_consulta` y `codigo_http` se agregan a la ejecución para la reproducción y diagnóstico. Nunca incluir secretos de FIRMS en `parametros_consulta`.
4. **Trazabilidad de UPSERT**: en Core, `id_archivo_origen` apuntará al Bronze de la versión consolidada, no necesariamente al primero. Actualizar la referencia y las mediciones en la misma transacción.
5. **Unicidad de métricas**: `UNIQUE(id_observacion,codigo_metrica)` define un único valor actual por tipo de métrica. Historias de cambio quedan fuera del MVP.
6. **Territorio**: el bbox -70,-24,-57,-9 es una región rectangular de interés que incluye Bolivia y áreas vecinas. No es un filtro exacto a fronteras nacionales. Los filtros por límites administrativos siguen fuera del MVP.
7. **No publicar privilegios de escritura**: E1 no expone accesos públicos a PostgreSQL; API solo expone `/health`. Se crearán roles separados de lectura/ETL antes de los endpoints reales de la semana 3.
8. **FIRMS**: comprobar MAP_KEY antes del tercer día de S1. Si no se consigue acceso, registrar la decisión y preparar la alternativa Open-Meteo desde la S2. No incluir la clave en código, URLs registradas ni logs.
9. **Sin simulación engañosa**: el frontend inicial ofrece navegación y estado de la API, y marca como pendientes los indicadores todavía no conectados a datos reales.
10. **Programación**: el servicio ETL existe como comando independiente y se automatizará en S2/S3 mediante cron en un entorno persistente; FastAPI no expone un endpoint de ejecución.
