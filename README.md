# Deep Research Agent

```text
ALB → FastAPI (ECS)
  → Step Functions (DynamoDB QUEUED + SQS + SNS alert)
  → ECS worker → Deep Agent (Gemini + Tavily)
  → S3 reports/<hash>-<slug>.md + DynamoDB COMPLETED/FAILED
  → EventBridge → SNS completed/failed alert
```

API keys load from **AWS Secrets Manager** (fallback: `.env`).

## HTTP API

`/research` endpoints require the shared key from Secrets Manager
(`RESEARCH_API_KEY`) in the `X-API-Key` header; `/health` is public.

```bash
curl -X POST "$ALB/research" \
  -H "X-API-Key: $RESEARCH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Your question"}'

curl "$ALB/research/<job_id>" -H "X-API-Key: $RESEARCH_API_KEY"
```

## Layout

```text
api/main.py             # FastAPI: POST /research, GET /research/{job_id}
src/agent.py            # CLI + research orchestration
src/worker.py           # SQS polling worker
tools/search.py         # Tavily
helpers/
  config.py             # .env / settings
  secrets.py            # Secrets Manager
  jobs.py               # DynamoDB job state
  queue.py              # SQS receive/ack
  stepfunctions.py      # start enqueue execution
  events.py             # EventBridge domain events
  observability.py      # JSON logs + CloudWatch metrics
  reports.py            # local report naming
  s3.py                 # S3 upload
scripts/
  test_secrets.py
  test_s3.py
infra/                  # ECS / ALB / Step Functions / EventBridge / Terraform
reports/                # local staging only (gitignored)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Configure `.env`:

```env
SECRETS_MANAGER_SECRET_ID=deep-research-agent/dev
MODEL=google_genai:gemini-3.5-flash-lite
AWS_REGION=eu-north-1
S3_BUCKET=deep-research-agent-139675292967-eu-north-1-an
```

Put API keys in Secrets Manager JSON: `GOOGLE_API_KEY`, `TAVILY_API_KEY`, …

AWS credentials: env vars or `~/.aws/credentials` (needs S3 + Secrets Manager access).

## Run

```bash
# Secrets Manager + upload to S3 (deletes local after upload)
python -m src.agent --secrets-overwrite "What is LangGraph?"

# Keep a local copy too
python -m src.agent --secrets-overwrite --keep-local "Your question"

# Local only
python -m src.agent --no-upload "Your question"
```

## Smoke tests

```bash
python scripts/test_secrets.py
python scripts/test_s3.py
pytest
```

## Docker

Image has **no API keys**. At runtime it uses AWS credentials + Secrets Manager.

### Build

```bash
docker build -t deep-research-agent:local .
```

### Run

```bash
docker run --rm \
  -e AWS_REGION=eu-north-1 \
  -e S3_BUCKET=deep-research-agent-139675292967-eu-north-1-an \
  -e SECRETS_MANAGER_SECRET_ID=deep-research-agent/dev \
  -e MODEL=google_genai:gemini-3.5-flash-lite \
  -v "$HOME/.aws:/home/appuser/.aws:ro" \
  deep-research-agent:local \
  "What is LangGraph?"
```

Or with Compose:

```bash
docker compose run --rm agent "What is LangGraph?"
```

### Dockerfile map (learning)

| Part | Why |
|------|-----|
| `FROM python:3.12-slim` | Small base image with a stable Python |
| `ENV PYTHONUNBUFFERED=1` | Live logs in the terminal |
| Copy `pyproject.toml` + packages then `pip install .` | Install app as a package |
| `USER appuser` | Do not run as root |
| `ENTRYPOINT ... --secrets-overwrite` | Always load keys from Secrets Manager |
| No `.env` in the image | Secrets stay outside the image |

## CI / CD (GitHub Actions)

Repo: https://github.com/adhithyasash1/deep-research-agent

| Workflow | When | What |
|----------|------|------|
| **CI** | push / PR to `main` | `pytest` only (no AWS) |
| **Deploy** | manual (`workflow_dispatch`) | ARM64 build → ECR → register ECS task defs |

Deploy stays manual so every push does not burn Fargate/ECR credits. Default leaves services at `desiredCount=0`; set **scale_up** when you want them running.

AWS auth uses **OIDC** (role `deep-research-github-actions`) - no long-lived access keys in GitHub secrets.
