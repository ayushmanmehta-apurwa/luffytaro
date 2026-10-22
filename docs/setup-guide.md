# Setup guide and troubleshooting

The full step-by-step instructions (Windows PowerShell with Linux/macOS equivalents) are in the top-level `README.md`.

## Checklist
1. Python 3.11+ and Node 20+ installed (`python --version`, `node --version`).
2. `python -m venv .venv` then activate it, then `pip install -r backend\requirements.txt`.
3. `cd frontend; npm install`.
4. Optional: `Copy-Item .env.example backend\.env` and fill in Nebius values.
5. Backend: `cd backend; uvicorn app.main:app --reload --port 8000`.
6. Frontend: `cd frontend; npm run dev`, open http://localhost:5173.

## Troubleshooting
| Problem | Fix |
|---|---|
| `running scripts is disabled` when activating the venv | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again |
| `python` not found | Reinstall Python and tick "Add python.exe to PATH", or try `py -m venv .venv` |
| `Request failed (500)` on the very first report or page load (Windows) | Windows has no timezone database. Run `pip install tzdata` (it is now in `requirements.txt`), restart the backend. The newest code also falls back safely. For ANY 500, the real reason is the last red lines in the backend terminal. |
| `ECONNREFUSED 127.0.0.1:8000` in the frontend terminal | The backend is not running. Start it in its own terminal. |
| Red banner "Cannot reach the API" | The backend is not running on port 8000. Start it (step 5). |
| Banner says Demo mode but you set a key | The key and **both** `FAST_MODEL` and `REASON_MODEL` must be set. Restart the backend after editing `.env`. |
| `python smoke_test.py` fails with 404 or "model not found" | The model ID is wrong. Copy it exactly from the Token Factory model list. |
| Live mode: tickets always go to the human queue | The model call is failing or returning invalid JSON. Look at the `error` text in the ticket's decision trail and run `smoke_test.py`. |
| Photo upload rejected | Use JPEG, PNG or WebP under 5 MB (change `MAX_UPLOAD_BYTES`). |
| Closure says `needs_evidence` for every photo | Photos need a camera capture time (EXIF). Messaging apps remove it. Use the phone camera, or the app's sample evidence. |
| Sample evidence is missing in the Department screen | It only appears for tickets created with the sample report buttons in this browser. |
| Something odd after changing code | Use Admin > Reset demo workspace, or delete `backend/civicclosure.db` while the backend is stopped. |
| Red banner "Cannot reach the server" on a deployed site | It may be waking up (the page retries by itself for about a minute). If it stays, run `npm run check:deploy` from `frontend` and read the diagnosis. |
| `429 Too many requests` | The per-IP limit was hit. Wait a minute or raise `RATE_LIMIT_PER_MINUTE`. |
