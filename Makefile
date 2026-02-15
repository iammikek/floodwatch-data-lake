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

