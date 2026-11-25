import json
from datetime import datetime, timezone

import httpx
import pytest
from pipelines.extractores.usgs import ErrorExtraccion, descargar_usgs, parametros_usgs


def test_parametros_bolivia_con_utc():
    fecha = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)
    p = parametros_usgs(7, fecha)
    assert p["starttime"] == "2026-10-12T14:00:00"
    assert p["endtime"] == "2026-10-19T14:00:00"
    assert p["minlongitude"] < p["maxlongitude"]
    with pytest.raises(ValueError):
        parametros_usgs(31)


def test_extrae_los_bytes_sin_modificarlos():
    original = b'{"type":"FeatureCollection","features":[{"type":"Feature","id":"abc"}],"metadata":{"count":1}}'
    cliente = httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, content=original, request=req)))
    with cliente:
        resultado = descargar_usgs(cliente, parametros_usgs(1), esperar=lambda _: None)
    assert resultado.original == original
    assert resultado.registros_recibidos == 1
    assert resultado.intentos == 1


def test_reintenta_http_503_y_luego_200():
    estados = iter([503, 200])
    def handler(req):
        estado = next(estados)
        return httpx.Response(estado, content=json.dumps({"type": "FeatureCollection", "features": []}).encode(), request=req)
    with httpx.Client(transport=httpx.MockTransport(handler)) as cliente:
        respuesta = descargar_usgs(cliente, parametros_usgs(1), esperar=lambda _: None)
    assert respuesta.intentos == 2


def test_no_reintenta_cambios_de_esquema():
    with httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"error": "formato desconocido"}, request=req))) as cliente:
        with pytest.raises(ErrorExtraccion, match="esquema") as error:
            descargar_usgs(cliente, parametros_usgs(1), esperar=lambda _: None)
    assert error.value.intentos == 1
