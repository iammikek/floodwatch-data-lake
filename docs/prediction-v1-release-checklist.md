# Prediction v1 release checklist

**Schema:** `floodwatch.prediction.v1`
**Method:** `historic_analogue_v1`
**Corridor:** `a361-muchelney` (A361 Muchelney corridor, Somerset Levels)

---

## Data readiness

- [ ] All four corridor measures backfilled ≥ 24 months (target 60+)
  - `52119-level-stage-i-15_min-mASD` (Gaw Bridge) — flood-monitoring recent only; hydrology GUID pending
  - `52153-level-stage-i-15_min-mASD` (Midelney) — optional until long archive; omitted from analogue fingerprints when empty
  - `52245-level-stage-i-15_min-m` (Westonzoyland PS) — hydrology archive mapped
  - `52230-level-stage-i-15_min-m` (Langport Great Bow) — hydrology GUID pending
- [ ] `check-corridor-coverage --min-months 24` exits 0
- [ ] Backfill window includes golden eval periods: Jan 2014, Feb 2020, Aug 2018
- [ ] Empty gzip placeholders are not counted as coverage (resume refetch)

## Engine (data-lake)

- [x] `predict_corridor("a361-muchelney")` returns `floodwatch.prediction.v1`
- [x] Response includes ≥ 1 `historic_analogue` driver on a rising fixture
- [x] `analogue_consensus` driver always present with `impactRate` / `watchRate`
- [x] `method.name` = `historic_analogue_v1`
- [x] `method.parameters` includes `windowHours`, `historyDays`, `topK`, `minSimilarity`
- [x] `method.notes` visible and honest about limitations

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
- [ ] Real archive hindcast for Storm Dennis / Jan 2014 returns non-`no_data` (blocked until primary gauge archive exists)
- Soft gate: `tests/test_real_storm_replay.py` (skips without archive)

```bash
./scripts/replay-storms.sh
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
- [x] Storm replay picker + place history list
- [x] Larger place map; default `place` preset (flood bounds + gauges, route off)
- [x] Production mode: no silent mock fallback
- [x] Prediction panel first in main column

## Documentation

- [x] `AGENTS.md` includes hydrology archive + storm replay
- [x] `docs/prediction-corridor-backfill.md` covers hydrology mapping gap
- [x] `docs/place-lidar-volume.md` deferred LiDAR plan
- [x] flood-watch `docs/check-route-alternate-view.md` deferred route view
