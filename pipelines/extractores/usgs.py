"""Extractor USGS FDSNWS GeoJSON (una ventana temporal y un bbox)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
REINTENTABLES = {429, 500, 502, 503, 504}


class ErrorExtraccion(Exception):
    def __init__(self, mensaje: str, intentos: int, codigo_http: int | None = None):
        super().__init__(mensaje)
        self.intentos = intentos
        self.codigo_http = codigo_http


@dataclass(frozen=True)
class RespuestaUSGS:
    original: bytes
    registros_recibidos: int
    intentos: int
    codigo_http: int


def parametros_usgs(dias: int, ahora: datetime | None = None) -> dict[str, Any]:
    if not 1 <= dias <= 30:
        raise ValueError("--dias debe estar entre 1 y 30")
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    desde = ahora - timedelta(days=dias)
    # API USGS interpreta las horas ISO sin desplazamiento como UTC.
    iso_utc = lambda fecha: fecha.strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "format": "geojson", "starttime": iso_utc(desde), "endtime": iso_utc(ahora),
        "minlatitude": -24.0, "maxlatitude": -9.0,
        "minlongitude": -70.0, "maxlongitude": -57.0,
        "orderby": "time-asc", "limit": 20000,
    }


def descargar_usgs(
    cliente: httpx.Client, parametros: dict[str, Any],
    max_intentos: int = 3, esperar=time.sleep,
) -> RespuestaUSGS:
    """Reintenta solamente fallos transitorios. No altera los bytes descargados."""
    if max_intentos < 1:
        raise ValueError("max_intentos debe ser positivo")
    for numero in range(1, max_intentos + 1):
        try:
            respuesta = cliente.get(USGS_URL, params=parametros)
            if respuesta.status_code in REINTENTABLES:
                if numero < max_intentos:
                    esperar(min(2 ** (numero - 1), 4))
                    continue
                raise ErrorExtraccion(
                    f"USGS devolvió HTTP {respuesta.status_code}", numero, respuesta.status_code
                )
            if respuesta.status_code != 200:
                raise ErrorExtraccion(
                    f"USGS devolvió HTTP {respuesta.status_code}", numero, respuesta.status_code
                )
            try:
                objeto = json.loads(respuesta.content)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ErrorExtraccion("USGS devolvió JSON inválido", numero, 200) from exc
            if (not isinstance(objeto, dict) or objeto.get("type") != "FeatureCollection"
                    or not isinstance(objeto.get("features"), list)):
                raise ErrorExtraccion("USGS cambió el esquema esperado de GeoJSON", numero, 200)
            cuenta = len(objeto["features"])
            total = objeto.get("metadata", {}).get("count")
            if isinstance(total, int) and total != cuenta:
                raise ErrorExtraccion("USGS entregó un lote incompleto", numero, 200)
            if cuenta >= int(parametros.get("limit", 20000)):
                raise ErrorExtraccion("Lote en límite de API: reducir --dias para evitar truncamiento", numero, 200)
            return RespuestaUSGS(respuesta.content, cuenta, numero, 200)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if numero >= max_intentos:
                raise ErrorExtraccion(f"Error temporal de red de USGS: {type(exc).__name__}", numero) from exc
            esperar(min(2 ** (numero - 1), 4))
    raise AssertionError("Extracción terminó sin resultado")
