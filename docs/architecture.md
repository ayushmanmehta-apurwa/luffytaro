# Architecture

```
Browser (React)  --X-Workspace / X-Role / X-Reporter-->  FastAPI (backend/app/main.py)
                                                           |
                                                           v
                                              service.py  (business rules)
   report -> [intake] -> [triage] -> [duplicates] -> ticket + events
   claim  -> [verification gate: code checks, then model checks] -> verdict -> state machine
                                                           |
              llm.py -> Nebius Token Factory (OpenAI-compatible)       demo_ai.py -> Demo Mode rules
                                                           |
                                          SQLAlchemy (SQLite or PostgreSQL)
Nebius Serverless Job (jobs/hotspots) --X-Token--> /api/export, /api/hotspots
```

## Design rules
1. **Code decides, models perceive.** Models read text and photos and answer narrow questions. `pipeline/statemachine.py` is the only code that changes a ticket's state, and only `verifier` or `human_reviewer` may enter `VERIFIED_CLOSED`.
2. **Abstain when unsure.** Low confidence goes to the human queue. Model failures also go to humans; the app never substitutes fake output.
3. **Evidence receipts.** Each decision is an event with model, prompt version, latency and tokens, in a SHA-256 hash chain (`pipeline/audit.py`). The payload hash stays in the chain when a payload is deleted for privacy.
4. **Report text is untrusted data.** It is wrapped in tags, length-limited, and the model's answer must match a closed Pydantic schema. Injection-looking text is flagged in the audit log.

## Models
| Role | Setting | Used for |
|---|---|---|
| Fast path and vision | `FAST_MODEL` / `VISION_MODEL` (NVIDIA Nemotron 3 Nano Omni) | intake, duplicate judge, visual closure checks |
| Reasoning | `REASON_MODEL` (NVIDIA Nemotron 3 Super) | ambiguous routing, hotspot root-cause work orders |

Model IDs are never hard-coded. If the key or either ID is missing the app runs in Demo Mode and says so everywhere.

## Pipeline
- **Intake** (`pipeline/intake.py`): validated `Intake` object. Failure gives a low-confidence `other` report for a human.
- **Triage** (`pipeline/triage.py`): confidence at or above `route_direct` maps by `campus.yaml`. Otherwise the reasoning model (live) or human (demo). The model may only choose configured departments.
- **Duplicates** (`pipeline/duplicates.py`): candidates are open, same type, same place, last 72 hours, never synthetic sample tickets. A judge (model or text similarity) picks only from candidates.
- **SLA** (`pipeline/sla.py`): deadline from department and urgency. The demo clock shifts only when deadlines are evaluated, per workspace. Escalations it causes are flagged `simulated` and excluded from real figures. Real timestamps are never altered.

## Verification gate (`pipeline/verify.py`)
| Check | Type | Hard fail? |
|---|---|---|
| `not_reused`: byte-identical, near-identical pixels (own ticket), or perceptual-hash match (other tickets) | code | yes |
| `fresh`: EXIF capture time after the report photo and not in the future; missing EXIF is a soft fail | code | yes (missing EXIF: no) |
| `state_ok`: model answers the issue's question from `campus.yaml` (yes/no/unsure with confidence) | model | only when confidently wrong |
| `same_place`: model compares before and after | model | only when confidently "different" |

Verdict: any hard failure means **contradicted** (ticket reopened). Else any unmet check means **needs_evidence**. Else **verified**.
Types without a visual check wait for reporter confirmation or a human decision. A reporter saying "fixed" never closes a photo-checked ticket by itself.

## Data model
`tickets`, `events` (hash chain), `images` (resized JPEG + hashes + EXIF time), `settings` (demo clock per workspace), `hotspots`, `usage` (token and latency log).

## Workspaces
Each browser gets a random workspace id. Tickets, images and the demo clock are scoped to it, so testers never affect each other. New workspaces are seeded with synthetic tickets flagged `synthetic` (excluded from duplicate matching and from "real" escalation counts).
