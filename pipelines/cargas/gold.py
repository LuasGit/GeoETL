"""Carga dimensional idempotente Core -> Gold (PostgreSQL/PostGIS).

El grano de hecho_observacion es una observación canónica única.
La actualización de dimensiones y hechos ocurre en una transacción, con lock
advisory para proteger de cargas concurrentes.
"""
from __future__ import annotations

from pipelines.comun.bd import conectar

SQL_DIM_FECHA = """
INSERT INTO dw.dim_fecha (clave_fecha,fecha,anio,trimestre,mes,dia,dia_semana)
SELECT DISTINCT to_char((fecha_evento AT TIME ZONE 'UTC')::date,'YYYYMMDD')::integer AS clave,
       (fecha_evento AT TIME ZONE 'UTC')::date AS fecha,
       extract(year FROM fecha_evento AT TIME ZONE 'UTC')::smallint,
       extract(quarter FROM fecha_evento AT TIME ZONE 'UTC')::smallint,
       extract(month FROM fecha_evento AT TIME ZONE 'UTC')::smallint,
       extract(day FROM fecha_evento AT TIME ZONE 'UTC')::smallint,
       extract(isodow FROM fecha_evento AT TIME ZONE 'UTC')::smallint
FROM core.observacion_ambiental
ON CONFLICT (clave_fecha) DO NOTHING
"""
SQL_DIM_FUENTE = """
INSERT INTO dw.dim_fuente (codigo_fuente,nombre_fuente,proveedor)
SELECT DISTINCT codigo,nombre,nombre FROM ops.fuente_datos
ON CONFLICT (codigo_fuente) DO UPDATE SET
 nombre_fuente=EXCLUDED.nombre_fuente, proveedor=EXCLUDED.proveedor
"""
SQL_DIM_FENOMENO = """
INSERT INTO dw.dim_fenomeno (codigo_fenomeno,nombre,descripcion)
SELECT codigo,nombre,descripcion FROM core.tipo_fenomeno
ON CONFLICT (codigo_fenomeno) DO UPDATE SET
 nombre=EXCLUDED.nombre, descripcion=EXCLUDED.descripcion
"""
SQL_HECHOS = """
INSERT INTO dw.hecho_observacion AS actual
    (clave_fecha,clave_fuente,clave_fenomeno,id_observacion_origen,cantidad_observaciones)
SELECT to_char((o.fecha_evento AT TIME ZONE 'UTC')::date,'YYYYMMDD')::integer,
       f.clave_fuente, t.clave_fenomeno,o.id_observacion,1
FROM core.observacion_ambiental o
JOIN ops.fuente_datos origen ON origen.id_fuente=o.id_fuente
JOIN core.tipo_fenomeno tipo ON tipo.id_tipo_fenomeno=o.id_tipo_fenomeno
JOIN dw.dim_fuente f ON f.codigo_fuente=origen.codigo
JOIN dw.dim_fenomeno t ON t.codigo_fenomeno=tipo.codigo
ON CONFLICT (id_observacion_origen) DO UPDATE SET
 clave_fecha=EXCLUDED.clave_fecha,
 clave_fuente=EXCLUDED.clave_fuente,
 clave_fenomeno=EXCLUDED.clave_fenomeno,
 fecha_actualizacion=CASE
  WHEN (actual.clave_fecha,actual.clave_fuente,actual.clave_fenomeno)
    IS DISTINCT FROM (EXCLUDED.clave_fecha,EXCLUDED.clave_fuente,EXCLUDED.clave_fenomeno)
  THEN now() ELSE actual.fecha_actualizacion END
"""


def cargar_gold(con=None) -> dict[str, int]:
    """Permite inyectar conexión externa para pruebas de integración."""
    propia = con is None
    if propia:
        con = conectar()
    try:
        with con.transaction():
            con.execute("SELECT pg_advisory_xact_lock(442019, 3)")
            con.execute(SQL_DIM_FECHA)
            con.execute(SQL_DIM_FUENTE)
            con.execute(SQL_DIM_FENOMENO)
            con.execute(SQL_HECHOS)
            filas = con.execute("""SELECT
                 (SELECT count(*) FROM core.observacion_ambiental),
                 (SELECT count(*) FROM dw.hecho_observacion),
                 (SELECT count(*) FROM dw.dim_fecha),
                 (SELECT count(*) FROM dw.dim_fuente),
                 (SELECT count(*) FROM dw.dim_fenomeno)""").fetchone()
            if filas[0] != filas[1]:
                raise RuntimeError("Integridad Gold: cantidad de hechos distinta a Core")
            resultados = dict(zip(("core", "hechos", "fechas", "fuentes", "fenomenos"), filas))
        return resultados
    finally:
        if propia:
            con.close()


def main():
    resultado = cargar_gold()
    print("GOLD OK | " + " | ".join(f"{k}={v}" for k,v in resultado.items()))


if __name__ == "__main__":
    main()
