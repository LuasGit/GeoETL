import React, {useCallback, useEffect, useMemo, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {MapContainer, TileLayer, CircleMarker, Popup, Tooltip, LayersControl, ScaleControl, useMap, useMapEvents} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './style.css'

const SECCIONES = [
  {id:'inicio',nombre:'Inicio',icono:'▦'},
  {id:'mapa',nombre:'Mapa SIG',icono:'◎'},
  {id:'analitica',nombre:'Analítica',icono:'▥'},
  {id:'etl',nombre:'Procesamiento ETL',icono:'⇄'},
  {id:'termico',nombre:'Radar térmico',icono:'◷'},
  {id:'fuentes',nombre:'Fuentes y calidad',icono:'◈'},
]
const palette={SISMO:'#3179ce',PUNTO_CALOR:'#ed7d43',METEO_MODELO:'#2c9b86'}
const fmt = n => typeof n === 'number' ? new Intl.NumberFormat('es-BO').format(n) : '—'
const fecha = n => n ? new Date(n).toLocaleString('es-BO',{dateStyle:'medium',timeStyle:'short'}) : 'Sin información'
const fechaCorta = n => n ? new Date(n).toLocaleDateString('es-BO') : '—'
const lim = (s,n=90)=>s?.length>n?s.slice(0,n)+'…':s||'—'

async function obtener(ruta){
  const r=await fetch(ruta)
  if(!r.ok){let descripcion='Error HTTP '+r.status;try{const j=await r.json();descripcion=typeof j.detail==='string'?j.detail:descripcion}catch{} throw new Error(descripcion)}
  return r.json()
}
function useDatos(rutas,clave){
  const [estado,setEstado]=useState({datos:null,error:'',cargando:true})
  useEffect(()=>{
    let vivo=true
    setEstado(p=>({...p,cargando:true,error:''}))
    Promise.all(rutas.map(obtener)).then(datos=>{if(vivo)setEstado({datos,error:'',cargando:false})})
      .catch(e=>{if(vivo)setEstado({datos:null,error:e.message,cargando:false})})
    return ()=>{vivo=false}
  },[clave])
  return estado
}
function Mensaje({estado}){
  if(estado.cargando)return <div className="mensaje">Consultando información procesada…</div>
  if(estado.error)return <div role="alert" className="mensaje error">No se pudo consultar la API: {estado.error}</div>
  return null
}
function Tarjeta({etiqueta,valor,nota}){
  return <article className="metric-card"><span>{etiqueta}</span><strong>{valor}</strong><small>{nota}</small></article>
}
function SinDatos({texto='Todavía no hay datos disponibles con estos filtros.'}){
  return <div className="sin-datos"><span aria-hidden="true">◌</span><p>{texto}</p></div>
}
function Insignia({valor}){
  const estilos={EXITO:'ok',PARCIAL:'aviso',FALLIDO:'fallo',EJECUTANDO:'neutro',ACTUALIZADA:'ok',DESACTUALIZADA:'aviso',SIN_DATOS:'neutro',DESACTIVADA:'neutro'}
  return <span className={'insignia '+(estilos[valor]||'neutro')}>{valor||'—'}</span>
}
function Barra({valor,total,color}){
  return <div className="barra" aria-hidden="true"><div style={{width:`${total ? Math.max(2,100*valor/total):0}%`,background:color}}/></div>
}
function Distribucion({filas,clave='fenomeno'}){
  if(!filas?.length)return <SinDatos/>
  const max=Math.max(...filas.map(x=>x.cantidad),1)
  return <div className="distribucion">{filas.map(x=><div className="distribucion-fila" key={x[clave]}>
    <div className="distribucion-info"><span>{x[clave]}</span><strong>{fmt(x.cantidad)}</strong></div>
    <Barra valor={x.cantidad} total={max} color={palette[x[clave]]||'#558ea5'}/>
  </div>)}</div>
}
function Inicio({refresco}){
  const e=useDatos(['/api/v1/indicadores/resumen','/api/v1/fuentes/estado','/api/v1/calidad/resumen'],refresco)
  const [res,fuentes,calidad]=e.datos||[]
  return <><Mensaje estado={e}/>{res&&<>
    <div className="metric-grid">
      <Tarjeta etiqueta="Observaciones Gold" valor={fmt(res.total)} nota="Consolidadas sin duplicados"/>
      <Tarjeta etiqueta="Fuentes configuradas" valor={fmt(fuentes.items.length)} nota="Proveedores y contingencias"/>
      <Tarjeta etiqueta="Registros rechazados" valor={fmt(calidad.rechazados)} nota="Controles de calidad"/>
      <Tarjeta etiqueta="Registros pendientes" valor={fmt(calidad.pendientes)} nota="Por procesar en Silver"/>
    </div>
    <div className="two-col">
      <section className="panel"><div className="panel-head"><h2>Observaciones por fenómeno</h2><span className="mini-label">Capa Gold</span></div><Distribucion filas={res.por_fenomeno}/></section>
      <section className="panel"><div className="panel-head"><h2>Estado de las fuentes</h2><span className="mini-label">Última extracción</span></div>
        {fuentes.items.map(f=><div key={f.codigo} className="source-line"><div><strong>{f.codigo}</strong><small>{fecha(f.ultima_extraccion_valida)}</small></div><Insignia valor={f.estado_frescura}/></div>)}
      </section>
    </div>
    <p className="nota">Los indicadores provienen del Data Warehouse. La actualización depende de las extracciones y del procesamiento Gold ejecutados en el servidor.</p>
  </>}</>
}
function Controles({valor,setValor,fuentes=[]}){
  return <div className="filtros">
    <label>Fenómeno<select aria-label="Filtrar fenómeno" value={valor.fenomeno} onChange={e=>setValor(p=>({...p,fenomeno:e.target.value}))}>
      <option value="">Todos</option><option value="SISMO">Sismos</option><option value="PUNTO_CALOR">Puntos de calor</option><option value="METEO_MODELO">Meteorología modelada</option>
    </select></label>
    <label>Desde<input aria-label="Fecha desde" type="date" value={valor.desde} onChange={e=>setValor(p=>({...p,desde:e.target.value}))}/></label>
    <label>Hasta<input aria-label="Fecha hasta" type="date" value={valor.hasta} onChange={e=>setValor(p=>({...p,hasta:e.target.value}))}/></label>
    <button className="limpiar" onClick={()=>setValor({fenomeno:'',desde:'',hasta:''})} type="button">Limpiar</button>
  </div>
}
function consultaFiltros(f){const p=new URLSearchParams();for(const k of ['fenomeno','desde','hasta'])if(f[k])p.set(k,f[k]);return p.toString()}
function bboxSeguro(map){const b=map.getBounds();return [Math.max(-180,b.getWest()),Math.max(-90,b.getSouth()),Math.min(180,b.getEast()),Math.min(90,b.getNorth())].join(',')}
function VigilarVista({setBbox}){
  const map=useMapEvents({moveend:()=>setBbox(bboxSeguro(map)),zoomend:()=>setBbox(bboxSeguro(map))})
  useEffect(()=>{setBbox(bboxSeguro(map))},[map])
  return null
}
function AjustarMapa({features}){
  const map=useMap();return <div className="map-fit leaflet-top leaflet-right"><button onClick={()=>{if(features.length)map.fitBounds(features.map(f=>[f.geometry.coordinates[1],f.geometry.coordinates[0]]),{padding:[30,30],maxZoom:11});else map.setView([-17,-65],6)}}>Ajustar vista</button></div>
}
function Mapa({refresco}){
  const [filtros,setFiltros]=useState({fenomeno:'',desde:'',hasta:''})
  const [fuente,setFuente]=useState('')
  const [bbox,setBbox]=useState('-70,-24,-57,-9')
  const consulta=useMemo(()=>'/api/v1/mapa/observaciones?'+new URLSearchParams({bbox,limit:'1200',...(fuente?{fuente}:{}),...Object.fromEntries(Object.entries(filtros).filter(([,v])=>v))}),[bbox,filtros,fuente])
  const e=useDatos([consulta],consulta+'|'+refresco)
  const coleccion=e.datos?.[0]
  const grupos=useMemo(()=>{const g=new Map();for(const f of coleccion?.features||[]){const k=[...f.geometry.coordinates,f.properties.fenomeno,f.properties.fuente].join('|');if(!g.has(k))g.set(k,[]);g.get(k).push(f)}return [...g.values()]},[coleccion])
  return <><Controles valor={filtros} setValor={setFiltros}/><div className="extra-filtros"><label>Fuente <select value={fuente} onChange={e=>setFuente(e.target.value)}><option value="">Todas</option>{['USGS','FIRMS','OPEN_METEO','NASA_POWER'].map(x=><option key={x}>{x}</option>)}</select></label><button onClick={()=>{const b=new Blob([JSON.stringify(coleccion,null,2)],{type:'application/geo+json'});const url=URL.createObjectURL(b);const a=document.createElement('a');a.href=url;a.download='geoetl.geojson';a.click();URL.revokeObjectURL(url)}} disabled={!coleccion}>Exportar GeoJSON</button></div><div className="map-stats">
    <strong>{fmt(coleccion?.features?.length)} observaciones visibles</strong>
    <span>{coleccion?.properties?.truncado?'Se alcanzó el límite: aumenta el zoom para consultar un área menor.':'Mapa centrado en Bolivia y su entorno'}</span>
  </div>
  <section className="map-panel"><div className="map-canvas" data-testid="geoetl-map">
    <MapContainer center={[-17,-65]} zoom={6} minZoom={3} maxZoom={13} scrollWheelZoom={true} maxBounds={[[-85,-179],[85,179]]} style={{height:'100%',width:'100%'}}>
      <LayersControl position="bottomright"><LayersControl.BaseLayer checked name="Calles"><TileLayer noWrap attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /></LayersControl.BaseLayer><LayersControl.BaseLayer name="Claro"><TileLayer noWrap attribution='&copy; OpenStreetMap contributors &copy; CARTO' url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"/></LayersControl.BaseLayer></LayersControl>
      <ScaleControl position="bottomleft" imperial={false}/><AjustarMapa features={coleccion?.features||[]}/>
      <VigilarVista setBbox={setBbox}/>
      {grupos.map(grupo=>{const f=grupo[0];return <CircleMarker key={f.id} center={[f.geometry.coordinates[1],f.geometry.coordinates[0]]}
        radius={grupo.length>1?Math.min(18,7+Math.log2(grupo.length)*2):6} pathOptions={{color:palette[f.properties.fenomeno]||'#6d7b8b',fillOpacity:.8,weight:1}}>
        <Tooltip>{grupo.length} observación(es) · {f.properties.fuente}</Tooltip><Popup><strong>{f.properties.titulo||f.properties.fenomeno}</strong><p>Fuente: {f.properties.fuente}</p>
          <p>{fecha(f.properties.fecha_evento)} · {grupo.length} registros en esta ubicación (último mostrado)</p>
          {Object.entries(f.properties.mediciones||{}).map(([k,m])=><div key={k}>{k}: {m.valor} {m.unidad}</div>)}
        </Popup>
      </CircleMarker>})}
    </MapContainer>
  </div><div className="map-aside"><h3>Leyenda</h3>{Object.entries(palette).map(([k,color])=><div key={k} className="legend-row"><i style={{background:color}}/>{k.replaceAll('_',' ')}</div>)}
    <div className="map-divider"/><strong>Acerca de los datos</strong><p>Las detecciones térmicas no equivalen necesariamente a incendios confirmados. GeoETL no emite alertas oficiales.</p>
    <Mensaje estado={e}/>{coleccion&&!coleccion.features.length&&<SinDatos texto="No existen observaciones en el área y período seleccionados. Amplía las fechas o ejecuta una extracción en Procesamiento ETL."/>}
  </div></section></>
}
function Analitica({refresco}){
  const [f,setF]=useState({fenomeno:'',desde:'',hasta:''})
  const q=consultaFiltros(f)
  const e=useDatos(['/api/v1/indicadores/resumen?'+q,'/api/v1/indicadores/serie?'+q],q+'|'+refresco)
  const [res,serie]=e.datos||[]
  const max=Math.max(1,...(serie?.items||[]).map(x=>x.cantidad))
  return <><Controles valor={f} setValor={setF}/><Mensaje estado={e}/>{res&&<>
    <div className="metric-grid"><Tarjeta etiqueta="Observaciones en período" valor={fmt(res.total)} nota="Desde Gold"/>
      <Tarjeta etiqueta="Fenómenos" valor={res.por_fenomeno.length} nota="Con registros"/>
      <Tarjeta etiqueta="Fuentes" valor={res.por_fuente.length} nota="Con registros"/>
    </div>
    <div className="two-col">
      <section className="panel"><h2>Distribución por fenómeno</h2><Distribucion filas={res.por_fenomeno}/></section>
      <section className="panel"><h2>Distribución por fuente</h2><Distribucion filas={res.por_fuente} clave="fuente"/></section>
    </div>
    <section className="panel"><h2>Serie temporal de observaciones</h2>
      {serie?.items?.length?<div className="serie-chart" role="img" aria-label="Gráfico de conteos diarios por fenómeno">
        {serie.items.slice(-50).map((x,i)=><div title={`${x.fecha} · ${x.fenomeno}: ${x.cantidad}`} className="bar-column" key={x.fecha+x.fenomeno+i}>
          <span style={{height:`${Math.max(4,100*x.cantidad/max)}%`,background:palette[x.fenomeno]||'#487da8'}}/>
        </div>)}
      </div>:<SinDatos/>}
      <p className="nota">Una barra representa un conteo por fecha y fenómeno. No se promedian magnitudes sísmicas y potencia radiativa.</p>
    </section>
  </>}</>
}
function Procesamiento({refresco,onActualizar,onMapa}){
  const e=useDatos(['/api/v1/etl/ejecuciones'],refresco)
  const items=e.datos?.[0]?.items||[]
  return <><Operador onActualizar={onActualizar} onMapa={onMapa}/><Mensaje estado={e}/><section className="panel"><div className="panel-head"><h2>Historial de ejecuciones</h2><span className="mini-label">Últimos 40 lotes</span></div>
    {items.length?<div className="table-scroll"><table><thead><tr>{['Fuente','Inicio','Estado','Recibidos','Cargados','Duplicados','Rechazados','Pendientes','Duración'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>
      {items.map(x=><tr key={x.id_ejecucion}><td><b>{x.fuente}</b><small className="uuid">{x.id_ejecucion.slice(0,8)}…</small></td>
        <td>{fecha(x.inicio)}</td><td><Insignia valor={x.estado}/></td><td>{fmt(x.recibidos)}</td><td>{fmt(x.cargados)}</td><td>{fmt(x.duplicados)}</td>
        <td>{fmt(x.rechazados)}</td><td>{fmt(x.pendientes)}</td><td>{x.fin?`${Math.max(0,(new Date(x.fin)-new Date(x.inicio))/1000).toFixed(1)} s`:'—'}</td></tr>)}
    </tbody></table></div>:!e.cargando&&!e.error?<SinDatos texto="Aún no se han ejecutado extracciones."></SinDatos>:null}
  </section><p className="nota">Las operaciones web requieren un token privado. Reprocesamiento individual y configuración del programador permanecen en CLI.</p></>
}
function Fuentes({refresco}){
  const e=useDatos(['/api/v1/fuentes/estado','/api/v1/calidad/resumen'],refresco)
  const [fuentes,calidad]=e.datos||[]
  return <><Mensaje estado={e}/>{fuentes&&<>
    <div className="source-grid">{fuentes.items.map(f=><article className="source-card" key={f.codigo}>
      <div className="panel-head"><h2>{f.nombre}</h2><Insignia valor={f.estado_frescura}/></div>
      <div className="source-meta">Código: <strong>{f.codigo}</strong></div>
      <div className="source-meta">Última extracción válida: <strong>{fecha(f.ultima_extraccion_valida)}</strong></div>
      <div className="source-meta">Ejecuciones: <strong>{fmt(f.ejecuciones)}</strong></div>
      <div className="source-meta">Recibidos acumulados: <strong>{fmt(f.recibidos_acumulados)}</strong></div>
      <div className="source-meta">Frecuencia objetivo: <strong>{f.frecuencia_minutos} min</strong></div>
    </article>)}</div>
    <div className="metric-grid"><Tarjeta etiqueta="Registros recibidos" valor={fmt(calidad.recibidos)} nota="Acumulados en ejecuciones"/>
      <Tarjeta etiqueta="Cargados" valor={fmt(calidad.cargados)} nota="Altas y actualizaciones por lote"/>
      <Tarjeta etiqueta="Duplicados" valor={fmt(calidad.duplicados)} nota="Detectados por el pipeline"/>
      <Tarjeta etiqueta="Rechazados" valor={fmt(calidad.rechazados)} nota="Reglas de validación"/></div>
    <section className="panel"><h2>Motivos principales de rechazo</h2><Distribucion filas={calidad.por_regla} clave="regla"/></section>
  </>}</>
}
function Operador({onActualizar,onMapa}){
  const [token,setToken]=useState(''),[fuentes,setFuentes]=useState(['USGS','OPEN_METEO','NASA_POWER']),[dias,setDias]=useState(14),[atraso,setAtraso]=useState(10),[trabajo,setTrabajo]=useState(null),[error,setError]=useState(''),[enviando,setEnviando]=useState(false)
  async function llamada(ruta,body){const r=await fetch('/operador/'+ruta,{method:body?'POST':'GET',headers:{'X-Operator-Token':token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const j=await r.json();if(!r.ok)throw new Error(typeof j.detail==='string'?j.detail:'Solicitud no válida');return j}
  async function consultar(){try{const j=await llamada('estado');setTrabajo(j);setError('');return j}catch(e){setError(e.message)}}
  useEffect(()=>{if(trabajo?.estado!=='EJECUTANDO')return;const id=setInterval(async()=>{const j=await consultar();if(j&&j.estado!=='EJECUTANDO')onActualizar()},1800);return()=>clearInterval(id)},[trabajo?.estado,token])
  async function iniciar(accion){setEnviando(true);setError('');try{await llamada('ejecutar',{accion,fuentes,dias:Number(dias),atraso:Number(atraso)});setTrabajo({estado:'EJECUTANDO',pasos:[]});const j=await consultar();if(j&&j.estado!=='EJECUTANDO')onActualizar()}catch(e){setError(e.message)}finally{setEnviando(false)}}
  const ocupado=enviando||trabajo?.estado==='EJECUTANDO',bloqueado=ocupado||!token||!fuentes.length||dias<1||dias>14||atraso<7||atraso>90
  return <section className="panel operator"><div className="panel-head"><div><span className="eyebrow">CONTROL OPERATIVO</span><h2>Ejecutar el flujo de datos</h2><p className="nota">Ingesta, transformación y publicación sin utilizar la terminal.</p></div><Insignia valor={trabajo?.estado||'INACTIVO'}/></div>
    <div className="operator-auth"><label>Token de operador<input type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} placeholder="Token configurado en .env" disabled={ocupado}/></label><button disabled={!token||ocupado} onClick={consultar}>Conectar</button></div>
    <div className="source-options">{['USGS','FIRMS','OPEN_METEO','NASA_POWER'].map(x=><label key={x}><input type="checkbox" checked={fuentes.includes(x)} disabled={ocupado} onChange={e=>setFuentes(p=>e.target.checked?[...p,x]:p.filter(y=>y!==x))}/>{x}</label>)}</div>
    <details><summary>Opciones de extracción</summary><div className="operator-auth"><label>Días (1–14; FIRMS máx. 5)<input type="number" min="1" max="14" value={dias} disabled={ocupado} onChange={e=>setDias(e.target.value)}/></label><label>Atraso histórico (7–90 días)<input type="number" min="7" max="90" value={atraso} disabled={ocupado} onChange={e=>setAtraso(e.target.value)}/></label></div></details>
    <div className="steps-grid">{[['01','Extraer','Conservar originales en Bronze','extraer'],['02','Limpiar','Validar, deduplicar y cargar Core','limpiar'],['03','Publicar','Sincronizar el Data Warehouse','publicar']].map(([n,t,d,a])=><div className="step" key={a}><small>PASO {n}</small><h3>{t}</h3><p>{d}</p><button disabled={bloqueado} onClick={()=>iniciar(a)}>{t}</button></div>)}</div>
    <div className="operator-actions"><button className="primary" disabled={bloqueado} onClick={()=>iniciar('completo')}>{ocupado?'Procesando…':'Ejecutar todo'}</button><button onClick={()=>{onActualizar();onMapa()}}>Mostrar en el mapa</button><button onClick={onActualizar}>Actualizar historial</button></div>
    {error&&<p role="alert" className="mensaje error">{error}</p>}{trabajo?.error&&<p className="mensaje error">{trabajo.error}</p>}
    {trabajo?.pasos?.length>0&&<details open><summary>Actividad de la tarea</summary><div className="job-log" aria-live="polite">{trabajo.pasos.map((p,i)=><div key={i}><span>{p.paso}</span><span>{p.estado}</span></div>)}</div></details>}
    <p className="nota">FIRMS necesita MAP_KEY. Las fuentes meteorológicas son modelos históricos, no estaciones en vivo. El estado de la tarea es temporal; el historial de ingestas permanece en PostgreSQL.</p>
  </section>
}
function RadarTermico({refresco}){
  const [umbral,setUmbral]=useState(30),[minimo,setMinimo]=useState(3),[desde,setDesde]=useState(''),[hasta,setHasta]=useState('')
  const q=new URLSearchParams({umbral,minimo,...(desde?{desde}:{}),...(hasta?{hasta}:{})}).toString()
  const e=useDatos(['/api/v1/termico?'+q],q+'|'+refresco),r=e.datos?.[0]
  const [seleccion,setSeleccion]=useState('');const items=r?.items||[],actual=items.find(g=>g.fuente+'|'+g.ciudad===seleccion)||items[0]
  return <><section className="panel radar-hero"><span className="eyebrow">MÓDULO INNOVADOR · M6</span><h2>Radar de episodios térmicos</h2><p>Identifica rachas consecutivas de máximas diarias por ciudad y proveedor, sin mezclar detecciones satelitales con temperatura del aire.</p><div className="filtros"><label>Umbral (°C)<input type="number" min="-10" max="55" value={umbral} onChange={e=>setUmbral(e.target.value)}/></label><label>Días consecutivos<input type="number" min="2" max="14" value={minimo} onChange={e=>setMinimo(e.target.value)}/></label><label>Desde (UTC)<input type="date" value={desde} onChange={e=>setDesde(e.target.value)}/></label><label>Hasta (UTC)<input type="date" value={hasta} onChange={e=>setHasta(e.target.value)}/></label></div><p className="nota">Criterio exploratorio para posibles olas de calor, no definición climatológica oficial. Open-Meteo exige 24 horas con temperatura por día UTC; NASA POWER usa su máxima diaria. Los huecos interrumpen las rachas.</p></section><Mensaje estado={e}/>{r&&<><div className="metric-grid"><Tarjeta etiqueta="Episodios detectados" valor={fmt(items.reduce((a,g)=>a+g.episodios.length,0))} nota="Por fuente y ciudad; no deduplicados entre modelos"/><Tarjeta etiqueta="Series disponibles" valor={fmt(items.length)} nota="Ciudad × proveedor"/><Tarjeta etiqueta="Días mínimos" valor={r.minimo} nota={`Umbral ${r.umbral} °C`}/></div>{!items.length?<SinDatos texto="Sin temperaturas procesadas. Extrae Open-Meteo o NASA POWER y completa Limpiar."/>:<><section className="panel"><h2>Contraste entre modelos</h2><p className="nota">Compara máximas diarias en fechas UTC comunes. La coincidencia no valida observaciones de estación ni confirma una ola de calor.</p>{r.contraste?.length?<div className="table-scroll"><table><thead><tr>{['Ciudad','Días comunes','Diferencia media absoluta (°C)','Días en episodio ambos','Días en episodio solo uno'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{r.contraste.map(x=><tr key={x.ciudad}><td>{x.ciudad}</td><td>{x.dias_comparables}</td><td>{x.diferencia_media_absoluta??'—'}</td><td>{x.dias_en_episodio_ambos}</td><td>{x.dias_en_episodio_solo_uno}</td></tr>)}</tbody></table></div>:<SinDatos texto="Carga las dos fuentes meteorológicas para contrastarlas."/>}</section><section className="panel"><h2>Exploración geográfica</h2><div className="map-canvas radar-map"><MapContainer center={[-17,-65]} zoom={6} style={{height:'100%',width:'100%'}}><TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>{items.map(g=><CircleMarker key={g.fuente+g.ciudad} center={[g.latitud,g.longitud]} radius={g.episodios.length?15:8} pathOptions={{color:g.episodios.length?'#c05b13':'#0071e3',fillOpacity:.55}} eventHandlers={{click:()=>setSeleccion(g.fuente+'|'+g.ciudad)}}><Tooltip>{g.ciudad} · {g.fuente} · {g.episodios.length} episodios</Tooltip></CircleMarker>)}</MapContainer></div></section><section className="panel"><div className="panel-head"><h2>Serie diaria y cobertura</h2><select aria-label="Serie térmica" value={actual.fuente+'|'+actual.ciudad} onChange={e=>setSeleccion(e.target.value)}>{items.map(g=><option key={g.fuente+g.ciudad} value={g.fuente+'|'+g.ciudad}>{g.ciudad} · {g.fuente}</option>)}</select></div><p>{actual.dias_validos} de {actual.dias_ventana} días con datos válidos.</p><div className="daily-series">{actual.serie.map(x=><div key={x.fecha}><span>{x.fecha}</span><div className="barra"><i style={{display:'block',height:'100%',width:`${x.maxima===null?0:Math.max(0,Math.min(100,(x.maxima+10)/65*100))}%`,background:x.maxima>=r.umbral?'#c05b13':'#0071e3'}}/></div><b>{x.maxima===null?'Incompleto':`${x.maxima} °C`}</b></div>)}</div><h2>Episodios</h2>{actual.episodios.length?<div className="table-scroll"><table><thead><tr>{['Inicio','Fin','Días','Máxima','Exceso °C·día'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{actual.episodios.map(x=><tr key={x.desde}><td>{x.desde}</td><td>{x.hasta}</td><td>{x.dias}</td><td>{x.maxima} °C</td><td>{x.exceso_grados_dia}</td></tr>)}</tbody></table></div>:<SinDatos texto="No se detectaron episodios con este criterio y cobertura. Esto no demuestra ausencia de olas de calor."/>}</section></>}</>}</>
}

function App(){
  const [pagina,setPagina]=useState('inicio')
  const [refresco,setRefresco]=useState(0)
  const [salud,setSalud]=useState('Comprobando API')
  useEffect(()=>{obtener('/ready').then(()=>setSalud('API conectada')).catch(()=>setSalud('API no disponible'))},[refresco])
  const titulo=SECCIONES.find(x=>x.id===pagina)?.nombre||'Inicio'
  const partes={inicio:Inicio,mapa:Mapa,analitica:Analitica,etl:Procesamiento,fuentes:Fuentes,termico:RadarTermico}
  const Vista=partes[pagina]
  return <div className="shell">
    <aside className="sidebar"><div className="brand"><span className="brand-icon">◉</span><div><strong>GeoETL</strong><small>DATA ENGINEERING</small></div></div>
      <p className="nav-heading">PLATAFORMA</p><nav aria-label="Navegación principal">{SECCIONES.map(x=><button type="button" key={x.id} aria-current={x.id===pagina?'page':undefined} onClick={()=>setPagina(x.id)} className={'nav '+(x.id===pagina?'activo':'')}><span aria-hidden="true">{x.icono}</span>{x.nombre}</button>)}</nav>
      <div className="sidebar-end"><i/>GeoETL 2.0 · Centro ambiental</div>
    </aside>
    <main className="main"><header className="topbar"><span>Datos ambientales · Bolivia y entorno</span><div className="top-actions"><span className="conexion">{salud}</span><button type="button" onClick={()=>setRefresco(x=>x+1)} aria-label="Actualizar datos" className="refresh">↻ Actualizar</button></div></header>
      <div className="contenido"><div className="eyebrow">PLATAFORMA / {titulo.toUpperCase()}</div><div className="page-head"><div><h1>{titulo}</h1><p>Integración, análisis y trazabilidad de información ambiental.</p></div><span className="info-chip">● Datos de origen externo</span></div>
        <Vista refresco={refresco} onActualizar={()=>setRefresco(x=>x+1)} onMapa={()=>setPagina('mapa')}/>
        <footer>GeoETL · Integración USGS / FIRMS / Open-Meteo / NASA POWER · Información analítica, no alertas oficiales.</footer>
      </div>
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
