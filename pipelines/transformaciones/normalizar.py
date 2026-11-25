"""Contratos de calidad Silver. Todo módulo se puede probar sin base de datos ni DuckDB."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import math


class LoteInvalido(ValueError):
    """La estructura completa de la fuente es incompatible; no procesar como cero datos."""


class RegistroInvalido(ValueError):
    """Una observación tiene campos obligatorios inválidos."""


@dataclass(frozen=True)
class Observacion:
    clave: str
    fenomeno: str
    fecha_evento: str           # ISO 8601 UTC
    fecha_observacion: str | None
    latitud: float
    longitud: float
    titulo: str
    metadata: dict
    mediciones: dict[str, tuple[float, str]]
    huella: str                # cambio semántico (no incluye origen Bronze)


@dataclass(frozen=True)
class Rechazo:
    indice: int
    clave: str | None
    regla: str
    detalle: str


def _numero(valor, etiqueta: str, requerido: bool = True) -> float | None:
    if valor is None or valor == "":
        if requerido:
            raise RegistroInvalido(f"{etiqueta}: nulo/no disponible")
        return None
    if isinstance(valor, bool):
        raise RegistroInvalido(f"{etiqueta}: tipo booleano inválido")
    try:
        n = float(valor)
    except (ValueError, TypeError):
        raise RegistroInvalido(f"{etiqueta}: no numérico") from None
    if not math.isfinite(n):
        raise RegistroInvalido(f"{etiqueta}: valor no finito")
    return n


def _coordenadas(lat, lon) -> tuple[float, float]:
    lt, ln = _numero(lat, "latitud"), _numero(lon, "longitud")
    if not (-90 <= lt <= 90 and -180 <= ln <= 180):
        raise RegistroInvalido("coordenada_fuera_rango")
    return round(lt, 6), round(ln, 6)


def _fecha(valor: str | int | float, ahora: datetime) -> str:
    try:
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            # USGS indica milisegundos desde epoch.
            dt = datetime.fromtimestamp(float(valor) / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                # Solo se permite ISO sin zona cuando la API declara UTC.
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        raise RegistroInvalido("fecha_invalida") from None
    if dt.year < 1900 or dt > ahora + timedelta(days=1):
        raise RegistroInvalido("fecha_fuera_de_rango")
    return dt.isoformat(timespec="seconds")


def _observacion(clave: str, fenomeno: str, fecha: str, observado: str | None,
                 lat: float, lon: float, titulo: str,
                 metadata: dict, medidas: dict[str, tuple[float, str]]) -> Observacion:
    if not isinstance(clave, str) or not clave.strip() or len(clave) > 180:
        raise RegistroInvalido("clave_origen_invalida")
    if not medidas and fenomeno == "METEO_MODELO":
        raise RegistroInvalido("sin_mediciones_meteorologicas")
    semantica = {
        "clave": clave, "fenomeno": fenomeno, "fecha_evento": fecha,
        "latitud": lat, "longitud": lon, "titulo": titulo,
        "mediciones": {k: [round(v, 6), u] for k, (v, u) in sorted(medidas.items())},
    }
    huella = hashlib.sha256(json.dumps(semantica, sort_keys=True,
                          ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return Observacion(clave, fenomeno, fecha, observado, lat, lon, titulo,
                       metadata, medidas, huella)


def _procesar_registros(registros, normalizador):
    aceptados: list[Observacion] = []
    rechazados: list[Rechazo] = []
    for indice, dato in enumerate(registros, start=1):
        try:
            aceptados.append(normalizador(dato))
        except (RegistroInvalido, KeyError, IndexError, AttributeError, TypeError) as exc:
            clave = dato.get("id") if isinstance(dato, dict) else None
            mensaje = str(exc)[:250]
            regla = mensaje.split(":", 1)[0]
            reglas_canonicas = {
                "coordenada_fuera_rango", "fecha_invalida", "fecha_fuera_de_rango",
                "geometria_point_invalida", "magnitud_fuera_rango", "profundidad_fuera_rango",
                "clave_origen_invalida", "sin_mediciones_meteorologicas",
                "hora_adquisicion_invalida", "satelite_no_disponible",
            }
            if regla not in reglas_canonicas:
                regla = "validacion_registro"
            rechazados.append(Rechazo(indice, str(clave) if clave else None,
                                       regla, mensaje))
    return aceptados, rechazados


def _json(data: bytes):
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise LoteInvalido("El archivo Bronze no contiene JSON válido") from exc


def normalizar_usgs(datos: bytes, ahora: datetime | None = None):
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    objeto = _json(datos)
    if not isinstance(objeto, dict) or objeto.get("type") != "FeatureCollection" or not isinstance(objeto.get("features"), list):
        raise LoteInvalido("USGS: FeatureCollection/features no disponibles")

    def uno(f):
        if not isinstance(f, dict):
            raise RegistroInvalido("USGS: feature no es objeto")
        p = f.get("properties") or {}
        geo = f.get("geometry") or {}
        coords = geo.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2 or geo.get("type") != "Point":
            raise RegistroInvalido("geometria_point_invalida")
        lat, lon = _coordenadas(coords[1], coords[0])
        fecha = _fecha(p.get("time"), ahora)
        observado = _fecha(p["updated"], ahora) if p.get("updated") else None
        medidas = {}
        mag = _numero(p.get("mag"), "magnitud", requerido=False)
        if mag is not None:
            if not -3 <= mag <= 11:
                raise RegistroInvalido("magnitud_fuera_rango")
            medidas["MAGNITUD"] = (mag, str(p.get("magType") or "escala_no_indicada")[:30])
        if len(coords) > 2:
            depth = _numero(coords[2], "profundidad", requerido=False)
            if depth is not None:
                if not -20 <= depth <= 800:
                    raise RegistroInvalido("profundidad_fuera_rango")
                medidas["PROFUNDIDAD_KM"] = (depth, "km")
        clave = f.get("id")
        return _observacion(clave, "SISMO", fecha, observado, lat, lon,
                            str(p.get("place") or "Sismo USGS")[:180],
                            {"origen": "USGS", "tipo_magnitud": p.get("magType")}, medidas)

    aceptados, rechazados = _procesar_registros(objeto["features"], uno)
    return aceptados, rechazados, len(objeto["features"])


def normalizar_firms(datos: bytes, ahora: datetime | None = None):
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LoteInvalido("FIRMS: CSV no codificado en UTF-8") from exc
    lector = csv.DictReader(io.StringIO(texto))
    requeridas = {"latitude", "longitude", "acq_date", "acq_time", "satellite"}
    if not lector.fieldnames or not requeridas.issubset(set(lector.fieldnames)):
        raise LoteInvalido("FIRMS: encabezado CSV incompleto o sin datos tabulares")
    filas = list(lector)

    def uno(f):
        lat, lon = _coordenadas(f.get("latitude"), f.get("longitude"))
        hora_cruda = str(f.get("acq_time") or "").strip()
        if not hora_cruda:
            raise RegistroInvalido("hora_adquisicion_invalida")
        hora = hora_cruda.zfill(4)
        if len(hora) != 4 or not hora.isdigit() or int(hora[:2]) > 23 or int(hora[2:]) > 59:
            raise RegistroInvalido("hora_adquisicion_invalida")
        dt = f"{f.get('acq_date')}T{hora[:2]}:{hora[2:]}:00+00:00"
        fecha = _fecha(dt, ahora)
        sensor = str(f.get("satellite") or "").strip()
        instrumento = str(f.get("instrument") or "").strip()
        if not sensor:
            raise RegistroInvalido("satelite_no_disponible")
        clave_compuesta = f"{sensor}|{instrumento}|{fecha}|{lat:.6f}|{lon:.6f}"
        clave = "FIRMS-" + hashlib.sha256(clave_compuesta.encode()).hexdigest()[:40]
        medidas = {}
        for campo, codigo, unidad in (
            ("frp", "FRP_MW", "MW"),
            ("bright_ti4", "BRILLO_K", "K"),
            ("brightness", "BRILLO_K", "K"),
        ):
            valor = _numero(f.get(campo), campo, requerido=False)
            if valor is not None:
                medidas[codigo] = (valor, unidad)
        return _observacion(clave, "PUNTO_CALOR", fecha, fecha, lat, lon,
                            f"Detección térmica {sensor}",
                            {"satelite": sensor, "instrumento": instrumento,
                             "confianza": f.get("confidence"), "naturaleza": "deteccion_termica_no_incendio_confirmado"},
                            medidas)

    aceptados, rechazados = _procesar_registros(filas, uno)
    return aceptados, rechazados, len(filas)


def normalizar_openmeteo(datos: bytes, ciudad: str,
                         ahora: datetime | None = None):
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    objeto = _json(datos)
    if not isinstance(objeto, dict) or not isinstance(objeto.get("hourly"), dict):
        raise LoteInvalido("Open-Meteo: objeto hourly no disponible")
    if objeto.get("utc_offset_seconds") not in (0, None):
        raise LoteInvalido("Open-Meteo: zona temporal distinta de UTC")
    h = objeto["hourly"]
    tiempos = h.get("time")
    if not isinstance(tiempos, list):
        raise LoteInvalido("Open-Meteo: hourly.time debe ser un arreglo")
    metricas = ("temperature_2m", "precipitation", "wind_speed_10m")
    for campo in metricas:
        if not isinstance(h.get(campo), list) or len(h[campo]) != len(tiempos):
            raise LoteInvalido(f"Open-Meteo: serie {campo} incompleta")
    lat = objeto.get("latitude")
    lon = objeto.get("longitude")
    filas = [{"tiempo": t, "posicion": i} for i, t in enumerate(tiempos)]

    def uno(f):
        lt, ln = _coordenadas(lat, lon)
        fecha = _fecha(f["tiempo"], ahora)
        pos = f["posicion"]
        medidas = {}
        for campo, codigo, unidad in (
            ("temperature_2m", "TEMP_C", "°C"),
            ("precipitation", "PRECIP_MM", "mm"),
            ("wind_speed_10m", "VIENTO_KMH", "km/h"),
        ):
            numero = _numero(h[campo][pos], campo, requerido=False)
            if numero is not None:
                medidas[codigo] = (numero, unidad)
        clave = f"OM-{ciudad}-{fecha}"
        return _observacion(clave, "METEO_MODELO", fecha, fecha, lt, ln,
                            f"Condiciones meteorológicas modeladas: {ciudad}",
                            {"punto": ciudad, "origen": "Open-Meteo reanalisis", "naturaleza": "dato_modelado"},
                            medidas)
    aceptados, rechazados = _procesar_registros(filas, uno)
    return aceptados, rechazados, len(filas)


def normalizar_power(datos: bytes, ciudad: str, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    obj = _json(datos)
    try:
        series = obj['properties']['parameter']
        lon, lat = obj['geometry']['coordinates'][:2]
        if not all(isinstance(series[k], dict) for k in ('T2M_MAX','T2M_MIN','PRECTOTCORR')):
            raise TypeError()
        fechas = sorted(set().union(*(series[k].keys() for k in ('T2M_MAX','T2M_MIN','PRECTOTCORR'))))
        faltante = obj.get('header', {}).get('fill_value', -999)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise LoteInvalido('NASA POWER: estructura diaria inválida') from None
    def uno(f):
        lt, ln = _coordenadas(lat, lon)
        try:
            dia = datetime.strptime(f['dia'], '%Y%m%d').date().isoformat()
        except ValueError:
            raise RegistroInvalido('fecha_invalida') from None
        fecha = _fecha(dia+'T00:00:00+00:00', ahora)
        medidas = {}
        for k, codigo, unidad in [('T2M_MAX','TEMP_MAX_C','°C'),('T2M_MIN','TEMP_MIN_C','°C'),('PRECTOTCORR','PRECIP_MM_DIA','mm/día')]:
            n = _numero(series[k].get(f['dia']), k, requerido=False)
            if n is not None and n != faltante and n != -999:
                medidas[codigo] = (n, unidad)
        if 'TEMP_MAX_C' not in medidas:
            raise RegistroInvalido('sin_mediciones_meteorologicas')
        if 'TEMP_MIN_C' in medidas and medidas['TEMP_MIN_C'][0] > medidas['TEMP_MAX_C'][0]:
            raise RegistroInvalido('temperaturas_inconsistentes')
        return _observacion(f'POWER-{ciudad}-{dia}', 'METEO_MODELO', fecha, None, lt, ln,
                            f'Meteorología diaria NASA POWER: {ciudad}',
                            {'punto':ciudad,'origen':'NASA POWER','naturaleza':'dato_modelado_diario'},medidas)
    a,r = _procesar_registros([{'dia':d} for d in fechas], uno)
    return a,r,len(fechas)


def normalizar(fuente: str, datos: bytes, parametros: dict | None = None):
    parametros = parametros or {}
    if fuente == "USGS":
        return normalizar_usgs(datos)
    if fuente == "FIRMS":
        return normalizar_firms(datos)
    if fuente == "OPEN_METEO":
        return normalizar_openmeteo(datos, parametros.get("ciudad", "la_paz"))
    if fuente == "NASA_POWER":
        return normalizar_power(datos, parametros.get("ciudad", "la_paz"))
    raise LoteInvalido("Fuente no soportada: " + fuente)


def deduplicar_lote(registros: list[Observacion]):
    """Una observación consolidada por clave; en una repetición, la última gana."""
    unicos: dict[str, Observacion] = {}
    repetidos = 0
    for r in registros:
        if r.clave in unicos:
            repetidos += 1
        unicos[r.clave] = r
    return list(unicos.values()), repetidos
