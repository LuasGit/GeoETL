import {defineConfig,devices} from '@playwright/test'
export default defineConfig({
  testDir:'./e2e',
  timeout:25000,
  expect:{timeout:10000},
  use:{baseURL:process.env.BASE_URL||'http://localhost:5173',trace:'retain-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}},
            {name:'mobile-chromium',use:{...devices['Pixel 5']}}],
  reporter:[['list'],['html',{open:'never',outputFolder:'test-results/reporte-html'}]],
})
