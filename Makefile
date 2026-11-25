# GeoETL v1.0: Windows Git Bash con GNU Make y Docker Compose v2
.DEFAULT_GOAL := ayuda
COMPOSE := docker compose
DIAS ?= 7
DIAS_SEGUNDA ?= 2
FUENTE ?= auto
ATRASO ?= 10
CIUDAD ?= la_paz
ID ?=
.PHONY: ayuda preparar iniciar migrar roles iniciar-bd estado urls detener construir usgs segunda ingesta silver gold pipeline reprocesar verificar bronze integridad consultar pruebas test-unit test-api test-features test-integration test-integracion test-e2e test-all demo programador programador-parar programador-logs testdb-iniciar testdb-migrar salud registros test-performance historico

ayuda:
	@printf '\nGeoETL v1.0 | Comandos\n\n'
	@printf ' make preparar       -> copiar .env.example (no reemplaza .env)\n'
	@printf ' make iniciar        -> iniciar DB, migrar, roles, API y web\n'
	@printf ' make pipeline       -> extracciones + Silver/Core + Gold\n'
	@printf ' make usgs DIAS=7    -> extraer USGS a Bronze\n'
	@printf ' make historico DESDE=2026-01-01 HASTA=2026-02-01 -> backfill USGS\n'
	@printf ' make segunda FUENTE=auto DIAS_SEGUNDA=2 -> FIRMS/Open-Meteo\n'
	@printf ' make silver         -> procesar Bronze pendientes\n'
	@printf ' make gold           -> sincronizar Core -> Gold\n'
	@printf ' make reprocesar ID=UUID -> regenerar desde archivo original\n'
	@printf ' make verificar      -> inspeccionar Core/Gold/ops\n'
	@printf ' make pruebas        -> pruebas locales unitarias/API/funcionales\n'
	@printf ' make test-integration -> tests reales PostgreSQL/PostGIS aislado\n'
	@printf ' make test-e2e      -> Playwright (requiere descargar imagen grande)\n'
	@printf ' make test-all      -> todas las categorías\n'
	@printf ' make programador   -> iniciar automatización opcional\n'
	@printf ' make demo          -> comprobar pipeline ya ejecutado (sin extraer)\n'
	@printf ' make detener       -> detener sin borrar volumen DB\n\n'

preparar:
	@if [ -f .env ]; then printf '.env existente: no se sobrescribe. Verificar API_DB_PASSWORD.\n'; else cp .env.example .env && printf 'Edita .env y cambia contraseñas.\n'; fi

construir:
	$(COMPOSE) build etl api web operador

# Instalar/actualizar en el mismo Postgres: jamás hace down -v.
migrar:
	$(COMPOSE) exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f /sql/migraciones/001_base.sql'
	$(COMPOSE) exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f /sql/semillas/001_catalogos.sql'
	$(COMPOSE) exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f /sql/migraciones/002_semana2.sql'
	$(COMPOSE) exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f /sql/migraciones/003_gold.sql'
	$(COMPOSE) exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f /sql/migraciones/004_fuentes_v2.sql'

roles:
	$(COMPOSE) run --rm etl python -m pipelines.security

iniciar-bd: migrar roles

iniciar:
	$(COMPOSE) up -d --wait db
	$(COMPOSE) build etl api web operador
	"$(MAKE)" --no-print-directory migrar
	"$(MAKE)" --no-print-directory roles
	$(COMPOSE) up -d api web operador
	"$(MAKE)" --no-print-directory urls

estado:
	$(COMPOSE) ps

urls:
	@printf 'Web: http://localhost:5173/\nAPI: http://localhost:8000/docs\n'

salud:
	$(COMPOSE) exec -T api python -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8000/ready",timeout=10).read().decode())'

registros:
	$(COMPOSE) logs -f --tail=60 api web db

usgs:
	$(COMPOSE) run --rm etl python -m pipelines.cli extraer-usgs --dias $(DIAS)

historico:
	@test -n "$(DESDE)" -a -n "$(HASTA)" || (echo "Debes dar DESDE y HASTA (hasta exclusivo)"; exit 2)
	$(COMPOSE) run --rm etl python -m pipelines.historico --desde $(DESDE) --hasta $(HASTA)

segunda:
	$(COMPOSE) run --rm etl python -m pipelines.semana2 extraer-segunda --fuente $(FUENTE) --dias $(DIAS_SEGUNDA) --atraso $(ATRASO) --ciudad $(CIUDAD)

ingesta: usgs segunda

silver:
	$(COMPOSE) run --rm etl python -m pipelines.semana2 procesar-pendientes

gold:
	$(COMPOSE) run --rm etl python -m pipelines.cargas.gold

pipeline:
	$(COMPOSE) run --rm etl python -m pipelines.orquestador --dias-usgs $(DIAS) --dias-segunda $(DIAS_SEGUNDA) --fuente $(FUENTE) --atraso $(ATRASO) --ciudad $(CIUDAD)

