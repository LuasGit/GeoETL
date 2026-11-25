from datetime import datetime,timezone
from uuid import uuid4
import json
import pytest
from pytest_bdd import scenarios, given, when, then
from pipelines.comun.almacenamiento import guardar_bronze,verificar_bronze
from pipelines.transformaciones.normalizar import normalizar_usgs,deduplicar_lote

scenarios('ingesta.feature')


def feature(id_,lon=-68):
    return {'type':'Feature','id':id_,
            'properties':{'mag':4.3,'time':1792800000000,'place':'Bolivia'},
            'geometry':{'type':'Point','coordinates':[lon,-16,15]}}


@pytest.fixture
def contexto(tmp_path):return {'dir':tmp_path}


@given('un lote USGS de prueba con una observación válida y otra inválida')
def lote_invalido(contexto):
    contexto['bytes']=json.dumps({'type':'FeatureCollection','features':[feature('s-1'),feature('s-2',360)]}).encode()


@given('un lote USGS de prueba con dos observaciones repetidas')
def lote_duplicado(contexto):
    contexto['bytes']=json.dumps({'type':'FeatureCollection','features':[feature('s-1'),feature('s-1')]}).encode()


@when('almaceno Bronze y genero el dataset Silver')
def guardar_y_transformar(contexto):
    from pipelines.transformaciones.parquet import crear_parquet,publicar_parquet
    contexto['bronze']=guardar_bronze(contexto['bytes'],contexto['dir'],'usgs',uuid4())
    buenos,malos,_=normalizar_usgs(contexto['bytes'],datetime(2026,10,25,tzinfo=timezone.utc))
    contexto['buenos']=buenos; contexto['malos']=malos
    destino=contexto['dir']/'silver.parquet'
    publicar_parquet(crear_parquet(buenos,destino),destino)
    contexto['silver']=destino


@when('normalizo y deduplico las observaciones')
def deduplicar(contexto):
    buenos,malos,total=normalizar_usgs(contexto['bytes'],datetime(2026,10,25,tzinfo=timezone.utc))
    contexto['buenos'],contexto['duplicados']=deduplicar_lote(buenos)


@then('el archivo Bronze conserva exactamente los bytes originales')
def bytes_identicos(contexto):
    assert verificar_bronze(contexto['bronze'])
    assert contexto['bronze'].ruta_absoluta.read_bytes()==contexto['bytes']


@then('Silver contiene una observación válida')
def silver_valido(contexto):
    import duckdb
    with duckdb.connect(':memory:') as con:
        assert con.execute('SELECT count(*) FROM read_parquet(?)',[str(contexto['silver'])]).fetchone()[0]==1


@then('se registra un rechazo por coordenada fuera de rango')
def rechazo_validado(contexto):
    assert len(contexto['malos'])==1
    assert contexto['malos'][0].regla=='coordenada_fuera_rango'


@then('solo queda una identidad de origen')
def identidad_unica(contexto):
    assert len(contexto['buenos'])==1 and contexto['duplicados']==1
