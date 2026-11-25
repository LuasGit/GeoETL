\set ON_ERROR_STOP on
SELECT 'core_observaciones' AS indicador, count(*) AS valor FROM core.observacion_ambiental
UNION ALL SELECT 'gold_hechos', count(*) FROM dw.hecho_observacion
UNION ALL SELECT 'gold_dim_fecha', count(*) FROM dw.dim_fecha
UNION ALL SELECT 'gold_dim_fuente', count(*) FROM dw.dim_fuente
UNION ALL SELECT 'gold_dim_fenomeno', count(*) FROM dw.dim_fenomeno;
SELECT * FROM dw.vw_observaciones_diarias ORDER BY fecha DESC LIMIT 15;
