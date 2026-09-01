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

# Re-run safely — skips months that already have files
RESUME=1 FROM=2022-01 TO=2026-03 ./scripts/run-corridor-backfill.sh
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
