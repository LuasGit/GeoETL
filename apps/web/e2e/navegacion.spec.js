import {test,expect} from '@playwright/test'

// Recorre el frontend real con o sin observaciones; no fabrica respuestas API.
test('navegación completa con estados de carga o datos',async ({page})=>{
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Inicio'})).toBeVisible()
  for(const nombre of ['Mapa SIG','Analítica','Procesamiento ETL','Fuentes y calidad']){
    await page.getByRole('button',{name:new RegExp(nombre)}).click()
    await expect(page.getByRole('heading',{name:nombre,exact:true})).toBeVisible()
  }
})

test('el mapa Leaflet se renderiza y admite filtros',async ({page})=>{
  await page.goto('/')
  await page.getByRole('button',{name:/Mapa SIG/}).click()
  await expect(page.getByTestId('geoetl-map')).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()
  await page.getByLabel('Filtrar fenómeno').selectOption('SISMO')
  await expect(page.getByLabel('Filtrar fenómeno')).toHaveValue('SISMO')
})

test('analítica muestra sus filtros y consumo',async ({page})=>{
  await page.goto('/')
  await page.getByRole('button',{name:/Analítica/}).click()
  await expect(page.getByLabel('Fecha desde')).toBeVisible()
  await page.getByLabel('Fecha desde').fill('2026-10-01')
  await expect(page.getByLabel('Fecha desde')).toHaveValue('2026-10-01')
})

test('panel de operador y radar térmico disponibles', async ({page})=>{
  await page.goto('/')
  await page.getByRole('button',{name:/Procesamiento ETL/}).click()
  await expect(page.getByRole('button',{name:'Extraer',exact:true})).toBeDisabled()
  await expect(page.getByRole('button',{name:'Mostrar en el mapa'})).toBeVisible()
  await page.getByRole('button',{name:/Radar térmico/}).click()
  await expect(page.getByRole('heading',{name:'Radar de episodios térmicos'})).toBeVisible()
  await expect(page.getByLabel('Umbral (°C)')).toBeVisible()
})
