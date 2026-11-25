BEGIN;
INSERT INTO ops.fuente_datos (codigo,nombre,url_base,formato_datos,frecuencia_minutos,esta_activa)
VALUES ('NASA_POWER','NASA POWER Daily','https://power.larc.nasa.gov/api/temporal/daily/point','JSON',1440,TRUE)
ON CONFLICT (codigo) DO NOTHING;
COMMIT;
