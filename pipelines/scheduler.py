"""Planificador sencillo (reloj UTC). No expuesto por la API."""
import os
import time
from datetime import datetime, timezone

from pipelines.orquestador import ejecutar_pipeline


def minutos_config():
    n=int(os.getenv('SCHEDULER_INTERVAL_MINUTES','360'))
    if not (15 <= n <= 10080):
        raise ValueError('SCHEDULER_INTERVAL_MINUTES debe estar entre 15 y 10080')
    return n


def main():
    espera=minutos_config()*60
    al_inicio=os.getenv('SCHEDULER_RUN_ON_START','true').strip().lower()=='true'
    print('SCHEDULER ACTIVO | intervalo minutos=',espera//60,flush=True)
    while True:
        if al_inicio:
            try:
                errores=ejecutar_pipeline(dias_segunda=14)
                print('Scheduler resultado', 'OK' if not errores else str(errores),flush=True)
            except Exception as exc:
                # Sobrevivir fallos temporales sin detener la programación futura.
                print('Scheduler error',type(exc).__name__,flush=True)
        al_inicio=True
        time.sleep(espera)

if __name__=='__main__':
    main()
