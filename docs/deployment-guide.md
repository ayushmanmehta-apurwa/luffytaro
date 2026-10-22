# Deployment guide

**Status:** the Docker files, `render.yaml` and the Nebius commands were written from the providers' documented formats but could not be run where this
project was built (no Docker, no Render/Vercel/Nebius account). Treat them as a tested-on-paper starting point, run them yourself, and do not say anything is
deployed until you have seen it working. The application itself was tested locally in a real browser, including the Vercel-style two-address setup.

Every setting is explained in `ENV_VARIABLES.md`.

## What a public demo needs
- It must stay reachable, free and unrestricted for the whole judging period (check the hackathon rules for the dates).
- Spending limits: keep `DAILY_TOKEN_BUDGET` and `RATE_LIMIT_PER_MINUTE` set, and set a spend limit in the Nebius console if it offers one.
- Never put a real key in the repository. Use the host's environment variables. Rotate the key after judging.

## Option A: everything on Render (simplest, one address)
The root `Dockerfile` builds the website and the API into one container, so there is nothing to connect.
1. Push the project to GitHub. The **repository root must contain `Dockerfile`, `backend/` and `frontend/`**.
2. Render: **New + > Blueprint** and pick the repo (it reads `render.yaml`), or **New + > Web Service** and set it by hand:
   - Language **Docker**, Dockerfile Path `./Dockerfile`
   - **Root Directory: empty** (setting it to `backend` makes Render run `npm install` in the wrong folder and the build fails)
   - Instance type **Free**, Health Check Path `/health`
3. Add the environment variables from `ENV_VARIABLES.md` (paste-ready block).
4. Open `https://YOUR-SERVICE.onrender.com/health`. Expect `{"status":"ok","mode":"live","database":"ok"}` (`demo` if the key or a model ID is missing).

Free-plan behaviour to plan for: the service sleeps after about 15 idle minutes and the first request afterwards takes about a minute (the site shows a friendly
"waking up" banner and retries by itself); the disk is temporary, which is fine because each visitor's sandbox is recreated automatically; **do not** create Render's
free database, because it expires after 30 days. A free uptime pinger on `/health` keeps it awake.

A service that you (or anyone with access) **suspended** answers every request with "This service has been suspended by its owner". Use **Resume Service**.

## Option B: website on Vercel, API on Render
1. Deploy the API on Render as in Option A. Note its address, for example `https://civicclosure.onrender.com`.
2. Vercel: **Add New > Project**, import the repo, then set **Root Directory `frontend`**, Framework **Vite**, Build `npm run build`, Output `dist`.
   Add the environment variable `VITE_API_BASE=https://civicclosure.onrender.com` (no trailing `/`). Deploy. `frontend/vercel.json` makes page refreshes work.
3. Copy your Vercel address (for example `https://civic-closure.vercel.app`) and set on Render: `CORS_ORIGINS=https://civic-closure.vercel.app`. Save and wait for the redeploy.
   To also allow Vercel preview deployments, add `CORS_ORIGIN_REGEX=https://civic-closure(-[a-z0-9-]+)?\.vercel\.app`.
4. Run the checker: `cd frontend; $env:SITE_URL="https://civic-closure.vercel.app"; npm run check:deploy`. If it fails it names the cause.
5. After **any** change to `VITE_API_BASE`, redeploy on Vercel (the value is baked in at build time).

| Symptom | Cause and fix |
|---|---|
| Console: "blocked by CORS policy" | `CORS_ORIGINS` does not exactly match the Vercel address (`https://`, same spelling). Fix on Render and wait for the redeploy. |
| Browser shows "This service has been suspended" or a 503 | The Render service is suspended or crashed. Resume it, check **Logs**. |
| Requests go to the Vercel address instead of Render | `VITE_API_BASE` missing or not redeployed. |
| Refreshing `/admin` gives a Vercel 404 | `frontend/vercel.json` is not in the repository. |
| Build log: `npm install` ... `backend/package.json` not found | Render's Root Directory is `backend` or the language is not Docker (see Option A step 2). |

## Option C: Google Cloud Run (always-free allowance, needs a billing account and card)
Build from the root `Dockerfile` (`gcloud run deploy --source .`), set the same environment variables, set a budget alert, and set `TRUST_PROXY_HOPS=1`.

## Nebius Serverless Job (hotspots)
Follow `../jobs/hotspots/README.md`: build and push the image, create the job (first from the console), pass `API_BASE`, `EXPORT_TOKEN`, `NEBIUS_API_KEY`, `REASON_MODEL`,
check `nebius ai job logs`, and confirm the Admin screen shows hotspots from "the Nebius Serverless Job". Screenshot the finished job and its logs as evidence.

## Optional: API as a Nebius Serverless Endpoint
Possible with `nebius ai endpoint create` and a container port; not attempted or verified here. Keep Option A or B as the dependable path.

## Security settings (all in `ENV_VARIABLES.md`)
`TRUST_PROXY_HOPS` (per-visitor rate limit behind a proxy), `DISABLE_DOCS`, `CSP_MODE` (starts as report-only so it can never break the site; check the browser console
then switch to `enforce`), `MAX_IMAGE_PIXELS`, `WORKSPACE_TTL_DAYS` (deletes old demo sandboxes).
Honest limits: roles are a demo switch (anyone can send `X-Role: admin` inside their own sandbox), and a workspace id works like a password for that sandbox. Do not store
real personal data on the public demo. Check your headers at https://securityheaders.com or in the browser (F12, Network, click the page, Response Headers).

## Before you share the link
- [ ] Open the site in a private window on a phone and complete one report and one closure.
- [ ] `npm run check:deploy` says OK, and the banner shows the mode you intend (live or demo).
- [ ] No secrets in the Git history (`git log -p | findstr /i api_key`).
- [ ] The README states what was and was not verified.
