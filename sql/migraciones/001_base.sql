-- GeoETL | Semana 1 | Idempotente (no destruye datos existentes).
\set ON_ERROR_STOP on
BEGIN;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS ops.fuente_datos (
    id_fuente UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    url_base TEXT NOT NULL,
    formato_datos VARCHAR(10) NOT NULL CHECK (formato_datos IN ('JSON','CSV')),
    frecuencia_minutos INTEGER NOT NULL CHECK (frecuencia_minutos > 0),
    esta_activa BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS ops.ejecucion_ingesta (
    id_ejecucion UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_fuente UUID NOT NULL REFERENCES ops.fuente_datos(id_fuente),
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_fin TIMESTAMPTZ,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('EJECUTANDO','EXITO','PARCIAL','FALLIDO')),
    registros_recibidos INTEGER NOT NULL DEFAULT 0 CHECK (registros_recibidos >= 0),
    registros_cargados INTEGER NOT NULL DEFAULT 0 CHECK (registros_cargados >= 0),
    registros_duplicados INTEGER NOT NULL DEFAULT 0 CHECK (registros_duplicados >= 0),
    registros_rechazados INTEGER NOT NULL DEFAULT 0 CHECK (registros_rechazados >= 0),
    -- Adaptación: en S1 quedan pendientes de Silver/Core.
    registros_pendientes INTEGER NOT NULL DEFAULT 0 CHECK (registros_pendientes >= 0),
    numero_intentos INTEGER NOT NULL DEFAULT 0 CHECK (numero_intentos >= 0),
    codigo_http INTEGER,
    parametros_consulta JSONB NOT NULL DEFAULT '{}'::jsonb,
    mensaje_error TEXT,
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio),
    CHECK (registros_recibidos = registros_cargados + registros_duplicados + registros_rechazados + registros_pendientes)
);

CREATE INDEX IF NOT EXISTS ix_ejecucion_fuente_fecha
    ON ops.ejecucion_ingesta (id_fuente, fecha_inicio DESC);

CREATE TABLE IF NOT EXISTS ops.archivo_crudo (
    id_archivo UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_ejecucion UUID NOT NULL REFERENCES ops.ejecucion_ingesta(id_ejecucion),
    ruta_archivo TEXT NOT NULL UNIQUE,
    checksum_sha256 CHAR(64) NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    formato VARCHAR(15) NOT NULL,
    tamanio_bytes BIGINT NOT NULL CHECK (tamanio_bytes >= 0),
    fecha_extraccion TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.registro_calidad (
    id_registro BIGSERIAL PRIMARY KEY,
    id_ejecucion UUID NOT NULL REFERENCES ops.ejecucion_ingesta(id_ejecucion),
    id_archivo UUID REFERENCES ops.archivo_crudo(id_archivo),
    clave_registro TEXT,
    regla VARCHAR(80) NOT NULL,
    resultado VARCHAR(20) NOT NULL CHECK (resultado IN ('RECHAZADO', 'ADVERTENCIA')),
    detalle TEXT NOT NULL,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.tipo_fenomeno (
    id_tipo_fenomeno SMALLSERIAL PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS core.observacion_ambiental (
    id_observacion UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_fuente UUID NOT NULL REFERENCES ops.fuente_datos(id_fuente),
    id_tipo_fenomeno SMALLINT NOT NULL REFERENCES core.tipo_fenomeno(id_tipo_fenomeno),
    -- El archivo debe respaldar la versión ACTUAL de esta observación.
    id_archivo_origen UUID NOT NULL REFERENCES ops.archivo_crudo(id_archivo),
    clave_origen VARCHAR(180) NOT NULL,
    fecha_evento TIMESTAMPTZ NOT NULL,
    fecha_observacion TIMESTAMPTZ,
    geometria GEOMETRY(Point,4326) NOT NULL,
    titulo VARCHAR(180),
    metadatos JSONB NOT NULL DEFAULT '{}'::jsonb,
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_observacion_fuente_origen UNIQUE (id_fuente, clave_origen),
    CONSTRAINT ck_geometria_valida CHECK (ST_IsValid(geometria))
);
CREATE INDEX IF NOT EXISTS ix_observacion_geom
    ON core.observacion_ambiental USING GIST (geometria);
CREATE INDEX IF NOT EXISTS ix_observacion_fecha
    ON core.observacion_ambiental (fecha_evento DESC);
CREATE INDEX IF NOT EXISTS ix_observacion_fenomeno_fecha
    ON core.observacion_ambiental (id_tipo_fenomeno, fecha_evento DESC);

CREATE TABLE IF NOT EXISTS core.medicion_observacion (
    id_medicion BIGSERIAL PRIMARY KEY,
    id_observacion UUID NOT NULL REFERENCES core.observacion_ambiental(id_observacion) ON DELETE CASCADE,
    codigo_metrica VARCHAR(40) NOT NULL,
    valor_numerico NUMERIC NOT NULL,
    unidad VARCHAR(30) NOT NULL,
    fecha_medicion TIMESTAMPTZ,
    -- Política del MVP: un valor consolidado por métrica y observación.
    CONSTRAINT uq_observacion_metrica UNIQUE (id_observacion, codigo_metrica)
);
COMMIT;
