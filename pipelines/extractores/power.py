"""NASA POWER: máximas/mínimas diarias modeladas, no estaciones."""
from datetime import datetime, timezone, timedelta
from pipelines.extractores.fuente_segunda import PUNTOS

POWER_URL = 'https://power.larc.nasa.gov/api/temporal/daily/point'

def parametros_power(dias, atraso, ciudad):
    if not 1 <= dias <= 14 or not 7 <= atraso <= 90 or ciudad not in PUNTOS:
        raise ValueError('NASA POWER: ventana o ciudad no válida')
    fin = datetime.now(timezone.utc).date() - timedelta(days=max(atraso, 14))
    inicio = fin - timedelta(days=dias-1)
    lat, lon = PUNTOS[ciudad]
    return {'parameters':'T2M_MAX,T2M_MIN,PRECTOTCORR','community':'AG',
            'latitude':lat,'longitude':lon,'start':inicio.strftime('%Y%m%d'),
            'end':fin.strftime('%Y%m%d'),'format':'JSON','time-standard':'UTC'}
