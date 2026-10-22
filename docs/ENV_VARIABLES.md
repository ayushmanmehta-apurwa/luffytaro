# Environment variables

Set these on your backend host (Render: service > **Environment**), or in `backend/.env` when running locally.
Never put real keys in Git. The frontend has exactly one variable (`VITE_API_BASE`, see the bottom).

## Paste-ready block for Render ("Add from .env")
Replace the four `PASTE_...` values. No quotes, no spaces around `=`, no comment text.
```
NEBIUS_API_KEY=PASTE_YOUR_NEBIUS_KEY
FAST_MODEL=PASTE_EXACT_NEMOTRON_OMNI_MODEL_ID
REASON_MODEL=PASTE_EXACT_NEMOTRON_SUPER_MODEL_ID
EXPORT_TOKEN=PASTE_A_LONG_RANDOM_TEXT
DAILY_TOKEN_BUDGET=300000
RATE_LIMIT_PER_MINUTE=40
TRUST_PROXY_HOPS=1
DISABLE_DOCS=true
CSP_MODE=report-only
```
Add this line only when the website is hosted separately (for example on Vercel):
```
CORS_ORIGINS=https://your-site.vercel.app
```
No key yet? Leave out the first three lines: the app then runs in clearly labelled **Demo Mode**.

## Reference
| Variable | Default | Meaning |
|---|---|---|
| `NEBIUS_API_KEY` | empty | Nebius Token Factory key. Empty = Demo Mode. |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1/` | Only change if Nebius tells you to. |
| `FAST_MODEL` | empty | Exact ID of NVIDIA Nemotron 3 Nano Omni (intake, duplicates, visual checks). Copy it from the Token Factory model list. |
| `VISION_MODEL` | `FAST_MODEL` | Optional separate vision model. |
| `REASON_MODEL` | empty | Exact ID of NVIDIA Nemotron 3 Super (hard routing, hotspots). |
| `EXPORT_TOKEN` | empty | Secret for `/api/export` and `/api/hotspots` (the Nebius job). Empty disables those endpoints. |
| `DATABASE_URL` | SQLite file | Leave empty on a free host. For PostgreSQL: `postgresql+psycopg2://user:pass@host:5432/db`. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Website addresses allowed to call the API. Exact match, `https://`, no trailing `/`, comma-separated. A trailing `/` is removed automatically. |
| `CORS_ORIGIN_REGEX` | empty | Optional pattern for extra addresses, e.g. Vercel previews: `https://your-site(-[a-z0-9-]+)?\.vercel\.app` |
| `TRUST_PROXY_HOPS` | `0` (Docker image: `1`) | Reverse proxies in front of the app. Needed so the rate limit works per visitor. |
| `DISABLE_DOCS` | off | `true` hides `/docs`, `/redoc`, `/openapi.json`. |
| `CSP_MODE` | `report-only` | Browser security policy: `report-only`, `enforce` or `off`. |
| `CSP_EXTRA_CONNECT` | empty | Extra API origin for the policy if the backend itself serves a page that calls another origin. |
| `MAX_UPLOAD_BYTES` | `5000000` | Largest photo accepted. |
| `MAX_IMAGE_PIXELS` | `25000000` | Largest photo dimensions accepted. |
| `RATE_LIMIT_PER_MINUTE` | `40` | Write requests per visitor per minute. |
| `DAILY_TOKEN_BUDGET` | `300000` | Daily cap on model tokens for the whole app. |
| `LLM_TIMEOUT_S`, `LLM_MAX_RETRIES` | `60`, `2` | Model call timeout and retry limit. |
| `SEED_NEW_WORKSPACES` | `true` | Fill each new visitor sandbox with labelled sample tickets. |
| `WORKSPACE_TTL_DAYS` | `14` | Delete demo sandboxes untouched this long (`0` = never). |
| `FORCE_DEMO_MODE` | off | `true` ignores the key and runs Demo Mode (used by the tests). |
| `PORT` | set by the host | Do not set it on Render. |

## Frontend (Vercel / any static host)
| Variable | Meaning |
|---|---|
| `VITE_API_BASE` | Address of the backend, e.g. `https://civicclosure.onrender.com`. No trailing `/`. Baked in at build time, so **redeploy after changing it**. Leave unset when the backend serves the website itself. |

## Job (`jobs/hotspots`)
`API_BASE`, `EXPORT_TOKEN`, `WORKSPACE`, `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `REASON_MODEL`. See `jobs/hotspots/README.md`.
