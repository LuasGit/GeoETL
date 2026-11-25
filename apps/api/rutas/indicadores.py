"""Consultas Gold y métricas de calidad/ejecución desde ops."""
from datetime import date
from fastapi import APIRouter, Depends, Query
from psycopg import Connection
from apps.api.dependencias import obtener_conexion
from apps.api.validacion import rango_fechas

router = APIRouter(prefix='/api/v1', tags=['indicadores'])


@router.get('/indicadores/resumen')
def resumen(
    desde: date | None = None, hasta: date | None = None,
    fenomeno: str | None = Query(default=None,max_length=30),
    db: Connection = Depends(obtener_conexion),
):
    rango_fechas(desde,hasta)
    params=(desde,desde,hasta,hasta,fenomeno,fenomeno)
    sql=""" FROM dw.hecho_observacion h
      JOIN dw.dim_fecha d ON d.clave_fecha=h.clave_fecha
      JOIN dw.dim_fenomeno t ON t.clave_fenomeno=h.clave_fenomeno
      JOIN dw.dim_fuente f ON f.clave_fuente=h.clave_fuente
      WHERE (%s::date IS NULL OR d.fecha >= %s)
      AND (%s::date IS NULL OR d.fecha <= %s)
      AND (%s::text IS NULL OR t.codigo_fenomeno=%s)"""
    total = db.execute('SELECT coalesce(sum(h.cantidad_observaciones),0)::bigint'+sql, params).fetchone()[0]
    por_tipo = db.execute('SELECT t.codigo_fenomeno,coalesce(sum(h.cantidad_observaciones),0)::bigint'+sql+
                          ' GROUP BY t.codigo_fenomeno ORDER BY 2 DESC',params).fetchall()
    por_fuente = db.execute('SELECT f.codigo_fuente,coalesce(sum(h.cantidad_observaciones),0)::bigint'+sql+
                            ' GROUP BY f.codigo_fuente ORDER BY 2 DESC',params).fetchall()
    return {'origen':'gold','total':total,
            'por_fenomeno':[{'fenomeno':x,'cantidad':y} for x,y in por_tipo],
            'por_fuente':[{'fuente':x,'cantidad':y} for x,y in por_fuente]}


@router.get('/indicadores/serie')
def serie(
    desde: date | None = None, hasta: date | None = None,
    fenomeno: str | None = Query(default=None,max_length=30),
    limit: int = Query(default=365,ge=1,le=2000),
    db: Connection = Depends(obtener_conexion),
):
    rango_fechas(desde,hasta)
    filas=db.execute("""SELECT d.fecha,t.codigo_fenomeno, sum(h.cantidad_observaciones)::bigint AS total
        FROM dw.hecho_observacion h
        JOIN dw.dim_fecha d ON d.clave_fecha=h.clave_fecha
        JOIN dw.dim_fenomeno t ON t.clave_fenomeno=h.clave_fenomeno
        WHERE (%s::date IS NULL OR d.fecha >= %s)
          AND (%s::date IS NULL OR d.fecha <= %s)
          AND (%s::text IS NULL OR t.codigo_fenomeno=%s)
        GROUP BY d.fecha,t.codigo_fenomeno
        ORDER BY d.fecha DESC,t.codigo_fenomeno LIMIT %s""",
        (desde,desde,hasta,hasta,fenomeno,fenomeno,limit)).fetchall()
    return {'items':[{'fecha':f.isoformat(),'fenomeno':t,'cantidad':n} for f,t,n in reversed(filas)]}


@router.get('/calidad/resumen')
def calidad(db: Connection = Depends(obtener_conexion)):
    resumen = db.execute("""SELECT coalesce(sum(registros_recibidos),0)::bigint,
       coalesce(sum(registros_cargados),0)::bigint,
       coalesce(sum(registros_duplicados),0)::bigint,
       coalesce(sum(registros_rechazados),0)::bigint,
       coalesce(sum(registros_pendientes),0)::bigint
       FROM ops.ejecucion_ingesta""").fetchone()
    reglas = db.execute("""SELECT regla,count(*)::bigint FROM ops.registro_calidad
                    GROUP BY regla ORDER BY count(*) DESC LIMIT 20""").fetchall()
    return {'recibidos':resumen[0],'cargados':resumen[1],
            'duplicados':resumen[2],'rechazados':resumen[3],
            'pendientes':resumen[4],
            'por_regla':[{'regla':r,'cantidad':n} for r,n in reglas]}
