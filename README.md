# Verdikt — AI Agent Claim Verifier

> **Don't just trust the claim. Verify the evidence.**

Verdikt is an independent verification layer for AI agent outputs. Instead of accepting a completion message at face value, Verdikt uses **NVIDIA Nemotron** (via the Nebius AI inference platform) to plan what evidence would prove or disprove a claim, then collects that evidence independently and renders a structured verdict.

Built for the **NVIDIA x Nebius Hackathon**.

---

## How It Works

```
Agent claim → Verification plan (Nemotron) → Evidence collection (local tests) → Verdict engine → VERIFIED / CONTRADICTED / INSUFFICIENT EVIDENCE
```

| Stage | Description | Powered By |
|---|---|---|
| **Plan** | Determines what evidence would prove or disprove a claim | Nemotron via Nebius |
| **Collect** | Gathers independent results from available checks | Local test runner (pytest) |
| **Evaluate** | Compares the claim against the collected evidence | Verdict engine |
| **Deploy check** | Verifies deployment via an independent source *(planned)* | — |

> **Prototype scope:** The current evidence check tests local login behaviour only. It does not independently verify a real deployment. Deployment evidence is always absent, so the verdict will be *INSUFFICIENT EVIDENCE* unless the login tests fail.

---

## Project Structure

```
agent-verifier/
├── backend/                    # Python verification engine (importable as `backend.*`)
│   ├── __init__.py
│   ├── api.py                  # FastAPI application
│   ├── planner.py              # LLM-driven verification plan generator
│   ├── evidence_collector.py   # Runs independent checks and captures results
│   ├── verdict_engine.py       # Evaluates evidence and returns a verdict
│   ├── verification_plan.py    # Plan schema validation
│   ├── login_app.py            # Demo subject: a simple login function
│   ├── run_verifier.py         # End-to-end verification entry point
│   └── tests/                  # Pytest test suite (20 existing + 7 API tests)
│       ├── test_api.py
│       ├── test_login_behavior.py
│       ├── test_plan.py
│       ├── test_verdict_engine.py
│       ├── test_verifier.py
│       └── test_nebius.py
├── frontend/                   # React + TypeScript + Vite UI
│   ├── src/
│   │   ├── App.tsx             # Verdikt dashboard (connected to API)
│   │   └── App.css             # Dark design system
│   └── .env                    # VITE_API_BASE_URL (gitignored)
├── scripts/                    # Developer utility scripts
│   ├── try_planner.py
│   └── try_evidence.py
├── .env                        # Real credentials (gitignored — never commit)
├── .env.example                # Environment variable template
├── .gitignore
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Python dependencies
└── README.md
```

---

## Getting Started (Windows)

### Prerequisites

- Python 3.10+
- Node.js 18+
- A [Nebius AI](https://studio.nebius.com/) API key

### 1. Clone the repo

```powershell
git clone https://github.com/your-username/agent-verifier.git
cd agent-verifier
```

### 2. Set up the Python virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
copy .env.example .env
# Open .env and fill in your NEBIUS_API_KEY
```

Your `.env` must contain:

```
NEBIUS_API_KEY=your_actual_api_key
NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
```

### 4. Start the API server

Run from the **repository root** (not from `backend/`):

```powershell
python -m uvicorn backend.api:app --reload
```

The API will be available at `http://127.0.0.1:8000`.  
Interactive docs: `http://127.0.0.1:8000/docs`

### 5. Set up and start the frontend

In a **second terminal**, from the repo root:

```powershell
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

The frontend reads `VITE_API_BASE_URL` from `frontend/.env` (defaults to `http://127.0.0.1:8000`). This file is gitignored; it is created automatically at setup or you can create it manually:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 6. Run the test suite

From the **repository root** with the virtual environment active:

```powershell
python -m pytest
```

Expected output: **27 passed** (20 original tests + 7 API tests).

---

## API Reference

### `GET /health`

Returns API status.

```json
{ "status": "ok", "service": "verdikt-api" }
```

### `POST /verify`

Submit a claim for verification.

**Request body:**
```json
{ "claim": "The login bug is fixed and the deployment is successful." }
```

- `claim` must be 5–2000 characters. Empty or out-of-range inputs return HTTP 422.

**Response:**
```json
{
  "claim": "...",
  "plan": {
    "claim": "...",
    "checks": [
      { "id": "deployment_status", "description": "..." },
      { "id": "bug_reproduction",  "description": "..." },
      { "id": "expected_behavior", "description": "..." }
    ]
  },
  "evidence": {
    "check_id": "expected_behavior",
    "passed": true,
    "exit_code": 0,
    "tests_ran": true,
    "stdout": "3 passed in 0.02s",
    "stderr": "",
    "evidence_source": "pytest"
  },
  "verdict": "INSUFFICIENT EVIDENCE"
}
```

---

## Developer Scripts

Run from the project root (virtual environment active):

```powershell
# Test the planner (calls Nemotron via Nebius)
python scripts/try_planner.py

# Test the evidence collector (runs pytest locally)
python scripts/try_evidence.py
```

---

## Verdict Values

| Verdict | Meaning |
|---|---|
| `VERIFIED` | All evidence supports the claim |
| `CONTRADICTED` | Evidence contradicts the claim |
| `INSUFFICIENT EVIDENCE` | Not enough evidence to decide |

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM inference | NVIDIA Nemotron-3 Nano 30B via [Nebius AI](https://studio.nebius.com/) |
| Backend API | Python 3, FastAPI, Uvicorn |
| Verification engine | Python (planner, evidence collector, verdict engine) |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 |
| Testing | pytest + FastAPI TestClient |

---

## Security Notes

- `NEBIUS_API_KEY` must remain in `.env` on the server. It is never exposed to the browser or any `VITE_` variable.
- The API does not include full stack traces or exception messages in HTTP error responses.
- CORS is restricted to `localhost:5173` and `127.0.0.1:5173` only.
- `.env`, `.venv/`, `node_modules/`, build outputs, and `frontend/.env` are all gitignored.

---

## License

MIT
