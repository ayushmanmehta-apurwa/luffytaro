# Hotspot job (Nebius Serverless Jobs)

Finds recurring problems (for example 4 water-leak tickets in one hostel) and writes one root-cause work order.

## Run it locally (no Docker, no credits)

```powershell
# terminal 1: start the API with the job endpoints enabled
cd backend
$env:EXPORT_TOKEN = "dev-token"
uvicorn app.main:app --port 8000

# terminal 2: run the job in demo mode (grouping rules, labelled "not AI")
cd jobs/hotspots
pip install -r requirements.txt
$env:API_BASE = "http://localhost:8000"; $env:EXPORT_TOKEN = "dev-token"; $env:WORKSPACE = "demo"
python run.py --demo
```
Linux/macOS: use `export NAME=value` instead of `$env:NAME = "value"`.
Set `NEBIUS_API_KEY` and `REASON_MODEL` and drop `--demo` for the live reasoning-model analysis.

## Build the image
```
docker build -t ghcr.io/YOUR_GITHUB_NAME/civic-hotspots:latest jobs/hotspots
docker push ghcr.io/YOUR_GITHUB_NAME/civic-hotspots:latest    # make the package public
```

## Deploy on Nebius (NOT verified by the author: review against the current Nebius docs first)
Create the first job from the Nebius console (AI Services, then Jobs, then Create job). It fills in the platform,
preset and subnet. Then the CLI form looks like this:
```
nebius ai job create --name civic-hotspots \
  --image ghcr.io/YOUR_GITHUB_NAME/civic-hotspots:latest \
  --platform <cpu-platform> --preset <smallest-preset> --subnet-id <default-subnet-id> \
  --env API_BASE=https://YOUR-API-URL --env WORKSPACE=demo \
  --env NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/ --env REASON_MODEL=<exact-model-id> \
  --env EXPORT_TOKEN=<token> --env NEBIUS_API_KEY=<key>
nebius ai job logs <job-id> --follow
```
Check `nebius ai job create --help` for `--env-secret` and use it for the token and key. The API must be reachable
from the internet. The job needs no GPU. Do not claim the job is deployed until you have seen it finish and
`posted N hotspot(s)` in its logs.
