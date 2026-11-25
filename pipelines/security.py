"""Crea cuenta exclusiva SELECT para la API; solo CLI administrativa.

Requiere credenciales de migración en PGUSER/PGPASSWORD y API_DB_PASSWORD
establecida en el ambiente. Idempotente, sin interpolar contraseñas en SQL plano.
"""
import os

from psycopg import sql
from pipelines.comun.bd import conectar


def aprovisionar():
    password = os.environ.get('API_DB_PASSWORD', '').strip()
    if not password or password.lower().startswith('cambia_') or password in ('CAMBIAR', 'password'):
        raise RuntimeError('Establece API_DB_PASSWORD segura en .env')
    with conectar() as con:
        # CREATE ROLE no se ejecuta en transacción abierta cuando se requiere
        # control explícito; conexión de CLI admin, nunca accesible por HTTP.
        existente = con.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', ('geoetl_reader',)).fetchone()
        if not existente:
            con.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier('geoetl_reader')))
        con.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(
            sql.Identifier('geoetl_reader'), sql.Literal(password)))
        con.execute(sql.SQL('REVOKE CREATE ON SCHEMA public FROM {}').format(sql.Identifier('geoetl_reader')))
        con.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO geoetl_reader').format(sql.Identifier(os.environ['PGDATABASE'])))
        for esquema in ('ops', 'core', 'dw'):
            con.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO geoetl_reader').format(sql.Identifier(esquema)))
            con.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO geoetl_reader').format(sql.Identifier(esquema)))
            # No privilegios de INSERT/UPDATE/DELETE, incluso si existía este usuario antes.
            con.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM geoetl_reader').format(sql.Identifier(esquema)))
            con.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO geoetl_reader').format(sql.Identifier(esquema)))
        con.execute('ALTER ROLE geoetl_reader SET default_transaction_read_only = on')
    print('Permisos API: geoetl_reader solo lectura (ops/core/dw).')


if __name__ == '__main__':
    aprovisionar()
