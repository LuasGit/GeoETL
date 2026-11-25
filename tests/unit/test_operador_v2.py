from fastapi.testclient import TestClient
from apps.api import operador

def test_token_requerido(monkeypatch):
    monkeypatch.setenv('OPERATOR_TOKEN','x'*32)
    c=TestClient(operador.app)
    assert c.get('/operador/estado').status_code==401
    assert c.get('/operador/estado',headers={'X-Operator-Token':'x'*32}).status_code==200
    assert c.post('/operador/ejecutar',headers={'X-Operator-Token':'x'*32},json={'accion':'borrar'}).status_code==422

def test_token_sin_configurar(monkeypatch):
    monkeypatch.delenv('OPERATOR_TOKEN',raising=False)
    assert TestClient(operador.app).get('/operador/estado').status_code==503

def test_ocupado(monkeypatch):
    monkeypatch.setenv('OPERATOR_TOKEN','x'*32)
    monkeypatch.setattr(operador,'trabajo',{'estado':'EJECUTANDO','pasos':[]})
    r=TestClient(operador.app).post('/operador/ejecutar',headers={'X-Operator-Token':'x'*32},json={'accion':'limpiar'})
    assert r.status_code==409
