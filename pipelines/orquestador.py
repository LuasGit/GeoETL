"""Orquestación secuencial manual o programada con aislamiento de fallos por fuente."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys

from pipelines.cli import ejecutar_usgs
from pipelines.semana2 import extraer_segunda, procesar_pendientes
from pipelines.cargas.gold import cargar_gold


def ejecutar_pipeline(*, dias_usgs=7, dias_segunda=2, fuente='auto', atraso=10, ciudad='la_paz'):
    from pipelines.comun.bd import conectar
    bloqueo=conectar()
    try:
        obtenido=bloqueo.execute('SELECT pg_try_advisory_lock(442019,1)').fetchone()[0]
        if not obtenido:
            print('Existe otra ejecución del pipeline en curso: se omite esta ejecución.',flush=True)
            return [('ORQUESTACION','ocupado')]
        return _procesar_pipeline(dias_usgs=dias_usgs,dias_segunda=dias_segunda,
                                 fuente=fuente,atraso=atraso,ciudad=ciudad)
    finally:
        bloqueo.close()


def _procesar_pipeline(*, dias_usgs=7, dias_segunda=2, fuente='auto', atraso=10, ciudad='la_paz'):
    fallos=[]
    print('PIPELINE INICIO',datetime.now(timezone.utc).isoformat(),flush=True)
    try:
        ejecutar_usgs(dias_usgs)
    except Exception as e:
        fallos.append(('USGS',type(e).__name__))
        print('USGS FALLÓ:',type(e).__name__,file=sys.stderr,flush=True)
    from pipelines.operaciones import extraer
    fuentes = ['OPEN_METEO','NASA_POWER'] if fuente=='auto' else ['FIRMS' if fuente=='firms' else 'OPEN_METEO']
    if fuente=='auto' and os.getenv('FIRMS_MAP_KEY','').strip():
        fuentes.append('FIRMS')
    for etiqueta in extraer(fuentes, min(dias_segunda,14), atraso, lambda p,e: print(p,e,flush=True)):
        fallos.append((etiqueta,'extraccion_fallida'))
    # Aun ante una falla de extracción, procesar archivos Bronze existentes.
    try:
        procesar_pendientes()
    except Exception as e:
        fallos.append(('SILVER_CORE',type(e).__name__))
    try:
        resultado=cargar_gold()
        print('GOLD:',json.dumps(resultado),flush=True)
    except Exception as e:
        fallos.append(('GOLD',type(e).__name__))
        print('Gold falló:',type(e).__name__,file=sys.stderr,flush=True)
    print('PIPELINE FIN',datetime.now(timezone.utc).isoformat(), 'fallos=',fallos,flush=True)
    return fallos


def main():
    p=argparse.ArgumentParser(description='Pipeline completo GeoETL')
    p.add_argument('--dias-usgs',type=int,default=7)
    p.add_argument('--dias-segunda',type=int,default=2)
    p.add_argument('--fuente',choices=['auto','firms','openmeteo'],default='auto')
    p.add_argument('--atraso',type=int,default=10)
    p.add_argument('--ciudad',choices=['la_paz','cochabamba','santa_cruz'],default='la_paz')
    a=p.parse_args()
    fallos=ejecutar_pipeline(dias_usgs=a.dias_usgs,dias_segunda=a.dias_segunda,
                           fuente=a.fuente,atraso=a.atraso,ciudad=a.ciudad)
    return 1 if fallos else 0

if __name__=='__main__':
    raise SystemExit(main())
