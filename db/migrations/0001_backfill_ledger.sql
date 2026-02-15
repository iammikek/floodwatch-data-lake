CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS backfill_ledger (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset text NOT NULL,
  region_id text NULL,
  series_id text NULL,
  slice_from timestamptz NOT NULL,
  slice_to timestamptz NOT NULL,
  grain text NOT NULL,
  source_url text NOT NULL,
  source_etag text NULL,
  dest_path text NOT NULL,
  status text NOT NULL,
  attempt_count int NOT NULL DEFAULT 0,
  rows_ingested int NOT NULL DEFAULT 0,
  bytes_raw bigint NOT NULL DEFAULT 0,
  duration_ms bigint NOT NULL DEFAULT 0,
  started_at timestamptz NULL,
  finished_at timestamptz NULL,
  last_error text NULL,
  worker_id text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT backfill_ledger_slice_chk CHECK (slice_to > slice_from),
  CONSTRAINT backfill_ledger_dataset_chk CHECK (dataset IN ('hydrology_readings','haduk_grid_daily','era5_land_hourly','nrfa_daily','incidents','other')),
  CONSTRAINT backfill_ledger_grain_chk CHECK (grain IN ('month','day','hour')),
  CONSTRAINT backfill_ledger_status_chk CHECK (status IN ('pending','running','success','partial','failed','skipped'))
);

CREATE UNIQUE INDEX IF NOT EXISTS backfill_ledger_unique_slice
ON backfill_ledger (dataset, COALESCE(region_id, ''), COALESCE(series_id, ''), slice_from, slice_to);

CREATE INDEX IF NOT EXISTS backfill_ledger_status_idx ON backfill_ledger (status);
CREATE INDEX IF NOT EXISTS backfill_ledger_report_idx ON backfill_ledger (dataset, region_id, slice_from);

