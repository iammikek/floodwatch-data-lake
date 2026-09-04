# Prediction corridor backfill (P1)

Backfill mined EA stage history for the **A361 Muchelney** prediction corridor — the minimum data required before `historic_analogue_v1` can run on live hydrology.

**Ref:** `flood-watch/docs/build/11-prediction-v1-analogues.md` (P1)

---

## Measures

| measure_id | Gauge |
|------------|-------|
| `52119-level-stage-i-15_min-mASD` | Gaw Bridge · River Parrett (primary) |
| `52153-level-stage-i-15_min-mASD` | Midelney · River Isle |
| `52245-level-stage-i-15_min-m` | Westonzoyland PS |
| `52230-level-stage-i-15_min-m` | Langport Great Bow |

Registry: `api/config/corridors.py` (`a361-muchelney`).

---

## Quick start

Prereqs: Docker Desktop, `.env` configured, network access to EA APIs.

```bash
# Default: 2 years ago January → current month, resume missing slices
./scripts/run-corridor-backfill.sh

# Explicit window (recommended for v1: 24–60 months)
FROM=2022-01 TO=2026-03 ./scripts/run-corridor-backfill.sh

# Extended window for golden eval scenarios (Jan 2014, Feb 2020)
FROM=2013-12 TO=2026-09 ./scripts/run-corridor-backfill.sh

# Re-run safely — skips months that already have non-empty readings
RESUME=1 FROM=2013-12 TO=2026-09 ./scripts/run-corridor-backfill.sh

# Hydrology archive (long retention) for mapped gauges — currently Westonzoyland
python -m ingestion.cli backfill-ea-hydrology-corridor \
  --corridor a361-muchelney --from 2013-09 --to 2026-09 --resume
```

Gaw Bridge / Midelney / Langport Great Bow are **not** exact matches in the
Hydrology catalogue. Proxies in `api/config/hydrology_measures.py`:

| FM measure | Proxy hydrology station | Notes |
|------------|-------------------------|-------|
| Gaw Bridge `52119-…` | Thorney Mill (~3.1 km) | Archive from 2011; covers 2014/2020 |
| Great Bow `52230-…` | Monks Leaze (~1 km) | Archive from 2007; covers 2014/2020 |
| Midelney `52153-…` | *(none yet)* | Midelney Lock is ~90 m but only from Aug 2022 |
| Westonzoyland `52245-…` | Exact match | Archive from 1998 |

```bash
# Hydrology archive (mapped + proxy gauges) — use last full month as --to
python -m ingestion.cli backfill-ea-hydrology-corridor \
  --corridor a361-muchelney --from 2013-09 --to 2026-08 --resume
```

Via Docker:
```bash
docker compose exec -T lake-worker python -m ingestion.cli backfill-ea-hydrology-corridor \
  --corridor a361-muchelney --from 2013-09 --to 2026-08 --resume
```

Output path per month:

`data/raw/ea/readings/{measure_id}/{YYYY}-{MM}.ndjson.gz`

---

## CLI (inside lake-worker)

```bash
docker compose exec -T lake-worker python -m ingestion.cli backfill-ea-corridor \
  --corridor a361-muchelney \
  --from 2022-01 \
  --to 2026-03 \
  --resume

docker compose exec -T lake-worker python -m ingestion.cli check-corridor-coverage \
  --corridor a361-muchelney \
  --from 2022-01 \
  --to 2026-03 \
  --min-months 24
```

Coverage report only (no exit on gap):

```bash
python -m ingestion.cli check-corridor-coverage \
  --corridor a361-muchelney \
  --from 2022-01 \
  --to 2026-03
```

---

## Acceptance (P1)

- [ ] Each of the four measures has **≥ 24** non-empty monthly files for the chosen window
- [ ] `check-corridor-coverage --min-months 24` exits 0
- [ ] `GET /v1/predictions?corridor=a361-muchelney` returns non-`no_data` primary analysis (after P2 engine)

---

## Notes

- **Idempotent:** `--resume` skips existing month files; safe to interrupt and rerun.
- **Not in public git:** raw `data/raw/` stays on private Bitbucket / local disk only.
- **Region backfill** (`./scripts/run-collector.sh`) still useful for discovery; corridor backfill is targeted and faster for prediction v1.
