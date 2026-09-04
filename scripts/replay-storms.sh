#!/usr/bin/env bash
# Replay curated storms against local EA readings (hindcast).
# Usage: ./scripts/replay-storms.sh [corridor]
set -euo pipefail
CORRIDOR="${1:-a361-muchelney}"
cd "$(dirname "$0")/.."
python - <<PY
from datetime import datetime, timezone
from api.config.storms import list_storms
from api.services.predictions import predict_corridor

corridor = "${CORRIDOR}"
for storm in list_storms(corridor):
    now = datetime.fromisoformat(storm["as_of"].replace("Z", "+00:00")).astimezone(timezone.utc)
    doc = predict_corridor(corridor, history_days=120, now=now)
    verdict = doc.get("prediction", {}).get("verdict")
    conf = doc.get("prediction", {}).get("confidence")
    print(f"{storm['id']}\tas_of={storm['as_of']}\tverdict={verdict}\tconfidence={conf}")
PY
