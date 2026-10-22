# CivicClosure: AI-powered campus issue reporting with verified resolution

Students report campus problems with text and a photo. The system structures the report, routes it, merges duplicates and runs the
deadline clock. When a department says "fixed", **the system checks the evidence before it lets the ticket close.**

Built for the Nebius x NVIDIA Global AI Hackathon on **Nebius Token Factory** with **NVIDIA Nemotron** open models.

## Read this first: what is real and what is not

| | Status |
|---|---|
| **Demo Mode** (no API key) | Works offline and free. Uses simple keyword rules and image statistics. It is **not AI** and **not NVIDIA model output**. The app, every API result and the evaluation screen label it as such. |
| **Live Mode** (Nebius key + model IDs) | The code paths exist and are tested **against a stand-in client only**. They have **not** been run against the real Nebius API or real Nemotron models by the author. Run `python smoke_test.py` with your own key to check your account before relying on it. |
| Tests | 103 backend tests pass, the frontend passes ESLint, and a 9-step **real-browser test** (headless Chrome clicking through the whole site, including a phone-sized screen and a Vercel-style setup where the website and API are on different addresses) passes with no console errors. See "Run the tests". |
| Evaluation | `eval/results/metrics.json` was produced by a real run in **Demo Mode** on **synthetic** data. It measures the rules, not NVIDIA models. |
| Not verified | Real Nemotron output quality and latency, Hindi/Hinglish voice (not implemented), the Docker build, PostgreSQL, deployment on Render/Vercel/Nebius, and the Nebius job on Nebius itself. Everything else above was run. |

Also be aware: photo capture times (EXIF) and visual analysis are **evidence checks, not proof**. A determined person can edit metadata or
stage a photo. The audit log is **tamper-evident, not tamper-proof**. The role switcher is a **demo convenience, not authentication**.

## What it does

1. **Intake**: text + photo (+ campus location) become validated structured data (issue, urgency, place).
2. **Routing**: known issues map to departments by rules (`backend/app/domain/campus.yaml`). Unsure cases go to a **human review queue**.
3. **Duplicates**: reports of the same problem in the same place merge into one ticket with a report count.
4. **SLA**: each department has deadlines by urgency. Overdue tickets escalate. A clearly labelled **demo clock** lets you show this quickly.
5. **Verification gate**: a closure claim is checked for a reused photo, capture time, whether the photo shows the fixed state, and whether it is the same place. Verdicts: **Verified**, **Needs evidence**, **Contradicted**. Only the gate or a human reviewer can close a ticket.
6. **Audit log**: every event is in a SHA-256 hash chain with an integrity check.
7. **Hotspots**: recurring problems become one root-cause work order (in-app, or as a Dockerised Nebius Serverless Job).
8. **Privacy**: reporters can delete their photos and text. Report text is treated as data, never as instructions.

Problems that cannot be seen in a photo (Wi-Fi, furniture, pests) close only after the reporter confirms, or a human reviewer decides.

## Quick start on Windows (PowerShell)

### 1. Install the tools (once)
- **Python 3.11 or newer**: https://www.python.org/downloads/ (tick "Add python.exe to PATH" in the installer)
- **Node.js 20 or newer (LTS)**: https://nodejs.org/
- **VS Code**: https://code.visualstudio.com/

Check them in PowerShell: `python --version` and `node --version`.

### 2. Extract and open
Right-click `CivicClosure_Complete_Project.zip`, choose **Extract All**, then open the extracted folder in VS Code
(**File > Open Folder**). Open a terminal with **Terminal > New Terminal** (it should be PowerShell).

### 3. Install the backend
```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass     # only if activation is blocked
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```
If the website later shows `Request failed (500)`, run `pip install tzdata` and restart the backend (Windows has no timezone database). The real cause of any 500 is printed in the backend terminal.

### 4. Install the frontend
```powershell
cd frontend
npm install
cd ..
```

### 5. Configure (optional: skip this to stay in Demo Mode)
```powershell
Copy-Item .env.example backend\.env
notepad backend\.env
```
To use the real models, fill in `NEBIUS_API_KEY`, `FAST_MODEL` and `REASON_MODEL` (copy the exact IDs from the Nebius Token Factory model list; never guess them), then check them:
```powershell
cd backend
python smoke_test.py
cd ..
```
Never commit `.env`. It is already in `.gitignore`.

### 6. Initialise the database
The API creates the tables automatically on start. To do it by hand: `cd backend; python init_db.py; cd ..`

### 7. Start the backend (terminal 1)
```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```
Check http://127.0.0.1:8000/health shows `{"status":"ok","mode":"demo","database":"ok"}` (`"mode":"live"` once your Nebius settings are in).

### 8. Start the frontend (terminal 2: **Terminal > New Terminal**)
```powershell
cd frontend
npm run dev
```

### 9. Open the website
Go to **http://localhost:5173**. A yellow banner says **Demo mode** until live AI is configured.

### Linux / macOS
```bash
bash scripts/setup.sh                      # venv + dependencies + database (creates backend/.env from .env.example)
. .venv/bin/activate && cd backend && uvicorn app.main:app --reload --port 8000     # terminal 1
cd frontend && npm run dev                                                          # terminal 2
```
(Windows users can run `scripts\setup.ps1` for the same one-time setup.)

### One-process mode (optional)
`cd frontend; npm run build` and then start only the backend: it serves the built site at http://127.0.0.1:8000 .

