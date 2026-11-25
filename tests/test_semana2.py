"""Fixtures: cero llamadas HTTP reales. El usuario verifica APIs reales ejecutando CLI."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from pipelines.extractores.fuente_segunda import parametros_openmeteo, url_firms
from pipelines.transformaciones.normalizar import (
    LoteInvalido, deduplicar_lote, normalizar_firms, normalizar_openmeteo,
    normalizar_usgs,
)

AHORA = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def _usgs(mag=4.0, lon=-68.0, lat=-16.0, clave="us-001"):
    return {"type": "Feature", "id": clave,
            "properties": {"mag": mag, "time": 1792800000000, "place": "Bolivia"},
            "geometry": {"type": "Point", "coordinates": [lon, lat, 20.0]}}


def _datos_usgs(*features):
    return json.dumps({"type": "FeatureCollection", "features": list(features)}).encode()


def test_usgs_normalizacion_utc_y_medidas():
    validos, malos, total = normalizar_usgs(_datos_usgs(_usgs()), AHORA)
    assert total == 1 and not malos and len(validos) == 1
    assert validos[0].longitud == -68.0
    assert validos[0].latitud == -16.0
    assert validos[0].fecha_evento.endswith("+00:00")
    assert validos[0].mediciones["MAGNITUD"] == (4.0, "escala_no_indicada")


def test_usgs_coordenada_fuera_rango_rechazada():
    validos, malos, total = normalizar_usgs(_datos_usgs(_usgs(lon=300)), AHORA)
    assert total == 1 and len(malos) == 1 and not validos
    assert "coordenada_fuera_rango" in malos[0].detalle


def test_usgs_idempotencia_en_lote_y_cambio_semantico():
    items, _, _ = normalizar_usgs(_datos_usgs(_usgs(), _usgs()), AHORA)
    finales, repetidos = deduplicar_lote(items)
    assert len(finales) == 1 and repetidos == 1
    cambiados, _, _ = normalizar_usgs(_datos_usgs(_usgs(mag=4.4)), AHORA)
    assert finales[0].huella != cambiados[0].huella


def test_usgs_lote_incompatible_falla_no_se_confunde_con_vacio():
    with pytest.raises(LoteInvalido):
        normalizar_usgs(b'{"error":"formato modificado"}', AHORA)


def test_firms_csv_y_clave_determinista():
    contenido = ("latitude,longitude,acq_date,acq_time,satellite,instrument,frp,confidence\n"
                 "-16.5,-68.2,2026-10-20,1230,N,VIIRS,12.5,n\n").encode()
    a, e, n = normalizar_firms(contenido, AHORA)
    b, _, _ = normalizar_firms(contenido, AHORA)
    assert n == 1 and len(a) == 1 and not e
    assert a[0].clave == b[0].clave
    assert a[0].fenomeno == "PUNTO_CALOR"
    assert a[0].mediciones["FRP_MW"][0] == 12.5


def test_firms_registro_invalido_no_detiene_lote():
    data = ("latitude,longitude,acq_date,acq_time,satellite,instrument,frp\n"
            "-16.5,-68.2,2026-10-20,1230,N,VIIRS,10\n"
            "-150,-68.2,2026-10-20,1230,N,VIIRS,10\n").encode()
    buenos, malos, total = normalizar_firms(data, AHORA)
    assert total == 2 and len(buenos) == 1 and len(malos) == 1


def test_firms_no_acepta_csv_sin_encabezado():
    with pytest.raises(LoteInvalido):
        normalizar_firms(b"No data available", AHORA)


def _mete_json():
    return json.dumps({
        "latitude": -16.5, "longitude": -68.125, "utc_offset_seconds": 0,
        "hourly": {"time": ["2026-10-20T00:00", "2026-10-20T01:00"],
                   "temperature_2m": [10.0, None], "precipitation": [0.0, 1.0],
                   "wind_speed_10m": [8.0, 9.0]}
    }).encode()


def test_openmeteo_un_dato_por_hora_no_por_archivo():
    buenos, malos, total = normalizar_openmeteo(_mete_json(), "la_paz", AHORA)
    assert total == 2 and len(buenos) == 2 and not malos
    assert buenos[0].clave != buenos[1].clave
    assert buenos[0].fenomeno == "METEO_MODELO"
    assert "TEMP_C" not in buenos[1].mediciones
    assert "PRECIP_MM" in buenos[1].mediciones


def test_openmeteo_series_incompletas_no_se_aceptan():
    obj = json.loads(_mete_json())
    obj["hourly"]["wind_speed_10m"] = [8.0]
    with pytest.raises(LoteInvalido):
        normalizar_openmeteo(json.dumps(obj).encode(), "la_paz", AHORA)


def test_firms_url_y_parametros_openmeteo():
    url = url_firms("llave-ficticia", 2)
    assert url.endswith("/-70,-24,-57,-9/2")
    p = parametros_openmeteo(3, 10, "la_paz", datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert p["start_date"] == "2026-10-13"
    assert p["end_date"] == "2026-10-15"
    assert p["timezone"] == "UTC"


def test_parquet_duckdb_roundtrip(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    from pipelines.transformaciones.parquet import crear_parquet, publicar_parquet
    r, _, _ = normalizar_usgs(_datos_usgs(_usgs()), AHORA)
    destino = tmp_path / "silver.parquet"
    temporal = crear_parquet(r, destino)
    assert temporal.is_file()
    publicar_parquet(temporal, destino)
    db = duckdb.connect(":memory:")
    try:
        filas = db.execute("SELECT clave_origen,latitud,longitud FROM read_parquet(?)", [str(destino)]).fetchall()
    finally:
        db.close()
    assert filas == [("us-001", -16.0, -68.0)]
