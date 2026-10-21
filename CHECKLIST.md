# Weather API Cache — Project Checklist

Based on the project requirements and architecture diagram:

```
Client ⇄ Weather API ──1. check cache──▶ Redis
                     ◀─2. cache response─
                     ──5. save cached results──▶ Redis
         Weather API ──3. request──▶ 3rd-party weather service
                     ◀─4. response───
```

Status as of 2026-10-20. Items marked *(partial)* are started but not finished.

## 1. Project setup

- [x] Pick a stack: FastAPI + httpx (`pyproject.toml`)
- [x] Add the Redis client dependency (`redis>=8.1.0`)
- [x] Type checking with Pyrefly enabled for the project (`[tool.pyrefly]` in `pyproject.toml`; check with `uvx pyrefly check`)
- [x] Redis server running locally (Homebrew service, `127.0.0.1:6379`)
- [x] Verify the app can connect to Redis (`ping()` → `PONG`)

## 2. Start with a hardcoded response

- [ ] *(partial)* Skipped straight to the real API call, which is fine. Useful fallback for isolating routing issues if you get stuck.

## 3. Environment variables

- [x] Weather API key read from env (`config.py`), stored as `SecretStr` with `min_length=1` — empty or missing key is rejected
- [x] Base URL configurable via env, with a default
- [x] `.env` is in `.gitignore`, and `.env.example` lists the variable names without real values
- [x] `pydantic-settings`, `Depends(get_settings)` + `@lru_cache`, fail fast in the `lifespan`
- [x] Secret unwrapped with `.get_secret_value()` only inside the request, not at import time
- [x] `env_file` is an absolute path (`BASE_DIR / ".env"`)
- [x] Type alias renamed (`EnvSettings`)
- [x] `redis_url` in `Settings` with a default, documented as `REDIS_URL` (commented out) in `.env.example`
- [x] Cache TTL in env (`cache_ttl_seconds: Annotated[int, Field(ge=1)] = 43200` in `Settings`, `CACHE_TTL_SECONDS` in `.env.example`) — `ge=1` blocks `0`, which Redis rejects for `SET ... EX`
- [x] `env_ignore_empty=True` in `model_config` — an empty value (`KEY=`) falls back to the default; an empty API key still fails as “Field required”
- [ ] *(Optional, Pyright only)* `# pyright: ignore[reportCallIssue]` on `return Settings()` — Pyrefly doesn’t report this false positive, so it’s only needed if you also run Pyright
- [x] Lowercase field names (`weather_api_key`, `api_base_url`, `redis_url`) — env var names in `.env` stay UPPERCASE
- [x] Upstream timeout in env (`api_timeout_seconds: Annotated[float, Field(gt=0)] = 3.0`, `API_TIMEOUT_SECONDS` in `.env.example`) — `gt=0` blocks `0` (httpx fails instantly with `ConnectError`); plain `float` blocks `None` (no timeout)
  - Field name ↔ env var name must match (`api_time_out_seconds` ≠ `API_TIMEOUT_SECONDS` → “Extra inputs are not permitted”, app won’t start)
- [x] Gotcha: VS Code’s `python.terminal.useEnvFile` copies `.env` into a terminal **when it opens** — real env vars beat `.env`, so after changing `.env`, open a **new** terminal before restarting the server (found 2026-10-20: stale `API_BASE_URL` with a trailing `/`)

## 4. Fetch from the 3rd-party API (diagram steps 3–4)

- [x] Routes live under `/weather` (`APIRouter(prefix="/weather")`, 2026-10-20) — browsers request `/favicon.ico` on their own, and `/{location}` at the root treated it as a location and called Visual Crossing; root paths now get a `404` with no upstream call
- [x] `GET /weather/{location}` works against the real API (verified 2026-10-19: `200`, `resolvedAddress`, 15 days by default, ~170 KB)
- [x] Location sent in Visual Crossing’s URL path, URL-encoded with `quote()`; only `key` stays in `params`
  - `api_base_url` must **not** end with `/` — the route adds it (fixed 2026-10-19 in `config.py`, `.env`, `.env.example`; verified single `/`). A trailing `/` brings back `.../timeline//Vancouver` — document it in `.env.example` or guard it in code
- [x] Timeout set on purpose (2026-10-20): `AsyncClient(timeout=httpx.Timeout(settings.api_timeout_seconds))`, 3 s for all phases (httpx’s default would be 5 s)
  - `httpx.TimeoutException` → warning log (no URL) + `504` “Weather provider took too long to respond” (`from None`) — verified with a mocked timeout
