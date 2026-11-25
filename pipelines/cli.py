"""Entrada operativa. Semana 1: USGS -> Bronze + trazabilidad en ops."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from psycopg.types.json import Jsonb

from pipelines.comun.almacenamiento import guardar_bronze
from pipelines.comun.bd import conectar
from pipelines.extractores.usgs import ErrorExtraccion, descargar_usgs, parametros_usgs


def ejecutar_usgs(dias: int, ahora=None) -> None:
    parametros = parametros_usgs(dias, ahora=ahora)
    id_ejecucion = uuid4()
    raiz = Path(os.getenv("DATA_DIR", "/app/datos"))
    archivo_bronze = None
    transaccion_confirmada = False

    with conectar() as conexion:
        with conexion.transaction():
            fila = conexion.execute(
                "SELECT id_fuente FROM ops.fuente_datos WHERE codigo = %s AND esta_activa = TRUE",
                ("USGS",),
            ).fetchone()
            if not fila:
                raise RuntimeError("USGS no está configurado. Ejecuta la migración y las semillas.")
            id_fuente = fila[0]
            conexion.execute(
                """INSERT INTO ops.ejecucion_ingesta
                   (id_ejecucion,id_fuente,estado,parametros_consulta)
                   VALUES (%s,%s,'EJECUTANDO',%s)""",
                (id_ejecucion, id_fuente, Jsonb(parametros)),
            )
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0), follow_redirects=True) as cliente:
                respuesta = descargar_usgs(cliente, parametros)

            archivo_bronze = guardar_bronze(
                respuesta.original, raiz, "usgs", id_ejecucion, "geojson"
            )
            with conexion.transaction():
                conexion.execute(
                    """INSERT INTO ops.archivo_crudo
                       (id_ejecucion,ruta_archivo,checksum_sha256,formato,tamanio_bytes)
                       VALUES (%s,%s,%s,'GEOJSON',%s)""",
                    (id_ejecucion, archivo_bronze.ruta_relativa,
                     archivo_bronze.checksum_sha256, archivo_bronze.tamanio_bytes),
                )
                conexion.execute(
                    """UPDATE ops.ejecucion_ingesta
                       SET estado='EXITO', fecha_fin=now(),
                           registros_recibidos=%s, registros_pendientes=%s,
                           numero_intentos=%s, codigo_http=%s
                       WHERE id_ejecucion=%s""",
                    (respuesta.registros_recibidos, respuesta.registros_recibidos,
                     respuesta.intentos, respuesta.codigo_http, id_ejecucion),
                )
            transaccion_confirmada = True
            print(f"E1 OK | ejecución={id_ejecucion}")
            print(f"Registros recibidos: {respuesta.registros_recibidos} (aún pendientes de Silver)")
            print(f"Bronze: {archivo_bronze.ruta_relativa}")
            print(f"SHA-256: {archivo_bronze.checksum_sha256}")
        except Exception as exc:
            # Si la escritura física ocurrió pero PostgreSQL falló, evita un archivo huérfano.
            if archivo_bronze and not transaccion_confirmada:
                archivo_bronze.ruta_absoluta.unlink(missing_ok=True)
            with conexion.transaction():
                conexion.execute(
                    """UPDATE ops.ejecucion_ingesta
                       SET estado='FALLIDO', fecha_fin=now(), mensaje_error=%s,
                           numero_intentos=%s, codigo_http=%s
                       WHERE id_ejecucion=%s""",
                    (str(exc)[:1000], getattr(exc, "intentos", 0),
                     getattr(exc, "codigo_http", None), id_ejecucion),
                )
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="GeoETL | CLI de extracción")
    sub = parser.add_subparsers(dest="comando", required=True)
    usgs = sub.add_parser("extraer-usgs", help="Descarga un lote USGS hacia Bronze")
    usgs.add_argument("--dias", type=int, default=7, help="Ventana UTC, 1-30 (defecto: 7)")
    args = parser.parse_args()
    if args.comando == "extraer-usgs":
        try:
            ejecutar_usgs(args.dias)
            return 0
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
