"""Analítica térmica sobre Core; separa productos horarios y diarios."""
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from apps.api.dependencias import obtener_conexion
from pipelines.episodios import detectar, contrastar

router=APIRouter(prefix='/api/v1',tags=['episodios térmicos'])

@router.get('/termico')
def termico(desde:date|None=None,hasta:date|None=None,umbral:float=Query(30,ge=-10,le=55),
            minimo:int=Query(3,ge=2,le=14),db=Depends(obtener_conexion)):
    hasta=hasta or datetime.now(timezone.utc).date()
    desde=desde or hasta-timedelta(days=59)
    if not 0<=(hasta-desde).days<=365:
        raise HTTPException(422,'El período debe contener entre 1 y 366 días')
    filas=db.execute('''SELECT f.codigo,o.metadatos->>'punto',
        (o.fecha_evento AT TIME ZONE 'UTC')::date AS dia,
        max(m.valor_numerico), count(DISTINCT date_trunc('hour',o.fecha_evento AT TIME ZONE 'UTC')),
        avg(ST_Y(o.geometria)),avg(ST_X(o.geometria))
        FROM core.observacion_ambiental o
        JOIN ops.fuente_datos f USING(id_fuente)
        JOIN core.medicion_observacion m USING(id_observacion)
        WHERE ((f.codigo='OPEN_METEO' AND m.codigo_metrica='TEMP_C') OR
               (f.codigo='NASA_POWER' AND m.codigo_metrica='TEMP_MAX_C'))
          AND o.metadatos->>'punto' IS NOT NULL
          AND o.fecha_evento >= %s::date::timestamp AT TIME ZONE 'UTC'
          AND o.fecha_evento < (%s::date+1)::timestamp AT TIME ZONE 'UTC'
        GROUP BY f.codigo,o.metadatos->>'punto',dia ORDER BY 1,2,3''',(desde,hasta)).fetchall()
    grupos={}
    for fuente,ciudad,dia,maxima,n,lat,lon in filas:
        g=grupos.setdefault((fuente,ciudad),{'fuente':fuente,'ciudad':ciudad,'latitud':float(lat),'longitud':float(lon),'serie':[]})
        completa=n==24 if fuente=='OPEN_METEO' else n==1
        g['serie'].append({'fecha':dia.isoformat(),'maxima':float(maxima) if completa else None,'muestras':n,'completa':completa})
    for g in grupos.values():
        g['episodios']=detectar([(x['fecha'],x['maxima']) for x in g['serie']],umbral,minimo)
        g['dias_validos']=sum(x['completa'] for x in g['serie'])
        g['dias_ventana']=(hasta-desde).days+1
    return {'desde':desde,'hasta':hasta,'umbral':umbral,'minimo':minimo,'zona':'UTC','items':list(grupos.values()),'contraste':contrastar(grupos.values())}
