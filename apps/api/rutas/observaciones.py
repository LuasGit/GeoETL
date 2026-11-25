"""Consultas canónicas Core y mapa GeoJSON. Sin SQL dinámico interpolado."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from apps.api.dependencias import obtener_conexion
from apps.api.validacion import bbox_validado, rango_fechas

router = APIRouter(prefix='/api/v1', tags=['observaciones'])

DETALLE_SQL = """
SELECT o.id_observacion::text, f.codigo, t.codigo, o.clave_origen,
       o.fecha_evento,o.fecha_observacion,o.titulo,
       ST_X(o.geometria), ST_Y(o.geometria), o.metadatos,
       (SELECT coalesce(jsonb_object_agg(m.codigo_metrica,
                  jsonb_build_object('valor',m.valor_numerico,'unidad',m.unidad)), '{}'::jsonb)
          FROM core.medicion_observacion m WHERE m.id_observacion=o.id_observacion),
       a.checksum_sha256,a.id_ejecucion::text
FROM core.observacion_ambiental o
JOIN ops.fuente_datos f ON f.id_fuente=o.id_fuente
JOIN core.tipo_fenomeno t ON t.id_tipo_fenomeno=o.id_tipo_fenomeno
JOIN ops.archivo_crudo a ON a.id_archivo=o.id_archivo_origen
"""


def convertir(fila):
    return dict(zip(('id','fuente','fenomeno','clave_origen','fecha_evento',
                     'fecha_observacion','titulo','longitud','latitud','metadatos',
                     'mediciones','checksum_bronze','id_ejecucion'),fila))


@router.get('/observaciones')
def listar_observaciones(
    fuente: str | None = Query(default=None, max_length=30),
    fenomeno: str | None = Query(default=None, max_length=30),
    desde: date | None = None, hasta: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
    db: Connection = Depends(obtener_conexion),
):
    rango_fechas(desde, hasta)
    condicion = """ WHERE (%s::text IS NULL OR f.codigo=%s)
             AND (%s::text IS NULL OR t.codigo=%s)
             AND (%s::date IS NULL OR (o.fecha_evento AT TIME ZONE 'UTC')::date >= %s)
             AND (%s::date IS NULL OR (o.fecha_evento AT TIME ZONE 'UTC')::date <= %s)"""
    filtros = (fuente,fuente,fenomeno,fenomeno,desde,desde,hasta,hasta)
    # La consulta detalle tiene checksum, geometría, mediciones; limitar resultados.
    filas = db.execute(DETALLE_SQL + condicion + ' ORDER BY o.fecha_evento DESC, o.id_observacion LIMIT %s OFFSET %s',
                       (*filtros,limit,offset)).fetchall()
    total = db.execute("""SELECT count(*) FROM core.observacion_ambiental o
       JOIN ops.fuente_datos f ON f.id_fuente=o.id_fuente
       JOIN core.tipo_fenomeno t ON t.id_tipo_fenomeno=o.id_tipo_fenomeno""" + condicion, filtros).fetchone()[0]
    return {'items':[convertir(x) for x in filas], 'total':total,'limit':limit,'offset':offset}


@router.get('/observaciones/{id_observacion}')
def detalle_observacion(id_observacion: UUID, db: Connection = Depends(obtener_conexion)):
    fila = db.execute(DETALLE_SQL + ' WHERE o.id_observacion=%s', (id_observacion,)).fetchone()
    if fila is None:
        raise HTTPException(404, 'Observación no encontrada')
    return convertir(fila)


@router.get('/mapa/observaciones')
def mapa_observaciones(
    bbox: str = Query(default='-70,-24,-57,-9'),
    desde: date | None = None, hasta: date | None = None,
    fenomeno: str | None = Query(default=None, max_length=30),
    fuente: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Connection = Depends(obtener_conexion),
):
    oeste,sur,este,norte = bbox_validado(bbox)
    rango_fechas(desde,hasta)
    filas = db.execute("""
       SELECT o.id_observacion::text,f.codigo,t.codigo,o.fecha_evento,o.titulo,
              ST_X(o.geometria),ST_Y(o.geometria),
              (SELECT coalesce(jsonb_object_agg(m.codigo_metrica,
                       jsonb_build_object('valor',m.valor_numerico,'unidad',m.unidad)),'{}'::jsonb)
                 FROM core.medicion_observacion m WHERE m.id_observacion=o.id_observacion)
       FROM core.observacion_ambiental o
       JOIN ops.fuente_datos f ON f.id_fuente=o.id_fuente
       JOIN core.tipo_fenomeno t ON t.id_tipo_fenomeno=o.id_tipo_fenomeno
       WHERE ST_Intersects(o.geometria,ST_MakeEnvelope(%s,%s,%s,%s,4326))
       AND (%s::text IS NULL OR t.codigo=%s)
       AND (%s::text IS NULL OR f.codigo=%s)
       AND (%s::date IS NULL OR (o.fecha_evento AT TIME ZONE 'UTC')::date >= %s)
       AND (%s::date IS NULL OR (o.fecha_evento AT TIME ZONE 'UTC')::date <= %s)
       ORDER BY o.fecha_evento DESC, o.id_observacion LIMIT %s
    """,(oeste,sur,este,norte,fenomeno,fenomeno,fuente,fuente,desde,desde,hasta,hasta,limit+1)).fetchall()
    truncado = len(filas)>limit
    features = []
    for id_,fuente_,tipo,fecha,titulo,lon,lat,medidas in filas[:limit]:
        features.append({'type':'Feature','id':id_,
                         'geometry':{'type':'Point','coordinates':[lon,lat]},
                         'properties':{'fuente':fuente_,'fenomeno':tipo,
                                       'fecha_evento':fecha.isoformat(),'titulo':titulo,
                                       'mediciones':medidas}})
    return {'type':'FeatureCollection','features':features,'properties':{'truncado':truncado,'limite':limit}}
