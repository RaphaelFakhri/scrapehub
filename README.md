# scrapehub

> Async, headless web-scraping framework for **sanctioned** sources — BeautifulSoup + Playwright, rotating proxies/UAs, polite rate-limiting + retry/backoff, bounded-concurrency batching, structured logging, selector resilience, and pydantic-validated CSV/JSON output.

[![ci](https://github.com/RaphaelFakhri/scrapehub/actions/workflows/ci.yml/badge.svg)](https://github.com/RaphaelFakhri/scrapehub/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![ruff](https://img.shields.io/badge/lint-ruff-orange)
![license](https://img.shields.io/badge/license-MIT-green)

## Legal & Ethics

scrapehub **only** targets sources that explicitly permit scraping or offer public APIs:

- `books.toscrape.com` — a sandbox built for scraping practice (static HTML).
- `quotes.toscrape.com` — sandbox with static, **`/js`** (JS-rendered) and **`/scroll`** (infinite-scroll/AJAX) variants.
- **Wikipedia REST API** (`/api/rest_v1/page/summary`).
- **Hacker News Firebase API** (`hacker-news.firebaseio.com`).

It respects robots/ToS, touches no authentication walls, and ships **no proxies**.
The anti-bot handling is lightweight realism (UA/header/proxy rotation + pacing) — **not** a CAPTCHA-solver or evasion toolkit, and must not be repurposed against non-sanctioned sites.

## Skills demonstrated

| Capability (job bullet) | Where it's proven (file → symbol) |
| --- | --- |
| Python web scraping with BeautifulSoup | `src/scrapehub/scrapers/books_static.py` → `parse_books_html` |
| Playwright headless rendering | `src/scrapehub/core/browser.py` → `BrowserManager.render` |
| JS-rendered content | `src/scrapehub/scrapers/quotes_js.py` → `QuotesJsScraper` |
| AJAX + infinite scroll | `src/scrapehub/core/browser.py` → `BrowserManager.scroll_collect`; `src/scrapehub/scrapers/quotes_scroll.py` → `QuotesScrollScraper.fetch_via_api` |
| APIs via rotating proxies + user-agents | `src/scrapehub/core/http_client.py` → `AsyncHttpClient.request` |
| Rotating proxy pool with health/cooldown | `src/scrapehub/core/proxy_pool.py` → `ProxyPool` |
| User-agent + realistic header rotation | `src/scrapehub/core/user_agents.py` → `UserAgentRotator` |
| Polite per-host rate limiting | `src/scrapehub/core/rate_limiter.py` → `RateLimiter` (token bucket) |
| Retry/backoff for transient failures | `src/scrapehub/core/retry.py` → `make_retrying`, `is_retryable_exception` |
| Scale via async batching + bounded concurrency | `src/scrapehub/core/batching.py` → `gather_bounded`, `process_in_batches` |
| Failure monitoring | `src/scrapehub/core/metrics.py` → `Metrics` |
| Structured logging (request-id, per-source) | `src/scrapehub/logging_setup.py` → `configure_logging`, `bind_run_context` |
| Resilience to selector changes | `src/scrapehub/selectors/registry.py` → `SelectorSet`, `select_text` (see `tests/test_selectors_resilience.py`) |
| Cleaning / normalization | `src/scrapehub/pipeline/clean.py` → `parse_currency`, `normalize_whitespace`, `dedupe_tags` |
| Validation + quarantine (pydantic v2) | `src/scrapehub/pipeline/validate.py` → `validate_records` |
| CSV + JSON export (schema-driven) | `src/scrapehub/pipeline/export.py` → `export_records` |
| Wikipedia REST API client | `src/scrapehub/scrapers/wikipedia_api.py` → `WikipediaApiScraper` |
| Hacker News Firebase API client | `src/scrapehub/scrapers/hackernews_api.py` → `HackerNewsApiScraper` |
| Typer CLI | `src/scrapehub/cli.py` → `app` |
| Dockerized + offline pytest + CI | `Dockerfile`, `tests/`, `.github/workflows/ci.yml` |

## Architecture

```
                         ┌────────────────────┐
                         │       cli.py        │  Typer: choose source/mode/out
                         └─────────┬──────────┘
                                   │
            ┌──────────────────────┼───────────────────────┐
            ▼                      ▼                        ▼
   ┌─────────────────┐   ┌──────────────────┐    ┌────────────────────┐
   │  core (infra)   │   │     scrapers      │    │   pipeline          │
   │  http_client    │◀──│  base.BaseScraper │───▶│  clean → validate   │
   │  browser        │   │  books_static     │    │  → export (CSV/JSON)│
   │  proxy_pool     │   │  quotes_js/scroll │    └────────────────────┘
   │  user_agents    │   │  wikipedia_api    │
   │  rate_limiter   │   │  hackernews_api   │          ▲
   │  retry / batch  │   └─────────┬─────────┘          │
   │  metrics        │             │     models (pydantic v2 schemas)
   └─────────────────┘             └──────────── selectors.registry (fallbacks)
```

Every scraper follows the same lifecycle defined in `scrapers/base.py`:
**fetch → parse → clean → validate → export**, with metrics + structured logs threaded through.

- **core/** — reusable infrastructure (clients, rotation, pacing, retry, batching, metrics).
- **scrapers/** — one module per sanctioned source, all subclassing `BaseScraper`.
- **models/** — `Book`, `Quote`, `Article`, `Story` pydantic schemas.
- **pipeline/** — normalization, validation/quarantine, CSV+JSON writers.
- **selectors/** — versioned CSS selector registry with ordered fallbacks.

## Quickstart

```bash
pip install -e ".[dev]"
python -m playwright install chromium   # only needed for the /js browser path
cp .env.example .env                     # optional: configure proxies/limits
```

## CLI usage

```bash
# Static BeautifulSoup catalogue (2 pages) -> data/books.csv + .json
scrapehub books --pages 2 --out data/books

# Static quotes
scrapehub quotes-static --pages 3

# JS-rendered quotes (needs Chromium)
scrapehub quotes-js --pages 2

# Infinite scroll via the AJAX JSON endpoint (default) or a real browser
scrapehub quotes-scroll --api --max-pages 10
scrapehub quotes-scroll --browser --max-pages 20

# Wikipedia REST summaries (rotating proxies + batched concurrency)
scrapehub wikipedia "Web scraping" "Asyncio" --concurrency 8 --batch 20

# Hacker News top stories
scrapehub hackernews --limit 30 --batch 20 --out data/hn
```

Equivalent module form: `python -m scrapehub <command> ...`. Runnable scripts live in `examples/`.

## Configuration

All config is environment-driven (prefix `SCRAPEHUB_`) via `pydantic-settings`; see `.env.example`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `SCRAPEHUB_PROXIES` | _(empty)_ | Comma-separated proxy URLs; rotated + health-checked. Supply your own. |
| `SCRAPEHUB_CONCURRENCY` | `8` | Max in-flight requests (bounded concurrency). |
| `SCRAPEHUB_BATCH_SIZE` | `20` | Chunk size for large id/url lists. |
| `SCRAPEHUB_RATE_LIMIT` | `4.0` | Per-host requests/second (token bucket). |
| `SCRAPEHUB_RATE_BURST` | `8` | Token-bucket burst capacity. |
| `SCRAPEHUB_TIMEOUT` | `30.0` | HTTP/browser timeout (s). |
| `SCRAPEHUB_MAX_RETRIES` | `4` | Retry attempts for transient errors. |
| `SCRAPEHUB_OUTPUT_DIR` | `data` | Where CSV/JSON land. |
| `SCRAPEHUB_LOG_FORMAT` | `console` | `json` or `console`. |
| `SCRAPEHUB_LOG_LEVEL` | `INFO` | Standard log level. |

**No secrets are committed** — proxies/keys come only from the environment.

## Output schemas

`Book` (price/rating/availability normalized), `Quote` (text/author/de-duped tags),
`Article` (Wikipedia summary), `Story` (HN item). Each run writes a `.csv` (schema-ordered
columns) and a pretty `.json` array.

```json
[
  { "title": "A Light in the Attic", "price": 51.77, "currency": "£",
    "rating": 3, "availability": "In stock", "in_stock": true,
    "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html" }
]
```

## Docker

```bash
docker compose up --build          # runs the default HN scrape into ./data
docker compose --profile proxy up  # also start a local mitmproxy mock
# or:
docker build -t scrapehub .
docker run --rm -v "$PWD/data:/data" scrapehub hackernews --limit 10 --out /data/hn
```

The runtime image is based on the official Playwright Python image so Chromium and
all system libraries are present for headless `/js` and `/scroll` runs.

## Testing

```bash
pytest                 # fully offline: httpx mocked via respx, Playwright stubbed
coverage run -m pytest && coverage report
```

- The JS scraper test injects a fake `BrowserManager` (no Chromium launch).
- The infinite-scroll test mocks the `/api/quotes` AJAX endpoint to exercise pagination.
- HTML/JSON fixtures live in `tests/fixtures/`.

> Offline mocks intentionally do not exercise live TLS/redirects/429s. Treat any
> live runs against the sanctioned sites as opt-in smoke tests, never default CI.

## Development

```bash
ruff check . && ruff format --check .   # lint + format
make dev test                           # install dev deps + run suite
```

`src/` layout, full type hints, docstrings throughout. See `ruff.toml` and `pyproject.toml`.

## Roadmap / limitations

- Live integration smoke tests are intentionally out of default CI.
- Playwright/Chromium versions are pinned for reproducibility; drift between local/CI/Docker can cause flaky headless runs.
- Anti-bot handling is deliberately minimal and source-respectful.
- `toscrape.com` markup / API shapes can drift; the selector registry + schema validation mitigate but cannot eliminate this.

## License

MIT — see [LICENSE](LICENSE).
