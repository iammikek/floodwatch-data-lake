SHELL := /bin/bash

.PHONY: up down logs-api logs-worker restart-api

up:
	docker compose up -d

down:
	docker compose down

logs-api:
	docker compose logs -f lake-api

logs-worker:
	docker compose logs -f lake-worker

restart-api:
	docker compose restart lake-api

collector:
	./scripts/run-collector.sh

corridor-backfill:
	./scripts/run-corridor-backfill.sh

corridor-coverage:
	docker compose exec -T lake-worker python -m ingestion.cli check-corridor-coverage \
	  --corridor $${CORRIDOR:-a361-muchelney} \
	  --from $${FROM:-2022-01} \
	  --to $${TO:-} \
	  --min-months $${MIN_MONTHS:-24}

clean-data:
	@echo "Removing zero-size archives and empty directories under data/raw/ea/readings..."
	@find data/raw/ea/readings -type f -name '*.ndjson.gz' -size 0 -print -delete || true
	@find data/raw/ea/readings -type d -empty -print -delete || true

floodzones-som:
	docker compose exec -T lake-worker python -u -m ingestion.cli fetch-ea-flood-zones-region --region SOM

rse-present-som:
	docker compose exec -T lake-worker python -u -m ingestion.cli fetch-ea-rivers-sea-extents-region --region SOM --scenario all

.PHONY: test test-api
test:
	@echo "Running unit tests inside lake-worker (Docker)..."
	docker compose exec -T -u root lake-worker python -m unittest discover -s tests -v

test-api:
	@echo "Running API tests inside lake-api (Docker)..."
	docker compose exec -T -u root lake-api python -m unittest discover -s tests -v
