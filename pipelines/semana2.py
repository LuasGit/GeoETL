"""GeoETL Semana 2: segunda fuente -> Bronze; todos los pendientes -> Silver + Core.

NO crea Gold: el esquema estrella se implementa en la semana 3.
Mantiene los procesos ETL fuera de la API pública.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid4

from pipelines.extractores.fuente_segunda import (
    BBOX_FIRMS, FIRMS_PRODUCTO, FIRMS_URL, METEO_URL, PUNTOS, FalloFuente,
    descargar, parametros_openmeteo, url_firms,
)
from pipelines.transformaciones.normalizar import (
    LoteInvalido, deduplicar_lote, normalizar,
)


def _db():
    from pipelines.comun.bd import conectar
    return conectar()


def _raiz() -> Path:
    return Path(os.getenv("DATA_DIR", "/app/datos"))


def _fuente(con, codigo: str):
    fila = con.execute("SELECT id_fuente FROM ops.fuente_datos WHERE codigo=%s", (codigo,)).fetchone()
    if not fila:
        raise RuntimeError(f"Fuente {codigo} no configurada. Ejecuta la migración 002.")
    return fila[0]


def _descargar_segunda(codigo: str, *, dias: int, atraso: int, ciudad: str, clave: str, producto=FIRMS_PRODUCTO):
    """Devuelve (bytes_originales, metadatos_sin_secretos, formato, extension, conteo, HTTP, intentos)."""
    if codigo == "FIRMS":
        if not 1 <= dias <= 5:
            raise ValueError("FIRMS admite --dias entre 1 y 5")
        url = url_firms(clave, dias, producto)
        parametros = {"producto": producto, "bbox": BBOX_FIRMS, "dias": dias}
        contenido, http, intentos = descargar(url)
        from pipelines.transformaciones.normalizar import normalizar_firms
        _, _, cuenta = normalizar_firms(contenido)
        # Un CSV válido con 0 detecciones es un resultado legítimo, no fallo HTTP.
        return contenido, parametros, "CSV", "csv", cuenta, http, intentos
    if codigo == "OPEN_METEO":
        parametros_http = parametros_openmeteo(dias, atraso, ciudad)
        contenido, http, intentos = descargar(METEO_URL, parametros_http)
        from pipelines.transformaciones.normalizar import normalizar_openmeteo
        _, _, cuenta = normalizar_openmeteo(contenido, ciudad)
        if cuenta == 0:
            raise FalloFuente("Open-Meteo devolvió una serie vacía", intentos, http)
        parametros = {**parametros_http, "ciudad": ciudad, "naturaleza": "serie_modelada_historica"}
        return contenido, parametros, "JSON", "json", cuenta, http, intentos
    if codigo == 'NASA_POWER':
        from pipelines.extractores.power import POWER_URL, parametros_power
        from pipelines.transformaciones.normalizar import normalizar_power
        params = parametros_power(dias, atraso, ciudad)
        contenido, http, intentos = descargar(POWER_URL, params)
        _, _, cuenta = normalizar_power(contenido, ciudad)
        if not cuenta:
            raise FalloFuente('NASA POWER devolvió una serie vacía', intentos, http)
        return contenido, {**params, 'ciudad':ciudad}, 'JSON', 'json', cuenta, http, intentos
    raise ValueError("Fuente desconocida")


def extraer_segunda(codigo: str, dias: int, atraso: int, ciudad: str, clave: str, producto=FIRMS_PRODUCTO):
    """Una ejecución en ops por extracción; FALLIDO queda registrado si falla la fuente."""
    from pipelines.comun.almacenamiento import guardar_bronze
    id_ejecucion = uuid4()
    ruta_bronze = None
    confirmado = False
    with _db() as con:
        id_fuente = _fuente(con, codigo)
        # metadatos de solicitud pre-registrados (nunca el secreto).
        meta_publica = ({"producto": producto, "bbox": BBOX_FIRMS, "dias": dias}
                        if codigo == "FIRMS" else {**parametros_openmeteo(dias, atraso, ciudad),
                                                    "ciudad": ciudad, "naturaleza": "serie_modelada_historica"})
        if codigo == "NASA_POWER":
            from pipelines.extractores.power import parametros_power
            meta_publica = {**parametros_power(dias, atraso, ciudad), "ciudad": ciudad}
        with con.transaction():
            con.execute("""INSERT INTO ops.ejecucion_ingesta
                   (id_ejecucion,id_fuente,estado,parametros_consulta)
                   VALUES (%s,%s,'EJECUTANDO',%s::jsonb)""",
                       (id_ejecucion, id_fuente, json.dumps(meta_publica)))
        try:
            contenido, parametros, formato, ext, cuenta, codigo_http, intentos = _descargar_segunda(
                codigo, dias=dias, atraso=atraso, ciudad=ciudad, clave=clave, producto=producto)
            ruta_bronze = guardar_bronze(contenido, _raiz(), codigo, id_ejecucion, ext)
            with con.transaction():
                con.execute("""INSERT INTO ops.archivo_crudo
                       (id_ejecucion,ruta_archivo,checksum_sha256,formato,tamanio_bytes)
                       VALUES (%s,%s,%s,%s,%s)""",
                            (id_ejecucion, ruta_bronze.ruta_relativa,
                             ruta_bronze.checksum_sha256, formato, ruta_bronze.tamanio_bytes))
                con.execute("""UPDATE ops.ejecucion_ingesta
                       SET estado='EXITO',fecha_fin=now(),registros_recibidos=%s,
                           registros_pendientes=%s,numero_intentos=%s,codigo_http=%s
                       WHERE id_ejecucion=%s""",
                            (cuenta, cuenta, intentos, codigo_http, id_ejecucion))
                # FIRMS estaba deshabilitado en las semillas de S1. Habilitarlo
                # solamente después de haber obtenido una respuesta válida.
                con.execute("UPDATE ops.fuente_datos SET esta_activa=TRUE WHERE id_fuente=%s",
                            (id_fuente,))
            confirmado = True
            print(f"BRONZE OK | fuente={codigo} | ejecución={id_ejecucion} | filas={cuenta}")
            print(f"archivo={ruta_bronze.ruta_relativa}")
            print(f"SHA-256={ruta_bronze.checksum_sha256}")
            return id_ejecucion
        except Exception as exc:
            if ruta_bronze and not confirmado:
                ruta_bronze.ruta_absoluta.unlink(missing_ok=True)
            # Evita mostrar URL/credencial de FIRMS en mensaje_error.
            mensaje = str(exc) if isinstance(exc, (FalloFuente, LoteInvalido, ValueError)) else type(exc).__name__
            with con.transaction():
                con.execute("""UPDATE ops.ejecucion_ingesta
                    SET estado='FALLIDO',fecha_fin=now(),mensaje_error=%s,
                        numero_intentos=%s,codigo_http=%s WHERE id_ejecucion=%s""",
                            (mensaje[:240], getattr(exc, "intentos", 0),
                             getattr(exc, "estado_http", None), id_ejecucion))
            raise


def _cargar_una(con, r, id_fuente, id_tipo, id_archivo, fecha_archivo):
    """Retorna 'cargado' o 'duplicado'. Evita sobrescribir con un replay histórico más antiguo."""
    from psycopg.types.json import Jsonb
    existente = con.execute("""SELECT o.id_observacion,
                   o.metadatos->>'_geoetl_hash', a.fecha_extraccion
               FROM core.observacion_ambiental o
               JOIN ops.archivo_crudo a ON a.id_archivo=o.id_archivo_origen
               WHERE o.id_fuente=%s AND o.clave_origen=%s FOR UPDATE OF o""",
                           (id_fuente, r.clave)).fetchone()
    if existente:
        id_observacion, hash_actual, fecha_actual_archivo = existente
        if hash_actual == r.huella or fecha_actual_archivo > fecha_archivo:
            return "duplicado"
    contenido = Jsonb({**r.metadata, "_geoetl_hash": r.huella})
    if existente:
        con.execute("""UPDATE core.observacion_ambiental SET
                     id_tipo_fenomeno=%s, id_archivo_origen=%s,
                     fecha_evento=%s, fecha_observacion=%s,
                     geometria=ST_SetSRID(ST_MakePoint(%s,%s),4326),
                     titulo=%s, metadatos=%s, fecha_actualizacion=now()
                   WHERE id_observacion=%s""",
                    (id_tipo, id_archivo, r.fecha_evento, r.fecha_observacion,
                     r.longitud, r.latitud, r.titulo, contenido, id_observacion))
        # Cuando una actualización elimina una métrica anterior, eliminamos la obsoleta.
        con.execute("DELETE FROM core.medicion_observacion WHERE id_observacion=%s", (id_observacion,))
    else:
        id_observacion = con.execute("""INSERT INTO core.observacion_ambiental
                (id_fuente,id_tipo_fenomeno,id_archivo_origen,clave_origen,
                 fecha_evento,fecha_observacion,geometria,titulo,metadatos)
                VALUES (%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326),%s,%s)
                RETURNING id_observacion""",
                    (id_fuente, id_tipo, id_archivo, r.clave,
                     r.fecha_evento, r.fecha_observacion, r.longitud, r.latitud,
                     r.titulo, contenido)).fetchone()[0]
    for codigo_metrica, (valor, unidad) in r.mediciones.items():
        con.execute("""INSERT INTO core.medicion_observacion
                    (id_observacion,codigo_metrica,valor_numerico,unidad,fecha_medicion)
                    VALUES (%s,%s,%s,%s,%s)""",
                    (id_observacion, codigo_metrica, valor, unidad, r.fecha_evento))
    return "cargado"


class IntegridadBronzeError(RuntimeError):
    pass


def procesar_ejecucion(id_ejecucion: UUID):
    """Bronze -> Silver (Parquet) -> Core, en una ejecución trazable y repetible.

    Conserva E1 en ops. La escritura Silver se realiza antes del commit SQL; ante una
    interrupción podría quedar un Parquet sin reflejo en Core. Reejecutar corrige.
    """
    from pipelines.transformaciones.parquet import crear_parquet, publicar_parquet
    with _db() as con:
        ejec = con.execute("""SELECT f.codigo, e.parametros_consulta,
                            e.registros_recibidos, a.id_archivo, a.ruta_archivo,
                            a.checksum_sha256, a.fecha_extraccion, e.estado
                          FROM ops.ejecucion_ingesta e
                          JOIN ops.fuente_datos f ON f.id_fuente=e.id_fuente
                          JOIN ops.archivo_crudo a ON a.id_ejecucion=e.id_ejecucion
                          WHERE e.id_ejecucion=%s""", (id_ejecucion,)).fetchall()
        if len(ejec) != 1:
            raise RuntimeError("Ejecución sin exactamente un archivo Bronze: " + str(id_ejecucion))
        codigo, parametros, recibidos, id_archivo, ruta, checksum, fecha_archivo, estado_anterior = ejec[0]
        if estado_anterior not in ("EXITO", "PARCIAL"):
            raise RuntimeError("La extracción todavía no es reprocesable")
        ruta_archivo = _raiz() / ruta
        if not ruta_archivo.is_file():
            raise IntegridadBronzeError("Archivo Bronze no disponible")
        original = ruta_archivo.read_bytes()
        if hashlib.sha256(original).hexdigest() != str(checksum).strip():
            raise IntegridadBronzeError("Checksum SHA-256 no coincide con el original; se aborta sin modificar Core")
        aceptados, rechazados, total = normalizar(codigo, original, parametros)
        if total != recibidos:
            raise RuntimeError(f"Conteos inconsistentes: fuente={total} ops={recibidos}")
        unicos, repetidos_dentro = deduplicar_lote(aceptados)
        salida = (_raiz() / "silver" / codigo.lower() /
                  fecha_archivo.astimezone(timezone.utc).strftime("%Y/%m/%d") /
                  f"{id_ejecucion}.parquet")
        temporal = crear_parquet(unicos, salida)
        try:
            with con.transaction():
                # Bloquea la ejecución para evitar procesamiento concurrente del mismo lote.
                con.execute("SELECT id_ejecucion FROM ops.ejecucion_ingesta WHERE id_ejecucion=%s FOR UPDATE",
                            (id_ejecucion,)).fetchone()
                id_fuente = _fuente(con, codigo)
                tipos = {fila[0]: fila[1] for fila in con.execute(
                    "SELECT codigo,id_tipo_fenomeno FROM core.tipo_fenomeno").fetchall()}
                con.execute("DELETE FROM ops.registro_calidad WHERE id_ejecucion=%s", (id_ejecucion,))
                for e in rechazados:
                    con.execute("""INSERT INTO ops.registro_calidad
                            (id_ejecucion,id_archivo,clave_registro,regla,resultado,detalle)
                            VALUES (%s,%s,%s,%s,'RECHAZADO',%s)""",
                                (id_ejecucion, id_archivo, e.clave, e.regla, e.detalle))
                cargados = 0
                duplicados = repetidos_dentro
                for r in unicos:
                    if r.fenomeno not in tipos:
                        raise RuntimeError(f"Tipo de fenómeno no configurado: {r.fenomeno}")
                    clasif = _cargar_una(con, r, id_fuente, tipos[r.fenomeno], id_archivo, fecha_archivo)
                    if clasif == "cargado":
                        cargados += 1
                    else:
                        duplicados += 1
                con.execute("""UPDATE ops.ejecucion_ingesta SET
                        registros_cargados=%s, registros_duplicados=%s,
                        registros_rechazados=%s, registros_pendientes=0,
                        estado=%s WHERE id_ejecucion=%s""",
                        (cargados, duplicados, len(rechazados),
                         "PARCIAL" if rechazados else "EXITO", id_ejecucion))
                # Publicar Silver dentro del bloque transaccional: el archivo puede
                # rehacerse desde Bronze en caso de un fallo posterior de commit.
                publicar_parquet(temporal, salida)
        finally:
            temporal.unlink(missing_ok=True)
        print(f"SILVER/CORE OK | {codigo} | ejecución={id_ejecucion}")
        print(f"  recibidos={recibidos} cargados={cargados} duplicados={duplicados} rechazados={len(rechazados)}")
        print(f"  Parquet: {salida.relative_to(_raiz())}")
        return {"recibidos": recibidos, "cargados": cargados,
                "duplicados": duplicados, "rechazados": len(rechazados)}


def procesar_pendientes():
    with _db() as con:
        ids = [r[0] for r in con.execute("""SELECT id_ejecucion
                       FROM ops.ejecucion_ingesta
                       WHERE registros_pendientes>0 AND estado IN ('EXITO','PARCIAL')
                       ORDER BY fecha_inicio""").fetchall()]
    if not ids:
        print("No hay extracciones Bronze pendientes de Silver.")
    fallos = []
    for i in ids:
        try:
            procesar_ejecucion(i)
        except IntegridadBronzeError as exc:
            with _db() as con:
                with con.transaction():
                    con.execute("""UPDATE ops.ejecucion_ingesta SET estado='FALLIDO',
                        registros_rechazados=registros_rechazados+registros_pendientes,
                        registros_pendientes=0,mensaje_error=%s WHERE id_ejecucion=%s""",('CUARENTENA BRONZE: '+str(exc),i))
                    con.execute("""INSERT INTO ops.registro_calidad (id_ejecucion,regla,resultado,detalle)
                        VALUES (%s,'integridad_bronze','RECHAZADO',%s)""",(i,str(exc)))
            fallos.append((i, str(exc)))
        except Exception as exc:
            fallos.append((i, str(exc)))
            print(f"ERROR al procesar lote {i}: {exc}", file=sys.stderr)
    if fallos:
        raise RuntimeError(f"No se pudieron procesar {len(fallos)} lotes. Los demás continuaron.")


def resumen():
    with _db() as con:
        for fila in con.execute("""SELECT f.codigo, count(e.*),
                     coalesce(sum(e.registros_recibidos),0),
                     coalesce(sum(e.registros_cargados),0),
                     coalesce(sum(e.registros_duplicados),0),
                     coalesce(sum(e.registros_rechazados),0),
                     coalesce(sum(e.registros_pendientes),0)
                   FROM ops.fuente_datos f LEFT JOIN ops.ejecucion_ingesta e USING (id_fuente)
                   GROUP BY f.codigo ORDER BY f.codigo""").fetchall():
            print("Fuente=%s | ejecuciones=%s recibidos=%s cargados=%s repetidos=%s rechazados=%s pendientes=%s" % fila)
        print("Core observaciones:", con.execute("SELECT count(*) FROM core.observacion_ambiental").fetchone()[0])
        print("Core mediciones:", con.execute("SELECT count(*) FROM core.medicion_observacion").fetchone()[0])


def main():
    parser = argparse.ArgumentParser(description="GeoETL Semana 2: segunda fuente, Silver y Core")
    sub = parser.add_subparsers(dest="accion", required=True)
    ext = sub.add_parser("extraer-segunda", help="FIRMS con clave o Open-Meteo sin clave")
    ext.add_argument("--fuente", choices=["auto", "firms", "openmeteo"], default="auto")
    ext.add_argument("--dias", type=int, default=2)
    ext.add_argument("--atraso", type=int, default=10, help="Solo Open-Meteo: retraso de archivo en días")
    ext.add_argument("--ciudad", choices=list(PUNTOS), default="la_paz")
    sub.add_parser("procesar-pendientes", help="Procesar todos los Bronze no consolidados")
    repro = sub.add_parser("reprocesar", help="Regenerar Silver/Core sin consultar la API")
    repro.add_argument("--id-ejecucion", type=UUID, required=True)
    sub.add_parser("resumen", help="Mostrar métricas de ingesta y Core")
    args = parser.parse_args()
    try:
        if args.accion == "extraer-segunda":
            clave = os.getenv("FIRMS_MAP_KEY", "").strip()
            if args.fuente == "firms" and not clave:
                raise ValueError("Falta FIRMS_MAP_KEY; usa --fuente openmeteo o --fuente auto")
            codigo = ("FIRMS" if args.fuente == "firms" or
                      (args.fuente == "auto" and clave) else "OPEN_METEO")
            dias = min(args.dias, 5) if codigo == "FIRMS" else args.dias
            if codigo == "FIRMS":
                try:
                    extraer_segunda(codigo, dias, args.atraso, args.ciudad, clave)
                except Exception:
                    if args.fuente != "auto":
                        raise
                    print("FIRMS no disponible: contingencia Open-Meteo documentada.", file=sys.stderr)
                    extraer_segunda("OPEN_METEO", args.dias, args.atraso, args.ciudad, "")
            else:
                extraer_segunda(codigo, dias, args.atraso, args.ciudad, "")
        elif args.accion == "procesar-pendientes":
            procesar_pendientes()
        elif args.accion == "reprocesar":
            procesar_ejecucion(args.id_ejecucion)
        elif args.accion == "resumen":
            resumen()
        return 0
    except Exception as exc:
        # No imprimir detalles HTTP crudos que puedan incluir secretos.
        mensaje = str(exc) if isinstance(exc, (FalloFuente, LoteInvalido, ValueError, RuntimeError, FileNotFoundError)) else type(exc).__name__
        print(f"ERROR Semana 2: {mensaje}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
