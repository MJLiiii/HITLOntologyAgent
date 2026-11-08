SHELL := /bin/sh
PYTHON := .venv/bin/python
export PYTHONPATH := services/api/src

# Override JAVA_HOME on other installations; the default resolves this Mac's Java 21.
JAVA_HOME ?= /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
export JAVA_HOME
OE_JAVA_EXECUTABLE ?= $(JAVA_HOME)/bin/java
export OE_JAVA_EXECUTABLE

.PHONY: setup build build-jena demo dev-up dev-down api dev-api dev-worker dev-ui migrate test test-unit test-contract test-integration test-e2e lint research-pilot export-results export-pilot backup-restore-check api-contracts check-api-contracts

setup:
	uv sync --frozen
	uv venv --python 3.12.14 .venv-ontocheck
	uv pip sync --python .venv-ontocheck/bin/python requirements-ontocheck.lock
	# NLTK refuses language data writable by another account, even on a read-only mount.
	chmod -R go-w resources/nltk
	npm --prefix apps/studio-plugin ci

build-jena:
	"$(JAVA_HOME)/bin/java" -version
	mvn -B -f services/jena-runner/pom.xml package

build: build-jena
	npm --prefix apps/studio-plugin run build

migrate:
	$(PYTHON) scripts/migrate.py

demo: build migrate
	OE_EMBEDDED_WORKER=true $(PYTHON) -m uvicorn oe_studio.main:app --host 127.0.0.1 --port 8000

api: dev-api

dev-worker: migrate
	$(PYTHON) -m oe_studio.worker

dev-api: migrate
	OE_EMBEDDED_WORKER=false $(PYTHON) -m uvicorn oe_studio.main:app --host 127.0.0.1 --port 8000 --reload

dev-ui:
	npm --prefix apps/studio-plugin run dev

# Optional PostgreSQL only. Requires Docker Compose and OE_POSTGRES_PASSWORD.
dev-up:
	docker compose --env-file .env -f infra/compose.yaml up -d --wait

dev-down:
	docker compose --env-file .env -f infra/compose.yaml down

test: test-unit test-contract test-integration test-e2e

test-unit:
	$(PYTHON) -m pytest tests/unit -q

# Real isolated Jena and OntoCheck boundaries; setup and build-jena are prerequisites.
test-contract:
	$(PYTHON) -m pytest tests/test_validation.py tests/test_assessment.py tests/test_engine_isolation.py tests/test_pdf_ingestion.py tests/test_benchmark_compatibility.py tests/contracts -q

test-integration:
	$(PYTHON) -m pytest tests/integration -q

# In-process HTTP workflow plus frontend interactions. Browser/live-host smoke is separate.
test-e2e:
	$(PYTHON) -m pytest tests/integration/test_workflow.py -q
	npm --prefix apps/studio-plugin test

lint:
	.venv/bin/ruff check services/api/src tests scripts migrations
	cd apps/studio-plugin && npm exec -- tsc --noEmit

research-pilot:
	$(PYTHON) scripts/research_pilot.py

export-results:
	$(PYTHON) scripts/export_results.py

export-pilot:
	$(PYTHON) scripts/research_pilot.py --export-only

api-contracts:
	$(PYTHON) scripts/export_openapi.py

check-api-contracts:
	$(PYTHON) scripts/export_openapi.py --check

# Stop Studio first; requires an initialized .data SQLite/artifact/Git store.
backup-restore-check:
	$(PYTHON) scripts/backup_restore.py check --data-dir .data
