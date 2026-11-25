\set ON_ERROR_STOP on
BEGIN;
INSERT INTO ops.fuente_datos (codigo, nombre, url_base, formato_datos, frecuencia_minutos, esta_activa)
VALUES
 ('USGS','USGS Earthquake Catalog','https://earthquake.usgs.gov/fdsnws/event/1/query','JSON',360,TRUE),
 ('FIRMS','NASA FIRMS','https://firms.modaps.eosdis.nasa.gov/api/area/csv','CSV',360,FALSE)
ON CONFLICT (codigo) DO UPDATE SET
    nombre=EXCLUDED.nombre, url_base=EXCLUDED.url_base,
    formato_datos=EXCLUDED.formato_datos, frecuencia_minutos=EXCLUDED.frecuencia_minutos;

INSERT INTO core.tipo_fenomeno (codigo, nombre, descripcion)
VALUES
 ('SISMO','Sismo','Evento sísmico registrado por USGS.'),
 ('PUNTO_CALOR','Punto de calor','Detección térmica del sensor; no equivale a incendio confirmado.')
ON CONFLICT (codigo) DO NOTHING;
COMMIT;
