"""Backfill USGS por ventanas UTC ≤7 días; conserva originales y trazabilidad.

La fecha --hasta es EXCLUSIVA; no procesa fechas posteriores al día actual.
No ejecuta Silver/Gold por sí solo.
"""
from __future__ import annotations

import argparse
from datetime import datetime,date,time,timedelta,timezone
from pipelines.cli import ejecutar_usgs


def ventanas(desde: date,hasta: date,dias_por_lote: int=7):
    if not 1<=dias_por_lote<=7:
        raise ValueError('dias_por_lote 1..7')
    if not desde<hasta or (hasta-desde).days>366:
        raise ValueError('Fechas inválidas; máximo 366 días por operación')
    inicio=desde
    while inicio<hasta:
        fin=min(inicio+timedelta(days=dias_por_lote),hasta)
        yield (inicio,fin,(fin-inicio).days)
        inicio=fin


def main():
    p=argparse.ArgumentParser(description='Carga histórica USGS en ventanas reproducibles, sin modificar originales')
    p.add_argument('--desde',required=True,help='AAAA-MM-DD inclusivo')
    p.add_argument('--hasta',required=True,help='AAAA-MM-DD exclusivo')
    p.add_argument('--lote',type=int,default=7,help='Días por lote (1..7)')
    args=p.parse_args()
    inicio=date.fromisoformat(args.desde)
    fin=date.fromisoformat(args.hasta)
    if fin>datetime.now(timezone.utc).date()+timedelta(days=1):
        raise ValueError('No se permiten ventanas históricas en el futuro')
    for a,b,dias in ventanas(inicio,fin,args.lote):
        print(f'USGS histórico {a} -> {b} (hasta exclusivo)',flush=True)
        ejecutar_usgs(dias, ahora=datetime.combine(b,time.min,tzinfo=timezone.utc))

if __name__=='__main__':
    main()
