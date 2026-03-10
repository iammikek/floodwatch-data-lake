# Changelog

## Unreleased
- Integrate EA flood warnings into /v1/warnings with geometry and severity
- Expand OpenAPI for measurements, tiles, and warnings schemas
- Optional Redis caching adapter and configuration hooks

## 0.1.0 — 2026-03-10
- Added /v1/measurements backed by NDJSON (raw/hour/day) with pagination
- Added /v1/polygons/tiles TMS endpoint with bbox filtering
- Introduced in‑process TTL cache and per‑IP rate limits
- Refactored API toward MVC (routers, services, models, utils)
- Extracted warnings into dedicated router/service (placeholder data)
- Added API tests for measurements, tiles, and rate limiting
- Updated Makefile: test‑api discovers and runs all API tests
