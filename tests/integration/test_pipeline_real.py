"""Pruebas reales contra geoetl_test (servicio testdb, NUNCA producción)."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
import json,os

import pytest

from pipelines.comun.bd import conectar
from pipelines.comun.almacenamiento import guardar_bronze
from pipelines.semana2 import procesar_ejecucion
from pipelines.cargas.gold import cargar_gold

pytestmark=pytest.mark.integration


def registro(clave, lon=-68.1, mag=4.2):
    tiempo=int((datetime.now(timezone.utc)-timedelta(days=2)).timestamp()*1000)
    return {'type':'Feature','id':clave,'properties':{'mag':mag,'time':tiempo,'place':'Bolivia'},
            'geometry':{'type':'Point','coordinates':[lon,-16.2,12]}}


@pytest.fixture(autouse=True)
def seguridad_y_limpieza():
    if os.environ.get('INTEGRATION_PG')!='1':
        pytest.skip('Para integración usar make test-integration (DB aislada)')
    with conectar() as con:
        nombre=con.execute('SELECT current_database()').fetchone()[0]
        assert nombre=='geoetl_test',f'PROHIBIDO borrar datos fuera de geoetl_test: {nombre}'
        con.execute("""TRUNCATE dw.hecho_observacion,dw.dim_fecha,dw.dim_fuente,dw.dim_fenomeno,
          core.medicion_observacion,core.observacion_ambiental,
          ops.registro_calidad,ops.archivo_crudo,ops.ejecucion_ingesta RESTART IDENTITY CASCADE""")
    yield


def preparar_lote(tmp_path,features,monkeypatch):
    payload=json.dumps({'type':'FeatureCollection','features':features,'metadata':{'count':len(features)}}).encode()
    monkeypatch.setenv('DATA_DIR',str(tmp_path))
    id_=uuid4()
    bronze=guardar_bronze(payload,tmp_path,'USGS',id_,'geojson')
    with conectar() as con:
        fuente=con.execute("SELECT id_fuente FROM ops.fuente_datos WHERE codigo='USGS'").fetchone()[0]
        con.execute("""INSERT INTO ops.ejecucion_ingesta
           (id_ejecucion,id_fuente,estado,fecha_fin,registros_recibidos,registros_pendientes)
           VALUES (%s,%s,'EXITO',now(),%s,%s)""",(id_,fuente,len(features),len(features)))
        con.execute("""INSERT INTO ops.archivo_crudo
           (id_ejecucion,ruta_archivo,checksum_sha256,formato,tamanio_bytes)
           VALUES (%s,%s,%s,'GEOJSON',%s)""",(id_,bronze.ruta_relativa,bronze.checksum_sha256,bronze.tamanio_bytes))
    return id_


def test_e2e_datos_idempotencia_gold_y_geojson(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from apps.api.main import app
    run=preparar_lote(tmp_path,[registro('eq1'),registro('eq1'),registro('eq-bad',lon=400)],monkeypatch)
    p=procesar_ejecucion(run)
    assert p=={'recibidos':3,'cargados':1,'duplicados':1,'rechazados':1}
    assert len(list((tmp_path/'silver').rglob('*.parquet')))==1
    with conectar() as con:
        assert con.execute('SELECT count(*) FROM core.observacion_ambiental').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM ops.registro_calidad').fetchone()[0]==1
    assert cargar_gold()['hechos']==1
    assert cargar_gold()['hechos']==1
    procesar_ejecucion(run)
    with conectar() as con:
        assert con.execute('SELECT count(*) FROM core.observacion_ambiental').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM core.medicion_observacion').fetchone()[0]==2
        assert con.execute('SELECT count(*) FROM dw.hecho_observacion').fetchone()[0]==1
    with TestClient(app) as cliente:
        geo=cliente.get('/api/v1/mapa/observaciones?bbox=-70,-24,-57,-9').json()
        assert geo['type']=='FeatureCollection'
        assert len(geo['features'])==1
        assert geo['features'][0]['geometry']['type']=='Point'
        assert cliente.get('/api/v1/indicadores/resumen').json()['total']==1
        assert cliente.get('/api/v1/calidad/resumen').json()['rechazados']==1
        assert cliente.get('/api/v1/observaciones').json()['total']==1
        assert cliente.get('/api/v1/fuentes/estado').status_code==200
        assert cliente.get('/api/v1/etl/ejecuciones').status_code==200


def test_gold_refleja_cambio_de_fecha_y_fuente_sin_duplicar(tmp_path,monkeypatch):
    run=preparar_lote(tmp_path,[registro('eq-update')],monkeypatch)
    procesar_ejecucion(run)
    cargar_gold()
    with conectar() as con:
        con.execute("""UPDATE core.observacion_ambiental
            SET fecha_evento=fecha_evento - interval '10 days' WHERE clave_origen='eq-update'""")
    assert cargar_gold()['hechos']==1
    with conectar() as con:
        fila=con.execute("""SELECT d.fecha,o.fecha_evento FROM dw.hecho_observacion h
           JOIN dw.dim_fecha d ON d.clave_fecha=h.clave_fecha
           JOIN core.observacion_ambiental o ON o.id_observacion=h.id_observacion_origen""").fetchone()
        assert fila[0]==fila[1].date()
        assert con.execute('SELECT count(*) FROM dw.hecho_observacion').fetchone()[0]==1


def test_usuario_api_no_puede_escribir():
    import psycopg
    from psycopg import errors
    with psycopg.connect(host=os.getenv('PGHOST','testdb'),port=5432,
                         dbname='geoetl_test',user='geoetl_reader',password='test_reader_only') as conn:
        assert conn.execute('SELECT count(*) FROM dw.hecho_observacion').fetchone()[0]>=0
        with pytest.raises(psycopg.Error):
            conn.execute("INSERT INTO core.tipo_fenomeno (codigo,nombre) VALUES ('NO_AUTORIZADO','X')")


def test_fallo_de_fuente_no_elimina_los_ultimos_datos_validos(tmp_path,monkeypatch):
    import httpx
    from pipelines.extractores.usgs import descargar_usgs, parametros_usgs, ErrorExtraccion
    run=preparar_lote(tmp_path,[registro('eq-conservado')],monkeypatch)
    procesar_ejecucion(run)
    cargar_gold()
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(503,request=req))) as cli:
        with pytest.raises(ErrorExtraccion):
            descargar_usgs(cli,parametros_usgs(1),max_intentos=2,esperar=lambda _:None)
    with conectar() as con:
        assert con.execute('SELECT count(*) FROM core.observacion_ambiental').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM dw.hecho_observacion').fetchone()[0]==1


@pytest.mark.performance
def test_consulta_espacial_con_mil_observaciones(tmp_path,monkeypatch):
    import time
    run=preparar_lote(tmp_path,[registro('perf-seed')],monkeypatch)
    procesar_ejecucion(run)
    with conectar() as con:
        con.execute("""INSERT INTO core.observacion_ambiental
          (id_fuente,id_tipo_fenomeno,id_archivo_origen,clave_origen,
           fecha_evento,geometria,titulo,metadatos)
          SELECT o.id_fuente,o.id_tipo_fenomeno,o.id_archivo_origen,
           'perf-'||g::text,o.fecha_evento,
           ST_SetSRID(ST_MakePoint(-69.1+(g%100)*0.02,-19.1+(g/100)*0.02),4326),
           'OBSERVACION SINTETICA DE PRUEBA','{}'::jsonb
          FROM core.observacion_ambiental o CROSS JOIN generate_series(1,1000) AS g
          WHERE o.clave_origen='perf-seed'""")
        t0=time.perf_counter()
        n=con.execute("""SELECT count(*) FROM core.observacion_ambiental
            WHERE ST_Intersects(geometria, ST_MakeEnvelope(-70,-24,-57,-9,4326))""").fetchone()[0]
        duracion=time.perf_counter()-t0
        assert n==1001
        # Umbral de desarrollo, no SLA de producción.
        assert duracion<10, f'Consulta tarda {duracion:.3f}s'
    assert cargar_gold()['hechos']==1001
