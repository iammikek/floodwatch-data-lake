# Prediction v1 release checklist

**Schema:** `floodwatch.prediction.v1`
**Method:** `historic_analogue_v1`
**Corridor:** `a361-muchelney` (A361 Muchelney corridor, Somerset Levels)

---

## Data readiness

- [x] Required corridor measures backfilled ≥ 24 months across golden windows (target 60+)
  - `52119-level-stage-i-15_min-mASD` (Gaw Bridge) — **hydrology proxy:** Thorney Mill (~3.1 km)
  - `52153-level-stage-i-15_min-mASD` (Midelney) — **optional**; no long archive yet (Midelney Lock from Aug 2022 only); omitted from analogue fingerprints when empty
  - `52245-level-stage-i-15_min-m` (Westonzoyland PS) — exact hydrology archive
  - `52230-level-stage-i-15_min-m` (Langport Great Bow) — **hydrology proxy:** Monks Leaze (~1 km)
- [x] Mapped / proxy gauges satisfy coverage for storm windows (Midelney excluded from hard gate while optional)
- [x] Backfill window includes golden eval periods: Jan–Feb 2014, Feb 2020, Aug 2018
- [x] Empty gzip placeholders are not counted as coverage (resume refetch)

```bash
# Expect Midelney shortfall until a long series is mapped:
python -m ingestion.cli check-corridor-coverage \
  --corridor a361-muchelney --from 2013-09 --to 2026-08 --min-months 24
```

## Engine (data-lake)

- [x] `predict_corridor("a361-muchelney")` returns `floodwatch.prediction.v1`
- [x] Response includes ≥ 1 `historic_analogue` driver on a rising fixture
- [x] `analogue_consensus` driver always present with `impactRate` / `watchRate`
- [x] `method.name` = `historic_analogue_v1`
- [x] `method.parameters` includes `windowHours`, `historyDays`, `topK`, `minSimilarity`
- [x] `method.notes` visible and honest about limitations
- [x] Optional gauges without archive are omitted from multi-gauge fingerprints

## Golden eval scenarios (synthetic)

| ID | Period | Expected verdict | Test |
|----|--------|-----------------|------|
| `eval-2014-01` | Jan–Feb 2014 Levels flood (`as_of` mid-Feb) | `at_risk` or `watch` | `tests/test_prediction_eval.py::EvalJan2014ParrettRise` |
| `eval-2020-02` | Storm Dennis Feb 2020 | `at_risk` | `tests/test_prediction_eval.py::EvalFeb2020StormDennis` |
| `eval-stable-summer` | Aug 2018 low flow | `clear` | `tests/test_prediction_eval.py::EvalAug2018StableSummer` |
| confidence monotonic | Synthetic gradient | impact ≥ mixed ≥ clear | `tests/test_prediction_eval.py::EvalConfidenceMonotonic` |

All synthetic eval tests pass:
```bash
docker compose exec -T lake-worker python -m unittest tests.test_prediction_eval -v
```

## Real-data storm replay

- [x] Catalogue: `api/config/storms.py` + `GET /v1/storms`
- [x] API `as_of` query param on `GET /v1/predictions`
- [x] Real archive hindcast (3 active gauges): Jan–Feb 2014 → `at_risk`, Storm Dennis → `at_risk`, Aug 2018 → `clear`
- Soft gate: `tests/test_real_storm_replay.py` (skips without archive)

```bash
./scripts/replay-storms.sh
# Expected (local archive + proxies, Midelney optional):
#   eval-2014-01        verdict=at_risk
#   eval-2020-02        verdict=at_risk
#   eval-stable-summer  verdict=clear
python -m unittest tests.test_real_storm_replay -v
```

## API (data-lake)

- [x] `GET /v1/predictions?corridor=a361-muchelney` returns 200 with v1 schema
- [x] `GET /v1/predictions?as_of=...` hindcast supported
- [x] `GET /v1/storms` catalogues curated events
- [x] `GET /v1/predictions/corridors` lists `a361-muchelney`
- [x] OpenAPI spec documents `as_of` + storms
- [x] API tests: `tests/test_api_predictions.py`

## Laravel proxy (flood-watch)

- [x] `CorridorPredictionService` expects `floodwatch.prediction.v1`
- [x] Proxies `as_of` and `/flood-watch/storms`
- [x] Fixture `tests/fixtures/data_lake_predictions.json` conforms to v1

## Cockpit (flood-watch)

- [x] Place-first surface (route UI behind `SHOW_ROUTE_VIEW=false`)
- [x] Storm replay picker + place history list (expanded Muchelney catalogue with kind / severity / impact_summary)
- [x] Larger place map; default `place` preset (flood bounds + gauges, route off)
- [x] Production mode: no silent mock fallback
- [x] Prediction panel first in main column
- [x] Local smoke: cockpit session → `/flood-watch/storms` + `as_of` predictions match lake `replay-storms.sh` (2026-09-04: at_risk / at_risk / clear)

## Documentation

- [x] `AGENTS.md` includes hydrology archive + storm replay
- [x] `docs/prediction-corridor-backfill.md` covers hydrology mapping gap
- [x] `docs/place-lidar-volume.md` deferred LiDAR plan
- [x] flood-watch `docs/check-route-alternate-view.md` deferred route view

## Cockpit smoke (manual / scripted)

With lake-api on `:8000` and flood-watch Sail on `:80` (`FLOOD_WATCH_DATA_LAKE_URL=http://host.docker.internal:8000`):

```bash
# Lake (no session)
curl -sS "http://127.0.0.1:8000/v1/storms?corridor=a361-muchelney"
curl -sS "http://127.0.0.1:8000/v1/predictions?corridor=a361-muchelney&as_of=2020-02-16T12:00:00Z"

# Laravel proxy needs the cockpit session cookie (EnsureFloodWatchSession)
COOKIE_JAR=$(mktemp)
curl -sS -c "$COOKIE_JAR" -b "$COOKIE_JAR" -o /dev/null "http://127.0.0.1/"
curl -sS -c "$COOKIE_JAR" -b "$COOKIE_JAR" -H "Accept: application/json" \
  "http://127.0.0.1/flood-watch/storms?corridor=a361-muchelney"
curl -sS -c "$COOKIE_JAR" -b "$COOKIE_JAR" -H "Accept: application/json" \
  "http://127.0.0.1/flood-watch/predictions?corridor=a361-muchelney&as_of=2020-02-16T12:00:00Z"
rm -f "$COOKIE_JAR"
```

Verified local pass (lake ≡ Laravel): Jan–Feb 2014 `at_risk` 0.78, Storm Dennis `at_risk` 0.9, Aug 2018 `clear` 0.62.
