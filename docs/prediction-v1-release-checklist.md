# Prediction v1 release checklist

**Schema:** `floodwatch.prediction.v1`
**Method:** `historic_analogue_v1`
**Corridor:** `a361-muchelney` (A361 Muchelney corridor, Somerset Levels)

---

## Data readiness

- [ ] All four corridor measures backfilled ≥ 24 months (target 60+)
  - `52119-level-stage-i-15_min-mASD` (Gaw Bridge)
  - `52153-level-stage-i-15_min-mASD` (Midelney)
  - `52245-level-stage-i-15_min-m` (Westonzoyland PS)
  - `52230-level-stage-i-15_min-m` (Langport Great Bow)
- [ ] `check-corridor-coverage --min-months 24` exits 0
- [ ] Backfill window includes golden eval periods: Jan 2014, Feb 2020, Aug 2018

## Engine (data-lake)

- [ ] `predict_corridor("a361-muchelney")` returns `floodwatch.prediction.v1`
- [ ] Response includes ≥ 1 `historic_analogue` driver on a rising fixture
- [ ] `analogue_consensus` driver always present with `impactRate` / `watchRate`
- [ ] `method.name` = `historic_analogue_v1`
- [ ] `method.parameters` includes `windowHours`, `historyDays`, `topK`, `minSimilarity`
- [ ] `method.notes` visible and honest about limitations

## Golden eval scenarios (synthetic)

| ID | Period | Expected verdict | Test |
|----|--------|-----------------|------|
| `eval-2014-01` | Jan 2014 Parrett rise | `at_risk` or `watch` | `tests/test_prediction_eval.py::EvalJan2014ParrettRise` |
| `eval-2020-02` | Storm Dennis Feb 2020 | `at_risk` | `tests/test_prediction_eval.py::EvalFeb2020StormDennis` |
| `eval-stable-summer` | Aug 2018 low flow | `clear` | `tests/test_prediction_eval.py::EvalAug2018StableSummer` |
| confidence monotonic | Synthetic gradient | impact ≥ mixed ≥ clear | `tests/test_prediction_eval.py::EvalConfidenceMonotonic` |

All eval tests pass:
```bash
docker compose exec -T lake-worker python -m unittest tests.test_prediction_eval -v
```

## API (data-lake)

- [ ] `GET /v1/predictions?corridor=a361-muchelney` returns 200 with v1 schema
- [ ] `GET /v1/predictions/corridors` lists `a361-muchelney`
- [ ] OpenAPI spec (`docs/openapi-data-lake.yaml`) documents v1 response shape
- [ ] API tests pass: `tests/test_api_predictions.py`

## Laravel proxy (flood-watch)

- [ ] `CorridorPredictionService` expects `floodwatch.prediction.v1`
- [ ] `GET /flood-watch/predictions?corridor=a361-muchelney` proxies v1
- [ ] Fixture `tests/fixtures/data_lake_predictions.json` conforms to v1
- [ ] Laravel tests pass (prediction-focused):
  - `FloodWatchPredictionsControllerTest`
  - `CorridorPredictionServiceTest`
  - `DataLakeClientContractTest`

## Cockpit (flood-watch)

- [ ] Prediction panel renders **first** in main column (`primary-panel` class)
- [ ] `fetchPrediction.js` warns on schema mismatch (not v1)
- [ ] Mock payloads (`prediction-risk.json`, `prediction-stable.json`) use v1
- [ ] Production mode: no silent mock fallback — show error panel when lake unavailable
- [ ] `method.notes` visible in contract annotation line
- [ ] Cockpit tests pass: `App.test.js`, `PredictionPanel.test.js`

## Documentation

- [ ] `README.md` references `floodwatch.prediction.v1`
- [ ] `docs/ux-wireframes/prediction-contract.md` updated to v1
- [ ] `docs/build/11-prediction-v1-analogues.md` status = implemented
- [ ] `docs/prediction-corridor-backfill.md` covers extended backfill window
- [ ] `AGENTS.md` includes corridor backfill instructions
