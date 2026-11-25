"""Contratos estructurales y parámetros que no requieren PostgreSQL."""
from datetime import datetime,timezone
import pytest
from apps.api.validacion import bbox_validado, rango_fechas
from fastapi import HTTPException
from pipelines.scheduler import minutos_config
from pipelines.cargas.gold import SQL_HECHOS


def test_bbox_bolivia():
    assert bbox_validado('-70,-24,-57,-9') == (-70.,-24.,-57.,-9.)


@pytest.mark.parametrize('input_', ['-70,-24,-71,-9', '12', 'NaN,-24,-60,-9', '-190,-10,0,2','-68,-100,-60,20'])
def test_bbox_invalido(input_):
    with pytest.raises(HTTPException) as err:
        bbox_validado(input_)
    assert err.value.status_code == 422


def test_rango_fechas_invertido():
    from datetime import date
    with pytest.raises(HTTPException):
        rango_fechas(date(2026,10,30),date(2026,10,1))


def test_gold_tiene_unicidad_y_upsert():
    assert 'ON CONFLICT (id_observacion_origen) DO UPDATE' in SQL_HECHOS
    assert 'dw.hecho_observacion' in SQL_HECHOS


def test_scheduler_intervalo(monkeypatch):
    monkeypatch.setenv('SCHEDULER_INTERVAL_MINUTES','15')
    assert minutos_config() == 15
    monkeypatch.setenv('SCHEDULER_INTERVAL_MINUTES','1')
    with pytest.raises(ValueError): minutos_config()
