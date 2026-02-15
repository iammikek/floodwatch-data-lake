# Flood Watch Performance with the Data Lake

## Triage Now (>10 s)

- Measure end‑to‑end: log TTFB, backend time, and tool durations per request.
- Separate cold vs warm: capture cache hit ratio for measurements, warnings, and retrieve‑context.
- Cap upstream time: set HTTP connect timeout 500 ms, total 2000 ms, retries with jitter.
- Serve first paint fast: render authoritative lists immediately; lazy‑load LLM summary.
- Reduce fan‑out: replace multi‑tool calls with a single retrieve‑context lake call.

Example timers (Laravel):

```php
$t0 = microtime(true);
$signals = $lake->retrieveContext($region, $window);
$t1 = microtime(true);
logger()->info('lake.retrieve_context.ms', ['ms' => ($t1 - $t0) * 1000]);
```

## Objectives & SLOs

- P95 dashboard render < 700 ms from cache; P99 < 2 s on cold paths.
- LLM tool roundtrip budget < 2 s for typical corridor queries.
- < 2 external calls on hot paths (everything else pre‑fetched/warmed).

## Performance Risks Without the Lake

- Fan‑out to EA/National Highways and weather increases tail latencies.
- Repeated correlation and filtering per request wastes CPU and tokens.
- Large geospatial joins and vector search are expensive in‑app.
- LLM tool calling amplifies latency when inputs are not pre‑shaped.

## Lake Integration Principles

- Shift heavy work to the lake: time‑series aggregation, geospatial joins, embeddings, and correlation.
- Keep payloads small and stable: region/time/route‑scoped endpoints, compact schemas, compression.
- Embrace cacheability: deterministic URLs, ETag/Last‑Modified, and explicit TTL hints.

## Endpoint Contracts That Reduce Work

- GET /v1/measurements: pre‑aggregated series for station_id/from/to/aggregate/bbox.
- GET /v1/warnings: geometry‑filtered active warnings with minimal fields.
- GET /v1/forecast: compact 5‑day outlook per region.
- GET /v1/retrieve‑context: structured signals + snippets for RAG to avoid multi‑tool fan‑out.
- Optional: GET /v1/route‑depth: sampled max/mean depth along a route for each vehicle class.

## Caching Strategy in Laravel

- Keying: lake:{endpoint}:{region|bbox}:{time_slice_hash}.
- TTLs:
  - measurements (recent): 60–300 s; historical backfill: 24 h.
  - warnings: 60 s.
  - retrieve‑context: 120 s (per region/route/time window).
  - forecast: 30 min.
- Pattern: stale‑while‑revalidate — serve cached value immediately, dispatch a refresh job in background.
- Invalidation: event‑driven only for severe warnings; otherwise rely on short TTLs and SWR.

## Async Prefetch & Warmers

- Scheduler jobs warm popular regions (BS/BA/TA/EX/TQ/PL/TR) every 1–5 minutes.
- Route‑aware warmers: when a user schedules a route, enqueue prefetch of warnings/context/route‑depth for the delivery window.
- On deploy or cache purge, run a one‑off warm‑all job to restore steady state quickly.

## Lake Client Patterns (Laravel)

- Use the HTTP client with defaults:
  - timeouts: connect 500 ms, total 1500–2000 ms.
  - retries with jitter (e.g., 3 attempts, exponential backoff).
  - circuit breaker: open after N failures; short‑circuit to cached data for T seconds.
- Response handling:
  - Respect ETag/If‑None‑Match to avoid re‑downloading.
  - Gzip/Brotli compression enabled; ensure Accept‑Encoding is set.
  - Validate contracts strictly; fall back to previous cached payloads on schema mismatch.

Example LakeClient defaults:

```php
use Illuminate\Support\Facades\Http;

class LakeClient {
    public function __construct(private string $baseUrl, private string $token) {}
    private function http() {
        return Http::withToken($this->token)
            ->acceptJson()
            ->withHeaders(['Accept-Encoding' => 'gzip, br'])
            ->connectTimeout(0.5)
            ->timeout(2.0)
            ->retry(3, 200, throw: false);
    }
    public function retrieveContext(string $region, array $window) {
        return $this->http()
            ->get($this->baseUrl.'/v1/retrieve-context', [
                'region' => $region,
                'time_window' => $window,
            ])->json();
    }
}
```

## LLM Cost & Latency Control

- Replace multi‑tool orchestration with a single retrieve‑context call returning correlated signals and snippets.
- Trim inputs: only top‑K snippets and summarized series; avoid raw lists unless requested.
- Cache LLM outputs for identical prompts + region/time; bust cache only when underlying signals change materially.

## Queue & Concurrency

- Separate worker pools:
  - web: handles HTTP (Octane enabled).
  - warmers: scheduled prefetch and SWR refresh.
  - llm: tool calling and summarization.
- Horizon tuning: cap per‑pool concurrency; prioritize warmers to keep web hits hot.

## Failure Modes & Degradation

- If the lake is slow/unavailable:
  - serve last known good cached payloads with an “as of” timestamp.
  - reduce snippet K and skip non‑critical sections to keep latency budgets.
  - display partial data with clear provenance rather than failing closed.

## Observability

- Metrics:
  - lake_http_latency_ms{endpoint}, cache_hit_ratio{endpoint}, llm_tool_duration_ms.
  - dashboard_ttfb_ms, dashboard_render_ms.
- Tracing:
  - propagate trace headers to the lake; sample p95 slow requests.
- Logging:
  - structured JSON for all lake requests with status, latency, and cache status.

## Security & Limits

- Use service tokens scoped read‑only; rotate and store in environment secrets.
- Apply per‑token rate limits; coordinate burst allowances for warmers.
- Enforce request size caps; paginate long series where needed.

## Implementation Steps in Flood Watch

- Add LAKE_BASE_URL and LAKE_TOKEN to config.
- Build a LakeClient with timeouts/retries/SWR and ETag support.
- Wire dashboard to read from lake caches; fall back to stale caches on errors.
- Add warmers:
  - cron: regions cycle every minute.
  - on‑demand: enqueue when routes are created/updated.
- Switch LLM orchestration to retrieve‑context; cache summaries by (region, time_window, vehicle_profile).
- Enable Octane (Swoole or RoadRunner) for increased concurrency on API and Livewire endpoints.
- Use Http::pool for concurrent lake requests when multiple endpoints are needed.

Concurrent requests example:

```php
[$warnings, $forecast] = Http::pool(function ($pool) use ($client) {
    return [
        $pool->as('warnings')->withToken(env('LAKE_TOKEN'))->acceptJson()
            ->connectTimeout(0.5)->timeout(2.0)
            ->get(env('LAKE_BASE_URL').'/v1/warnings', ['region' => 'SW']),
        $pool->as('forecast')->withToken(env('LAKE_TOKEN'))->acceptJson()
            ->connectTimeout(0.5)->timeout(2.0)
            ->get(env('LAKE_BASE_URL').'/v1/forecast', ['region' => 'SW']),
    ];
});
```

## Validation

- Synthetic load: simulate 100 concurrent dashboard hits with warmed caches — target p95 < 300 ms.
- Chaos tests: throttle the lake; verify circuit breaker, stale data, and user messaging.
- Compare tool call counts and OpenAI tokens pre/post to quantify savings.
