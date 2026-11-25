"""API privada local de operación. Nunca se expone el rol escritor en la API pública."""
import os
import secrets
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Literal
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field
def ejecutar(*args, **kwargs):
    from pipelines.operaciones import ejecutar as ejecutar_real
    return ejecutar_real(*args, **kwargs)

app=FastAPI(title='GeoETL Operador', docs_url=None, redoc_url=None, openapi_url=None)
lock=Lock()
trabajo={'estado':'INACTIVO','pasos':[]}

def autorizar(x_operator_token: str = Header(default='')):
    token=os.getenv('OPERATOR_TOKEN','')
    if len(token)<24:
        raise HTTPException(503,'Configura OPERATOR_TOKEN (mínimo 24 caracteres) en .env y reinicia operador.')
    if not secrets.compare_digest(x_operator_token.encode(),token.encode()):
        raise HTTPException(401,'Token de operador incorrecto')

class Peticion(BaseModel):
    accion: Literal['extraer','limpiar','publicar','completo']
    fuentes: list[Literal['USGS','FIRMS','OPEN_METEO','NASA_POWER']]=Field(default=['USGS','OPEN_METEO','NASA_POWER'],min_length=1,max_length=4)
    dias: int=Field(default=14,ge=1,le=14)
    atraso: int=Field(default=10,ge=7,le=90)

def ahora(): return datetime.now(timezone.utc).isoformat()

def registrar(paso, estado):
    with lock:
        trabajo['pasos'].append({'paso':paso,'estado':estado,'hora':ahora()})

def correr(p):
    try:
        fallos=ejecutar(p.accion,list(dict.fromkeys(p.fuentes)),p.dias,p.atraso,registrar)
        estado='PARCIAL' if fallos and any(x['estado']=='EXITO' for x in trabajo['pasos']) else 'FALLIDO' if fallos else 'EXITO'
        error=', '.join(fallos)
    except Exception as exc:
        estado='FALLIDO'; error=str(exc) if str(exc)=='Otro pipeline está en curso' else type(exc).__name__
    with lock:
        trabajo.update(estado=estado, error=error, fin=ahora())

@app.get('/operador/estado',dependencies=[Depends(autorizar)])
def estado():
    with lock: return {**trabajo,'pasos':list(trabajo['pasos'])}

@app.post('/operador/ejecutar',status_code=202,dependencies=[Depends(autorizar)])
def iniciar(p: Peticion):
    with lock:
        if trabajo['estado']=='EJECUTANDO': raise HTTPException(409,'Ya hay una tarea activa')
        trabajo.clear(); trabajo.update(estado='EJECUTANDO',accion=p.accion,inicio=ahora(),pasos=[])
    Thread(target=correr,args=(p,),daemon=True).start()
    return {'estado':'EJECUTANDO'}
