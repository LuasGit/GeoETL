"""NASA FIRMS o contingencia Open-Meteo: extracción pura sin claves en logs.

La llamada HTTP devuelve bytes tal cual; la persistencia y auditoría viven en semana2.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

import httpx

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
FIRMS_PRODUCTO = "VIIRS_SNPP_NRT"
FIRMS_PRODUCTOS = (FIRMS_PRODUCTO, "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
BBOX_FIRMS = "-70,-24,-57,-9"  # oeste,sur,este,norte; Bolivia y alrededores
PUNTOS = {
    "la_paz": (-16.50, -68.15),
    "cochabamba": (-17.39, -66.16),
    "santa_cruz": (-17.78, -63.18),
}


class FalloFuente(Exception):
    def __init__(self, mensaje: str, intentos: int, estado_http: int | None = None):
        super().__init__(mensaje)
        self.intentos = intentos
        self.estado_http = estado_http


def parametros_openmeteo(dias: int = 3, atraso: int = 10, ciudad: str = "la_paz",
                         ahora: datetime | None = None):
    """Para estabilidad del archivo histórico se excluyen los días más recientes."""
    if not 1 <= dias <= 14 or not 7 <= atraso <= 90:
        raise ValueError("Open-Meteo exige 1..14 días y atraso histórico 7..90 días")
    if ciudad not in PUNTOS:
        raise ValueError("Ciudad no contemplada: " + ciudad)
    hoy = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    fin = hoy - timedelta(days=atraso)
    inicio = fin - timedelta(days=dias - 1)
    lat, lon = PUNTOS[ciudad]
    return {"latitude": lat, "longitude": lon,
            "start_date": inicio.isoformat(), "end_date": fin.isoformat(),
            "hourly": "temperature_2m,precipitation,wind_speed_10m",
            "timezone": "UTC"}


def url_firms(clave: str, dias: int = 2, producto: str = FIRMS_PRODUCTO) -> str:
    if not clave or not clave.strip():
        raise ValueError("FIRMS_MAP_KEY no configurada")
    if not 1 <= dias <= 5:
        raise ValueError("FIRMS permite una ventana 1..5 días")
    # La clave forma parte de la URL exigida por NASA; nunca se registra en SQL.
    if producto not in FIRMS_PRODUCTOS:
        raise ValueError("Producto FIRMS no permitido")
    return f"{FIRMS_URL}/{clave}/{producto}/{BBOX_FIRMS}/{dias}"


def descargar(url: str, parametros: dict | None = None,
              max_intentos: int = 3, esperar=time.sleep):
    """Devuelve bytes, código HTTP e intentos. Los errores no incluyen URL con secretos."""
    if max_intentos < 1:
        raise ValueError("max_intentos debe ser positivo")
    with httpx.Client(timeout=httpx.Timeout(50.0), follow_redirects=True) as cliente:
        for intento in range(1, max_intentos + 1):
            try:
                r = cliente.get(url, params=parametros)
                if r.status_code in (429, 500, 502, 503, 504):
                    if intento < max_intentos:
                        esperar(min(2 ** (intento - 1), 4))
                        continue
                    raise FalloFuente(f"Fuente respondió HTTP {r.status_code}", intento, r.status_code)
                if r.status_code != 200:
                    raise FalloFuente(f"Fuente respondió HTTP {r.status_code}", intento, r.status_code)
                return r.content, r.status_code, intento
            except (httpx.TimeoutException, httpx.NetworkError):
                if intento == max_intentos:
                    raise FalloFuente("Error temporal de red consultando fuente externa", intento)
                esperar(min(2 ** (intento - 1), 4))
    raise AssertionError("Descarga no finalizada")
