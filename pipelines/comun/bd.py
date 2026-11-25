"""Conexión para CLI de ingesta (no usar desde endpoints públicos)."""
import os
import psycopg


def conectar():
    necesarios = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    faltantes = [n for n in necesarios if not os.getenv(n)]
    if faltantes:
        raise RuntimeError("Variables PostgreSQL faltantes: " + ", ".join(faltantes))
    return psycopg.connect(
        host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"], user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"], autocommit=True,
        connect_timeout=10,
    )