- [x] Decide on the response shape → **custom shape** (decided 2026-10-19, built — see below):
  ```
  {
    "location": <resolvedAddress>,
    "units": "metric",
    "current":  { temperature, feels_like, uv_index, conditions, humidity },
    "forecasts": [ { date, high, low, conditions, chance_of_rain } × 3 ]   // today + next 2 days
  }
  ```
  - Units fixed to Celsius (Visual Crossing metric unit group) — keep it simple
  - Request only 3 days from Visual Crossing (date keyword in the URL) — the cached raw response then only ever has 3 days
  - Field names in snake_case, independent of Visual Crossing’s names
- [x] Build the custom response shape (request metric units + 3 days, map Visual Crossing fields to your names) — done 2026-10-19
  - [x] Create `models/` (with `__init__.py`) and a file for the models and the conversion function (`models/json_to_structured_response.py`)
  - [x] Write the nested pydantic models: `Current`, `ForecastDay`, `ResponseShape` (`location`, `units`, `current`, `forecasts`)
    - [x] Nullability decided → **tolerant** (2026-10-19): every measured field is `X | None`; only `date` (`datetime.date`) and `location` are strict
    - [x] `forecasts` limited to 3 items with `Field(min_length=3, max_length=3)` — the conversion function picks the days, the model checks the count
  - [x] Write the conversion function `json_to_structured_response(json_response: dict[str, Any]) -> ResponseShape` (done 2026-10-19; ruff, ruff format, pyrefly clean; 9 sample cases checked)
    - Takes the parsed **dict** (`response.json()` or `json.loads(cached)`), so it works for both the cache-miss and cache-hit paths
    - Plain `def`, not `async` — it doesn't wait on any I/O
    - `current` comes from `currentConditions` (not `days[0]`, which holds whole-day values)
    - Fields read with `.get()`; missing objects fall back with `or {}` (`currentConditions`) and `or []` (`days`)
    - `days[:3]` drops extra days; fewer than 3 still fails
    - `model_validate({...})` for models with strict fields (`ForecastDay`, `ResponseShape`) — every bad-data case raises `ValidationError` (→ 502), and Pyrefly doesn’t flag the possibly-`None` values
  - [x] Update the route: `/next2days` in the URL path (was `/next3days`), `unitGroup=metric` and `include=days,current` in `params`, calls `json_to_structured_response`, returns `ResponseShape`
    - `include=current` alone drops `days` — list both; leaving out `hours` also shrinks the cached response
  - [x] Check with one real request (2026-10-19, `queryCost: 1`): `200`, 3 forecast days, Celsius values, every field filled in, raw response ~5.6 KB (was ~170 KB with `hours`)
    - Decided: request `next2days` (today + 2), `days[:3]` stays as a safety net — **not yet confirmed on the real API that it returns 3 days**
  - Facts from the Visual Crossing docs (checked 2026-10-19):
    - Dynamic date keywords go in the path after the location (e.g. `.../timeline/Vancouver/next3days`) and resolve in the **location’s local time** — no `datetime`/timezone code needed
    - `next3days` returns **4** days (today + 3) — confirmed on a real response; `days[:3]` trims it
    - `unitGroup` is a query parameter (`us` default, `uk`, `metric`, `base`) — put it in `params`
    - `days` field names: `datetime`, `tempmax`, `tempmin`, `conditions`, `precipprob` (forecast only), also `temp`, `feelslike`, `uvindex`, `humidity`
    - `currentConditions` fields aren’t documented one by one — confirmed on a real response: `temp`, `feelslike`, `uvindex`, `conditions`, `humidity` (all filled in)
- [x] ~~`GET /weather/{location}/{date1}`~~ — removed on purpose (2026-10-20); the API only serves current + 3-day forecast. `validation/date_string.py` (`DateSpec`) is now unused

## 5. Caching with Redis (diagram steps 1, 2, 5)

- [ ] **Step 1:** check the cache before calling the 3rd-party API
- [ ] **Step 2:** on a cache hit, return the cached data right away
- [ ] **Step 5:** on a cache miss, save the API response with `SET key value EX <ttl>`
- [ ] Design the cache key (the tip suggests the city code). Think about:
  - Normalization: should `Vancouver` and ` vancouver ` hit the same key?
- [ ] Serialize the data to store it (JSON string) and deserialize it on read
- [x] Decided: cache the **raw** Visual Crossing response and build the custom shape on every read — the shape can change without stale cache entries
- [ ] Cache-miss order (decided 2026-10-19): fetch → build the shape (validate) → **only on success** save the raw response → return the shape. On a `ValidationError`, nothing is cached
- [ ] Cache hit that fails validation (e.g. the models changed after the entry was saved) → delete that cache entry and refetch (decided 2026-10-19)
  - Refetch only **once**: if the fresh response also fails, return the error (§6) instead of trying again
- [ ] Decide what happens if Redis is down: return an error, or skip the cache and call the API directly?
- [ ] Shared `redis.asyncio` client + shared `httpx.AsyncClient`, created in the `lifespan` and closed with `aclose()`
- [ ] *(Nice to have)* Show whether the data came from the cache, e.g. an `X-Cache: HIT/MISS` header

