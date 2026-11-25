\set ON_ERROR_STOP on
BEGIN;
-- Mantener a USGS y FIRMS de la semana 1. Activar FIRMS solo con credencial disponible.
INSERT INTO ops.fuente_datos
    (codigo, nombre, url_base, formato_datos, frecuencia_minutos, esta_activa)
VALUES
    ('OPEN_METEO', 'Open-Meteo Historical Weather',
     'https://archive-api.open-meteo.com/v1/archive', 'JSON', 1440, TRUE)
ON CONFLICT (codigo) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    url_base = EXCLUDED.url_base,
    formato_datos = EXCLUDED.formato_datos,
    frecuencia_minutos = EXCLUDED.frecuencia_minutos;

INSERT INTO core.tipo_fenomeno (codigo, nombre, descripcion)
VALUES ('METEO_MODELO', 'Observación meteorológica modelada',
        'Serie horaria histórica estimada por modelos/reanálisis; no es medición directa en estación ni alerta oficial.')
ON CONFLICT (codigo) DO NOTHING;

-- SQL de apoyo: identificador natural (fuente + clave) y métrica única.
-- Las restricciones de integridad de Core están en 001_base.sql.
CREATE INDEX IF NOT EXISTS ix_calidad_ejecucion
    ON ops.registro_calidad(id_ejecucion);
COMMIT;
