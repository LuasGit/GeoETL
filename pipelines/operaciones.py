"""Operación por etapas; mismo candado que el programador v1."""
import os
from pipelines.cli import ejecutar_usgs
from pipelines.semana2 import extraer_segunda, procesar_pendientes
from pipelines.cargas.gold import cargar_gold
from pipelines.extractores.fuente_segunda import FIRMS_PRODUCTOS, PUNTOS


def extraer(fuentes, dias, atraso, informar):
    fallos=[]
    def intentar(etiqueta, fn):
        informar(etiqueta, 'EJECUTANDO')
        try:
            fn()
        except Exception as exc:
            fallos.append(etiqueta)
            informar(etiqueta, 'FALLIDO: '+type(exc).__name__)
        else:
            informar(etiqueta, 'EXITO')
    if 'USGS' in fuentes:
        intentar('USGS', lambda: ejecutar_usgs(dias))
    if 'FIRMS' in fuentes:
        clave=os.getenv('FIRMS_MAP_KEY','').strip()
        if not clave:
            fallos.append('FIRMS: falta MAP_KEY')
            informar('FIRMS','FALLIDO: configura FIRMS_MAP_KEY')
        else:
            for producto in FIRMS_PRODUCTOS:
                intentar(producto, lambda: extraer_segunda('FIRMS', min(dias,5), atraso,'la_paz',clave,producto))
    for fuente in ('OPEN_METEO','NASA_POWER'):
        if fuente in fuentes:
            for ciudad in PUNTOS:
                intentar(f'{fuente} / {ciudad}', lambda: extraer_segunda(fuente,dias,atraso,ciudad,''))
    return fallos


def ejecutar(accion, fuentes, dias, atraso, informar):
    from pipelines.comun.bd import conectar
    fallos=[]
    with conectar() as con:
        if not con.execute('SELECT pg_try_advisory_lock(442019,1)').fetchone()[0]:
            raise RuntimeError('Otro pipeline está en curso')
        try:
            if accion in ('extraer','completo'):
                fallos.extend(extraer(fuentes,dias,atraso,informar))
            for fase, fn in [('limpiar',procesar_pendientes),('publicar',cargar_gold)]:
                if accion in (fase,'completo'):
                    informar(fase,'EJECUTANDO')
                    try:
                        fn()
                    except Exception as exc:
                        fallos.append(fase)
                        informar(fase,'FALLIDO: '+type(exc).__name__)
                    else:
                        informar(fase,'EXITO')
        finally:
            con.execute('SELECT pg_advisory_unlock(442019,1)')
    return fallos
