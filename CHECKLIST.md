# Weather API Cache — Project Checklist

Based on the project requirements and architecture diagram:

```
Client ⇄ Weather API ──1. check cache──▶ Redis
                     ◀─2. cache response─
                     ──5. save cached results──▶ Redis
         Weather API ──3. request──▶ 3rd-party weather service
                     ◀─4. response───
```

Status as of 2026-10-18. Items marked *(partial)* are started but not finished.

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

## 4. Fetch from the 3rd-party API (diagram steps 3–4)

- [ ] *(partial)* `GET /{location}` exists, but it hasn’t worked against the real API yet **← next**
- [ ] Check how Visual Crossing expects the location to be sent — the route currently sends `.../timeline/?location=Vancouver&key=...`; compare that with the Timeline API URL format in their docs
- [ ] Set a timeout on the HTTP call
- [ ] Decide on the response shape: return the raw Visual Crossing JSON, or a trimmed and cleaned response of your own?
- [ ] *(partial)* `GET /{location}/{date1}` has date validation (`validation/date_string.py`), but the handler is still a `pass` placeholder (returns `200` with `null`)

## 5. Caching with Redis (diagram steps 1, 2, 5)

- [ ] **Step 1:** check the cache before calling the 3rd-party API
- [ ] **Step 2:** on a cache hit, return the cached data right away
- [ ] **Step 5:** on a cache miss, save the API response with `SET key value EX <ttl>`
- [ ] Design the cache key (the tip suggests the city code). Think about:
  - Normalization: should `Vancouver` and ` vancouver ` hit the same key?
  - Including the date in the key for the `/{location}/{date}` route
- [ ] Serialize the data to store it (JSON string) and deserialize it on read
- [ ] Decide what happens if Redis is down: return an error, or skip the cache and call the API directly?
- [ ] Shared `redis.asyncio` client + shared `httpx.AsyncClient`, created in the `lifespan` and closed with `aclose()`
- [ ] *(Nice to have)* Show whether the data came from the cache, e.g. an `X-Cache: HIT/MISS` header

## 6. Error handling

- [x] `raise_for_status()` is called before `.json()`
- [x] `print()` removed (use `logging` going forward)
- [ ] Upstream errors (e.g. a bad location) currently reach your client as a **500** — catch `httpx.HTTPStatusError` and return a clear 4xx or 502
- [ ] 3rd-party API down or timing out → 502/503/504 with a helpful message
- [ ] Bad or missing API key → handled without leaking the key. Note: the `HTTPStatusError` message includes the full URL, **including `key=...`**, so the key ends up in tracebacks and logs
- [ ] Don’t cache error responses

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
- [ ] Test the error paths (invalid location, upstream failure)
- [ ] Remove the commented-out code and the unused `Date` alias in `routes/location.py`
- [ ] README: how to set up the environment, start Redis, and run the app (currently empty)
- [ ] Update the placeholder `description` in `pyproject.toml`

---

**Suggested order:** section 4 so one real request works end to end → Redis caching (5) → error handling (6) → rate limiting (7) → tests (8).
