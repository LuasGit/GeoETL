"""Escribe Silver en Parquet con DuckDB sin Pandas ni PyArrow."""
from __future__ import annotations

from pathlib import Path
import json
import os
from uuid import uuid4


def crear_parquet(registros, destino: Path) -> Path:
    import duckdb
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + "." + uuid4().hex + ".tmp.parquet")
    con = duckdb.connect(":memory:")
    try:
        con.execute("""CREATE TABLE silver (
          clave_origen VARCHAR NOT NULL,
          codigo_fenomeno VARCHAR NOT NULL,
          fecha_evento_utc TIMESTAMPTZ NOT NULL,
          fecha_observacion_utc TIMESTAMPTZ,
          latitud DOUBLE NOT NULL,
          longitud DOUBLE NOT NULL,
          titulo VARCHAR,
          metadatos_json VARCHAR NOT NULL,
          mediciones_json VARCHAR NOT NULL,
          huella_sha256 VARCHAR NOT NULL)""")
        filas = [(
            r.clave, r.fenomeno, r.fecha_evento, r.fecha_observacion,
            r.latitud, r.longitud, r.titulo,
            json.dumps(r.metadata, ensure_ascii=False, sort_keys=True),
            json.dumps({k: {"valor": v, "unidad": u} for k, (v, u) in r.mediciones.items()},
                       ensure_ascii=False, sort_keys=True),
            r.huella,
        ) for r in registros]
        if filas:
            con.executemany("INSERT INTO silver VALUES (?,?,?,?,?,?,?,?,?,?)", filas)
        ruta_sql = str(temporal).replace("'", "''")
        con.execute(f"COPY (SELECT * FROM silver ORDER BY clave_origen) TO '{ruta_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        return temporal
    except Exception:
        temporal.unlink(missing_ok=True)
        raise
    finally:
        con.close()


def publicar_parquet(temporal: Path, destino: Path):
    os.replace(temporal, destino)
