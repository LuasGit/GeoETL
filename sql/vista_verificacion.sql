-- Ejecutar con psql para verificar el resultado E1.
SELECT f.codigo, e.id_ejecucion, e.estado, e.fecha_inicio,
       e.registros_recibidos, e.registros_pendientes,
       a.ruta_archivo, a.checksum_sha256
FROM ops.ejecucion_ingesta e
JOIN ops.fuente_datos f ON f.id_fuente = e.id_fuente
LEFT JOIN ops.archivo_crudo a ON a.id_ejecucion = e.id_ejecucion
ORDER BY e.fecha_inicio DESC
LIMIT 10;
