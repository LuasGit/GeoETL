"""Solo acceso lectura para la API; credenciales distintas de ETL."""
from collections.abc import Generator

import psycopg
from fastapi import HTTPException
from pipelines.comun.bd import conectar


def obtener_conexion() -> Generator[psycopg.Connection, None, None]:
    try:
        con = conectar()
    except (psycopg.Error, RuntimeError):
        raise HTTPException(503, 'Base de datos de consulta no disponible') from None
    try:
        with con:
            yield con
    finally:
        if not con.closed:
            con.close()
