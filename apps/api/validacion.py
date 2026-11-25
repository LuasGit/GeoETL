"""Validadores puros de filtros de consulta espacial y temporal."""
from datetime import date, datetime, time, timezone
import math

from fastapi import HTTPException


def bbox_validado(raw: str) -> tuple[float, float, float, float]:
    try:
        datos = [float(v.strip()) for v in raw.split(',')]
    except (ValueError, AttributeError):
        raise HTTPException(422, 'bbox debe tener oeste,sur,este,norte') from None
    if len(datos) != 4 or not all(math.isfinite(v) for v in datos):
        raise HTTPException(422, 'bbox necesita cuatro números finitos')
    oeste, sur, este, norte = datos
    if not (-180 <= oeste < este <= 180 and -90 <= sur < norte <= 90):
        raise HTTPException(422, 'bbox fuera de rango o invertido')
    return (oeste, sur, este, norte)


def rango_fechas(desde: date | None, hasta: date | None):
    if desde and hasta and desde > hasta:
        raise HTTPException(422, 'La fecha inicial no puede superar la final')
    return desde, hasta
