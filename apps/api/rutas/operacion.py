"""Observabilidad de fuentes y ejecuciones; acceso GET exclusivamente."""
from datetime import datetime,timezone
from fastapi import APIRouter, Depends, Query
from psycopg import Connection
from apps.api.dependencias import obtener_conexion

router=APIRouter(prefix='/api/v1',tags=['operacion'])


@router.get('/etl/ejecuciones')
def ejecuciones(limit: int=Query(default=40,ge=1,le=100), db: Connection=Depends(obtener_conexion)):
    filas=db.execute("""SELECT e.id_ejecucion::text,f.codigo,e.fecha_inicio,e.fecha_fin,e.estado,
       e.registros_recibidos,e.registros_cargados,e.registros_duplicados,
       e.registros_rechazados,e.registros_pendientes,e.numero_intentos,e.mensaje_error
       FROM ops.ejecucion_ingesta e
       JOIN ops.fuente_datos f ON f.id_fuente=e.id_fuente
       ORDER BY e.fecha_inicio DESC LIMIT %s""",(limit,)).fetchall()
    claves=('id_ejecucion','fuente','inicio','fin','estado','recibidos','cargados','duplicados',
            'rechazados','pendientes','intentos','mensaje_error')
    return {'items':[dict(zip(claves,r)) for r in filas]}


@router.get('/fuentes/estado')
def fuentes(db: Connection=Depends(obtener_conexion)):
    filas=db.execute("""SELECT codigo,nombre,esta_activa,frecuencia_minutos,
        ejecuciones,ultima_ejecucion,ultima_extraccion_valida,
        recibidos_acumulados,rechazados_acumulados FROM ops.vw_estado_fuentes ORDER BY codigo""").fetchall()
    ahora=datetime.now(timezone.utc)
    resultado=[]
    claves=('codigo','nombre','activa','frecuencia_minutos','ejecuciones','ultima_ejecucion',
            'ultima_extraccion_valida','recibidos_acumulados','rechazados_acumulados')
    for fila in filas:
        item=dict(zip(claves,fila))
        ultimo=item['ultima_extraccion_valida']
        atraso=(ahora-ultimo).total_seconds()/60 if ultimo else None
        item['atraso_minutos']=round(atraso,1) if atraso is not None else None
        item['estado_frescura']=('SIN_DATOS' if ultimo is None else
             'DESACTIVADA' if not item['activa'] else
             'DESACTUALIZADA' if atraso>item['frecuencia_minutos']*2 else 'ACTUALIZADA')
        resultado.append(item)
    return {'items':resultado}