reprocesar:
	@test -n "$(ID)" || (echo 'Indicar ID=<uuid>' >&2; exit 2)
	$(COMPOSE) run --rm etl python -m pipelines.semana2 reprocesar --id-ejecucion $(ID)
	"$(MAKE)" --no-print-directory gold

consultar:
	$(COMPOSE) exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f /sql/vista_verificacion.sql'

verificar:
	$(COMPOSE) exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f /sql/vistas/verificar_gold.sql'
	$(COMPOSE) run --rm etl python -m pipelines.semana2 resumen

bronze:
	$(COMPOSE) run --rm etl python -c 'from pathlib import Path; import json; arch=sorted(Path("/app/datos/bronze/usgs").rglob("*.geojson"));print("Archivos Bronze USGS:",len(arch));[print(p.name,"->",len(json.loads(p.read_bytes())["features"]),"observaciones") for p in arch]'

integridad:
	$(COMPOSE) run --rm etl python -c 'import hashlib,os;from pathlib import Path;from pipelines.comun.bd import conectar;c=conectar();filas=c.execute("SELECT ruta_archivo,checksum_sha256 FROM ops.archivo_crudo ORDER BY fecha_extraccion DESC LIMIT 100").fetchall();c.close();base=Path(os.getenv("DATA_DIR","/app/datos"));r=[((base/p).is_file() and hashlib.sha256((base/p).read_bytes()).hexdigest()==h.strip()) for p,h in filas];print("SHA-256 verificados",sum(r),"de",len(r));assert r and all(r),"Error de integridad Bronze"'

pruebas: test-unit test-api test-features

test-unit:
	$(COMPOSE) run --rm etl python -m pytest -q tests/test_bronze.py tests/test_usgs.py tests/test_semana2.py tests/unit

test-api:
	$(COMPOSE) run --rm etl python -m pytest -q tests/test_api.py tests/api

test-features:
	$(COMPOSE) run --rm etl python -m pytest -q tests/features

testdb-iniciar:
	$(COMPOSE) --profile test up -d --wait testdb

testdb-migrar: testdb-iniciar
	@for f in 001_base.sql 002_semana2.sql 003_gold.sql 004_fuentes_v2.sql; do \
		$(COMPOSE) --profile test exec -T testdb psql -v ON_ERROR_STOP=1 -U geoetl_tester -d geoetl_test -f /sql/migraciones/$$f || exit 1; \
	done
	$(COMPOSE) --profile test exec -T testdb psql -v ON_ERROR_STOP=1 -U geoetl_tester -d geoetl_test -f /sql/semillas/001_catalogos.sql
	$(COMPOSE) --profile test run --rm -e PGHOST=testdb -e PGDATABASE=geoetl_test -e PGUSER=geoetl_tester -e PGPASSWORD=test_local_only -e API_DB_PASSWORD=test_reader_only etl python -m pipelines.security

test-integration: testdb-migrar
	$(COMPOSE) --profile test run --rm -e INTEGRATION_PG=1 -e PGHOST=testdb -e PGPORT=5432 -e PGDATABASE=geoetl_test -e PGUSER=geoetl_tester -e PGPASSWORD=test_local_only etl python -m pytest -q tests/integration -m 'not performance'

test-integracion: test-integration

test-performance: testdb-migrar
	$(COMPOSE) --profile test run --rm -e INTEGRATION_PG=1 -e PGHOST=testdb -e PGPORT=5432 -e PGDATABASE=geoetl_test -e PGUSER=geoetl_tester -e PGPASSWORD=test_local_only etl python -m pytest -q tests/integration -m performance

test-e2e:
	$(COMPOSE) --profile e2e run --rm e2e

test-all: pruebas test-integration test-performance test-e2e

programador:
	$(COMPOSE) --profile schedule up -d --build scheduler

programador-logs:
	$(COMPOSE) --profile schedule logs -f --tail=80 scheduler

programador-parar:
	$(COMPOSE) --profile schedule stop scheduler

demo:
	"$(MAKE)" --no-print-directory estado
	"$(MAKE)" --no-print-directory salud
	"$(MAKE)" --no-print-directory consultar
	"$(MAKE)" --no-print-directory verificar
	"$(MAKE)" --no-print-directory integridad
	"$(MAKE)" --no-print-directory pruebas
	"$(MAKE)" --no-print-directory urls

# Compatibilidad con atajos de las versiones anteriores
semana2-instalar: migrar
semana2-procesar: silver
semana2-resumen: verificar
semana2-test: pruebas
semana2-fuente: segunda
semana2-web:
	$(COMPOSE) up -d --build api web
semana2-todo: semana2-instalar segunda silver gold pruebas semana2-web

detener:
	$(COMPOSE) --profile schedule --profile test --profile e2e down
