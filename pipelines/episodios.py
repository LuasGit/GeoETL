"""Detección descriptiva de episodios: no pronóstico ni definición oficial."""
from datetime import date, timedelta


def detectar(dias, umbral=30., minimo=3):
    """dias: pares (fecha ISO, máxima completa o None). Huecos cortan rachas."""
    episodios=[]; racha=[]
    def cerrar():
        if len(racha)>=minimo:
            episodios.append({'desde':racha[0][0].isoformat(),'hasta':racha[-1][0].isoformat(),
                'dias':len(racha),'maxima':round(max(v for _,v in racha),2),
                'exceso_grados_dia':round(sum(v-umbral for _,v in racha),2)})
        racha.clear()
    for d,v in sorted(dias):
        d=date.fromisoformat(str(d))
        if v is None or v<umbral:
            cerrar(); continue
        if racha and d!=racha[-1][0]+timedelta(days=1): cerrar()
        racha.append((d,v))
    cerrar()
    return episodios


def contrastar(grupos):
    """Contrasta Tmax de dos productos para fechas UTC completas coincidentes."""
    por_ciudad={}
    for g in grupos:
        por_ciudad.setdefault(g['ciudad'],{})[g['fuente']]=g
    salida=[]
    for ciudad, fuentes in sorted(por_ciudad.items()):
        if not {'OPEN_METEO','NASA_POWER'}<=fuentes.keys(): continue
        a,b=(fuentes[x] for x in ('OPEN_METEO','NASA_POWER'))
        series=[{x['fecha']:x['maxima'] for x in g['serie'] if x['maxima'] is not None} for g in (a,b)]
        dias=series[0].keys() & series[1].keys()
        def dias_episodio(g):
            return {d for d in dias if any(e['desde']<=d<=e['hasta'] for e in g['episodios'])}
        da,db=dias_episodio(a),dias_episodio(b)
        salida.append({'ciudad':ciudad,'dias_comparables':len(dias),
            'diferencia_media_absoluta':round(sum(abs(series[0][d]-series[1][d]) for d in dias)/len(dias),2) if dias else None,
            'dias_en_episodio_ambos':len(da&db),'dias_en_episodio_solo_uno':len(da^db)})
    return salida