## 6. Error handling

- [x] `raise_for_status()` is called before `.json()`
- [x] `print()` removed (use `logging` going forward)
- [x] Logging set up (2026-10-19): `basicConfig` + `getLogger("httpx").setLevel(logging.WARNING)` in `main.py`, only `getLogger(__name__)` in modules — httpx’s INFO request log printed the URL with `key=...`; verified the key no longer appears in the output
- [x] Upstream error statuses handled (2026-10-20): catch `httpx.HTTPStatusError` around `raise_for_status()`
  - Visual Crossing `400` whose body contains “No valid locations” → `404` “The system cannot find the location you entered” (`info` log)
  - Any other upstream status (other `400`s = our own bad params, `401` key, `429` quota, `5xx`) → `502` (`warning` log with the upstream status) — the client never learns about our key or quota
  - Facts (real requests, 2026-10-20): VC **guesses** most made-up locations (`Zzqxvbnm Nowhere 99999` → `200`, “Nowhere, Fort Cobb, OK”); only unmatchable input gives `400` “Bad API Request:No valid locations could be determined from the input”. VC’s `404` means a wrong URL structure, not a missing location
  - Gotcha: VC error bodies are **plain text** but labelled `application/json` — read them with `.text`, never `.json()`
  - [x] Upstream body **not logged** for any status (2026-10-20) — it’s outside our control and could echo the key; only the status is logged. Tradeoff: a `400` from our own bad param shows only “returned 400”, so check the body by hand when debugging
- [x] 3rd-party API down or timing out (2026-10-20)
  - [x] Timeout → `504` (see §4)
  - [x] Can’t connect (`httpx.ConnectError`) → `502` “Connection to API failed”
- [x] Bad or missing API key → `502` without leaking the key (2026-10-20). Every `raise HTTPException(...)` inside an `except` uses `from None`; logs never use `str(exc)`, `exc.request.url` or `logger.exception` for httpx errors — those contain `key=...`
- [ ] Don’t cache error responses
- [x] Upstream data that fails validation → `502` “Weather provider returned incomplete data” (2026-10-20)
  - Catches `pydantic.ValidationError` specifically; `logger.exception` logs the full error server-side (safe: it holds no URL)

## 7. Rate limiting

Goal: protect the Visual Crossing quota and keep one caller from using more than their share.

- [ ] Identify callers by **IP address** (no accounts; cookies are client-controlled, so they can’t be used for enforcement) **← do first: the other items depend on it**
  - Known limit: callers on a shared network share one limit — accepted, because this project’s users are unlikely to share IPs
  - Known limit: one person with many IPs can get around it — accepted, with the global cap below as a backstop
  - Open: where the real client IP comes from behind a proxy (`X-Forwarded-For` is client-controlled unless a trusted proxy sets it)
- [ ] **Per-IP limit:** count requests per caller in a time window (counting vs. timestamps still open)
- [ ] **Global cap** on calls to Visual Crossing — counts only cache misses, since cache hits don’t use quota
  - Open: what users get when the cap is reached, and when it resets
- [ ] Open: the actual numbers (per-IP limit, window, global cap)
- [ ] Open: should cache hits count toward the per-IP limit?
- [ ] Refuse requests over a limit with `429 Too Many Requests` (optionally a `Retry-After` header)
- [ ] Research when you get here: `slowapi`, or build it yourself with Redis (`INCR` + `EXPIRE`)

## 8. Testing and polish

- [ ] Tests with pytest (already in dev dependencies) — mock the 3rd-party API so the tests don’t use up your quota (no `tests/` folder yet)
- [ ] Tests that run the lifespan (`with TestClient(app)`) need `monkeypatch.setenv("WEATHER_API_KEY", ...)` + `get_settings.cache_clear()` — overrides don’t apply to the lifespan
- [ ] Test a cache hit and a cache miss
- [ ] Test the error paths — the 9 mocked cases in the scratchpad check (`check_errors.py`) are a good starting list: good, timeout, connect error, 400 no-location, 400 other, 401, 429, 500, 200 bad data
- [ ] Remove dead code: the unused `Date` alias in `routes/location.py`, and `validation/` (`DateSpec`) now that route 2 is gone
- [ ] Run `uvx ruff format .` (2 files would be reformatted as of 2026-10-20)
- [ ] README: how to set up the environment, start Redis, and run the app (currently empty)
- [ ] Update the placeholder `description` in `pyproject.toml`

---

## 9. Before finishing

- [ ] **Rotate the Visual Crossing API key** — it was printed in a traceback on 2026-10-20 (deferred to the end of the project). After rotating: update `.env`, then open a new terminal (see §3)

---

**Suggested order** (updated 2026-10-20): §4 done → error handling (6) done → **Redis caching (5) next** → rate limiting (7) → tests (8) → before finishing (9).
