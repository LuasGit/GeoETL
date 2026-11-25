"""Pruebas HTTP sin BD: contratos, autenticación de lectura y validaciones."""
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.dependencias import obtener_conexion


def test_health_v1():
    r=TestClient(app).get('/health')
    assert r.status_code == 200 and r.json()['version']=='1.0.0'


def test_solo_get_en_observaciones():
    r=TestClient(app).post('/api/v1/mapa/observaciones')
    assert r.status_code == 405


def test_bbox_invalido_es_422_no_500():
    # No permite que el test toque ninguna BD: inyección de dependencia.
    app.dependency_overrides[obtener_conexion]=lambda:object()
    try:
        r=TestClient(app).get('/api/v1/mapa/observaciones?bbox=imposible')
        assert r.status_code==422
    finally:
        app.dependency_overrides.clear()


def test_limite_geojson_es_422():
    app.dependency_overrides[obtener_conexion]=lambda:object()
    try:
        r=TestClient(app).get('/api/v1/mapa/observaciones?limit=9000')
        assert r.status_code==422
    finally:
        app.dependency_overrides.clear()


def test_openapi_publica_rutas_principales():
    rutas=TestClient(app).get('/openapi.json').json()['paths']
    assert '/api/v1/mapa/observaciones' in rutas
    assert '/api/v1/indicadores/resumen' in rutas
    assert '/api/v1/etl/ejecuciones' in rutas
    assert '/api/v1/calidad/resumen' in rutas
