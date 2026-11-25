import json
from pipelines.episodios import detectar
from pipelines.transformaciones.normalizar import normalizar_power
from pipelines.extractores.fuente_segunda import url_firms

def test_racha_y_huecos():
    d=[('2025-01-01',30),('2025-01-02',32),('2025-01-03',31),('2025-01-05',34),('2025-01-06',None),('2025-01-07',33)]
    assert detectar(d,30,3)==[{'desde':'2025-01-01','hasta':'2025-01-03','dias':3,'maxima':32,'exceso_grados_dia':3}]

def test_power_fill_value():
    obj={'geometry':{'coordinates':[-63,-17,400]},'header':{'fill_value':-999},'properties':{'parameter':{'T2M_MAX':{'20250101':35,'20250102':-999},'T2M_MIN':{'20250101':21,'20250102':-999},'PRECTOTCORR':{'20250101':0,'20250102':-999}}}}
    a,r,n=normalizar_power(json.dumps(obj).encode(),'santa_cruz')
    assert n==2 and len(a)==len(r)==1 and a[0].mediciones['TEMP_MAX_C']==(35,'°C')

def test_productos_firms():
    assert '/VIIRS_NOAA21_NRT/' in url_firms('fake',5,'VIIRS_NOAA21_NRT')

def test_contraste_compara_solo_fechas_validas():
    from pipelines.episodios import contrastar
    a={'ciudad':'santa_cruz','fuente':'OPEN_METEO','serie':[{'fecha':'2025-01-01','maxima':35},{'fecha':'2025-01-02','maxima':None}], 'episodios':[{'desde':'2025-01-01','hasta':'2025-01-03'}]}
    b={'ciudad':'santa_cruz','fuente':'NASA_POWER','serie':[{'fecha':'2025-01-01','maxima':33},{'fecha':'2025-01-02','maxima':34}], 'episodios':[]}
    assert contrastar([a,b])==[{'ciudad':'santa_cruz','dias_comparables':1,'diferencia_media_absoluta':2.0,'dias_en_episodio_ambos':0,'dias_en_episodio_solo_uno':1}]
