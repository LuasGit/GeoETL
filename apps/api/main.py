"""GeoETL 1.0: API de SOLO LECTURA sobre Core, Gold y Ops."""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg import Error as PsycopgError
from pipelines.comun.bd import conectar

from apps.api.rutas.observaciones import router as observaciones
from apps.api.rutas.indicadores import router as indicadores
from apps.api.rutas.operacion import router as operacion

app=FastAPI(title='GeoETL API',version='1.0.0',description='Monitoreo ambiental informativo; no alertas oficiales.')
origines=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origines,allow_credentials=False,
                   allow_methods=['GET'],allow_headers=['Content-Type'])


@app.get('/health',tags=['sistema'])
def health():
    return {'estado':'ok','servicio':'geoetl-api','version':'1.0.0'}


@app.get('/ready',tags=['sistema'])
def ready():
    try:
        with conectar() as con:
            con.execute('SELECT 1')
    except (PsycopgError,RuntimeError):
        raise HTTPException(503,'Base de datos no disponible') from None
    return {'estado':'listo'}


app.include_router(observaciones)
app.include_router(indicadores)
app.include_router(operacion)

from apps.api.rutas.termico import router as termico
app.include_router(termico)