## Try it in two minutes
1. Landing page: click the evidence options in the walkthrough (a scripted explanation, not a model call).
2. **Report an Issue**: click **Broken stair light** under "Try a sample report" and **Submit complaint**. You get a complaint ID, the department, the deadline and a decision trail.
3. Switch the role (sidebar) to **Department**. Open your ticket and pick **Reused original photo** under sample evidence, then **Claim resolution**: **Contradicted**. Try again with **Genuine repair photo**: **Verified**, and the ticket closes. Try **Screenshot** for **Needs evidence**.
4. Switch to **Admin**: statistics, human review queue, hotspots (press *Analyse recurring problems*), the audit viewer, the evaluation results and the **demo clock**.

Sample photos are **synthetic illustrations** drawn by the app. Sample evidence only matches tickets you created with the sample report buttons.
Every new browser gets a private workspace pre-filled with clearly labelled **Sample data** tickets.

## Run the tests
Backend (103 tests):
```powershell
cd backend
pytest -q
```
What is covered: state transitions, unauthorised-closure prevention, duplicate detection, verification verdicts (including synthetic scene photos), SLA and the demo clock,
audit-chain tampering and privacy deletion, API validation and role checks, workspace isolation, job-endpoint protection, prompt-injection handling, security headers,
CORS, rate limiting behind a proxy, parallel first requests from a new visitor, old-sandbox cleanup, and the live-mode code paths with a stand-in client.

Frontend lint:
```powershell
cd frontend
npm run lint
```

Browser test (needs Google Chrome or Edge; it clicks through every screen and fails on any console error or failed request):
```powershell
cd frontend
npm run build
# start the backend in another window (cd backend; uvicorn app.main:app --port 8000), then:
$env:CHROME_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"   # only if Chrome is not found automatically
npm run e2e
```
Add `$env:E2E_SHOTS = "1"` to save screenshots into `frontend/e2e/screenshots`.

## Check a deployed site (Vercel + Render)
```powershell
cd frontend
$env:SITE_URL = "https://your-site.vercel.app"
npm run check:deploy
```
It opens your site in Chrome, waits for the backend to answer and tells you the likely cause if it does not: CORS not allowing the site, `VITE_API_BASE` missing, a suspended or sleeping service, or a wrong address.

## Run the evaluation
```powershell
python eval\make_dataset.py        # synthetic labelled reports (offline templates; add --live to have the model write them)
python eval\run_eval.py            # writes eval\results\metrics.json, shown in Admin > Evaluation
```
It compares CivicClosure with a baseline that trusts closure claims and a one-prompt routing baseline, and reports fake-closure
acceptance, genuine-repair acceptance, duplicate detection, routing accuracy, human-review rate, latency and tokens. Read the note inside
the results: in Demo Mode it measures rules, not models. Use `--limit 20` for a cheap first live run. Everything is synthetic.

## Nebius Serverless Job (hotspots)
See `jobs/hotspots/README.md`. Run locally first (`python run.py --demo`). Deploying it on Nebius needs your own account and has **not** been verified by the author.

## Deploy
See `docs/deployment-guide.md` (one container on Render, or website on Vercel + API on Render, the Nebius job, keeping the demo alive through judging) and `docs/ENV_VARIABLES.md` (every setting, with a paste-ready block).

## Project layout
```
backend/app/        FastAPI app: main.py (routes), service.py (rules), llm.py (Nebius client), demo_ai.py (Demo Mode),
                    pipeline/ (intake, triage, duplicates, verify, statemachine, audit, sla), domain/campus.yaml
backend/tests/      103 tests       backend/smoke_test.py  checks your Nebius settings
frontend/src/       React + Vite + Tailwind: pages/ components/ services/      frontend/e2e/  browser tests + deployment checker
jobs/hotspots/      Dockerised hotspot job for Nebius Serverless Jobs
eval/               dataset generator, evaluation harness, baselines, results
docs/               architecture, setup guide, deployment guide, demo script
```

## Main API routes
Headers: `X-Workspace` (private sandbox), `X-Role` (reporter | department | admin: demo switch), `X-Reporter`.

| Route | Who | Purpose |
|---|---|---|
| `POST /api/reports` | reporter | submit text + photo, returns ticket + decision trail |
| `GET /api/tickets`, `GET /api/tickets/{id}` | all | list / detail with events and images |
| `POST /api/tickets/{id}/claim_closure` | department | upload after photo, runs the gate |
| `POST /api/tickets/{id}/confirm` | reporter | confirm or dispute a fix |
| `POST /api/tickets/{id}/human_decision` | admin | assign department, approve or reject closure |
| `GET /api/tickets/{id}/audit` | all | event chain + integrity result |
| `GET /api/stats`, `POST /api/admin/...` | admin | dashboard, demo clock, hotspots, reset |
| `GET /api/export`, `POST /api/hotspots` | job (X-Token) | used by the Nebius job |
| `GET /api/config`, `/api/metrics`, `/api/samples` | public | mode, evaluation results, sample images |

## Security and privacy summary
Backend-only API keys; upload size and image-format validation; input validation (Pydantic); CORS limited to configured origins; per-IP
rate limiting; token-protected job endpoints (disabled unless `EXPORT_TOKEN` is set); isolated demo workspaces; privacy deletion; model
output validated before use and never able to change state; report text wrapped and treated as data; daily token budget.
Limits: the in-memory rate limiter is per process; there is no real authentication or user accounts.

## Known limitations
- Live NVIDIA model behaviour (accuracy, latency, JSON output, vision) is untested here. Hindi/Hinglish voice input is **not implemented**; text in Hinglish is supported.
- Demo Mode photo checks only work on the app's own synthetic scenes. They are not computer vision.
- Visual closure checks cover four issue types. The rest need reporter confirmation or a human.
- The duplicate rule merges only within the same campus location and 72 hours; text similarity in Demo Mode is crude (recall is modest).
- Data is stored without encryption at rest; do not enter real personal data in a public demo.

## License
MIT. See `LICENSE`.
