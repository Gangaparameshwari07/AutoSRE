---
title: AutoSRE OpenEnv
emoji: "🛠️"
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AutoSRE OpenEnv Environment

## Overview
AutoSRE is an OpenEnv environment for microservice incident diagnosis and remediation. It simulates a realistic Site Reliability Engineering workflow in which an agent monitors service health, interprets operational signals, and applies corrective actions to restore platform stability.

The environment is designed as a real-world systems task rather than a toy benchmark. It focuses on service outages, cascading failures, resource exhaustion, and operational recovery through a structured control-plane API.

## Why This Environment
Production systems rarely fail in isolated ways. A database bottleneck can degrade authentication, which can then cascade into gateway failure and customer-visible downtime. AutoSRE models this dependency chain so that an agent must reason about root cause, prioritize the right fix, and recover the system efficiently.

## OpenEnv Interface
AutoSRE implements the standard OpenEnv interaction pattern:

- `reset()` initializes the environment to a task-specific failure scenario
- `step(action)` applies one remediation action and returns the updated observation, reward, termination flag, and metadata
- `state()` returns the current environment state without advancing the episode

## Action Space
The agent may choose one of the following actions:

- `restart_service`
- `scale_up`
- `scale_down`
- `clear_cache`
- `rollback`
- `noop`

Each action targets one of these services:

- `api-gateway`
- `auth-service`
- `order-service`
- `payment-service`
- `database`

## Observation Space
Each observation contains:

- service-level status
- CPU usage
- memory usage
- latency
- error rate
- recent logs
- alert summaries
- task description
- aggregate system health score in the `0.0-1.0` range

## Tasks
AutoSRE includes three graded tasks with increasing difficulty:

- `task_1_easy`: restore a crashed `payment-service`
- `task_2_medium`: stabilize an `auth-service` memory leak using cache clearing and scaling
- `task_3_hard`: recover from a cascading failure rooted in a degraded `database`

## Reward Design
The reward function is shaped around `system_health_score`, which provides continuous feedback across the trajectory instead of a sparse terminal-only signal.

Key properties:

- partial recovery receives partial reward
- degraded services contribute less than healthy services
- full service restoration yields a maximal score
- unnecessary or ineffective actions do not improve reward

## Grading
Each task is evaluated with a deterministic grader that returns a score in the `0.0-1.0` range.

The grader considers:

- service availability
- system performance
- recovery efficiency

If the API gateway remains unavailable at the end of the episode, the submission receives a failure score for that run.

## Project Structure
- `environment.py`: core simulation logic and environment state transitions
- `definitions.py`: task definitions and scenario injection
- `models.py`: typed action, observation, reward, and service models
- `graders.py`: deterministic task graders
- `server.py`: local FastAPI entrypoint
- `server/app.py`: packaging-compatible application entrypoint for OpenEnv deployment
- `inference.py`: baseline agent runner using the OpenAI client
- `openenv.yaml`: environment metadata
- `validate_submission.py`: local validation workflow
- `validate-submission.sh`: pre-submission deployment validator

## Setup
Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Required Environment Variables
- `API_BASE_URL`
- `MODEL_NAME`
- `API_KEY`

## Configuration and Secrets
AutoSRE reads runtime configuration from environment variables. Sensitive credentials are not hardcoded in the codebase.

Recommended deployment practice:

- store `API_KEY` as a Hugging Face Space secret
- store `API_BASE_URL` and `MODEL_NAME` as Space variables
- keep local credentials in `.env` only for development
- never commit `.env` to version control

The repository is configured so `.env` is excluded from both git tracking and Docker build context.

## Running Locally
Start the control plane:

```powershell
python server.py
```

In a second terminal, run the baseline agent:

```powershell
python inference.py
```

The agent reads `TASK_ID` from the environment. If `TASK_ID` is not set, it defaults to `task_3_hard`.

To run a specific task locally:

```powershell
$env:TASK_ID="task_1_easy"
python inference.py
```

The dashboard will be available at:

`http://localhost:7860`

## Validation
Run the local validator:

```powershell
python validate_submission.py
```

Run the OpenEnv packaging validator:

```powershell
openenv validate
```

After deployment, run the submission validator:

```bash
./validate-submission.sh https://gangapd-auto-sre-agent.hf.space
```

## Docker
Build and run locally:

```powershell
docker build -t autosre-check .
docker run -p 7860:7860 autosre-check
```

## Hugging Face Spaces
This project is configured for deployment as a Docker-based Hugging Face Space. The README front matter specifies:

- `sdk: docker`
- `app_port: 7860`

## Baseline Results
Observed local baseline grader results:

- `task_1_easy`: `1.00`
- `task_2_medium`: `1.00`
- `task_3_hard`: `0.99`

## Submission Status
The project has been validated locally and against the deployment checklist, including:

- `openenv validate`
- Docker build success
- live `/reset` response on Hugging Face Space
- successful baseline inference run against the deployed environment
