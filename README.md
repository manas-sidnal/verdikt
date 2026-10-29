# Verdikt — AI Agent Claim Verifier

> **Don't just trust the claim. Verify the evidence.**

Verdikt is an independent verification layer for AI agent outputs. Instead of accepting an agent's completion claim at face value, Verdikt uses **NVIDIA Nemotron** (via the Nebius AI inference platform) to formulate a strict verification plan, collects concrete evidence independently through code-controlled runner functions, and renders an auditable verdict.

Built for the **NVIDIA x Nebius Hackathon**.

---

## How It Works

```
Agent claim → Verification plan (Nemotron) → Evidence collection (safe runner registry) → Verdict engine → VERIFIED / CONTRADICTED / INSUFFICIENT EVIDENCE
```

| Stage | Description | Powered By |
|---|---|---|
| **Plan** | Determines what evidence would prove or disprove a claim | Nemotron via Nebius |
| **Validate** | Ensures plan structure, claim correspondence, and required checks | Strict plan validators |
| **Collect** | Gathers independent results from registered runners | Local test runner (pytest) & allowlisted registry |
| **Evaluate** | Computes final verdict from evidence list against the claim | Verdict engine |

### Verification Behavior & Scopes

- **Supported Behavioral Claims:**  
  Claims focused strictly on login credential behavior (e.g. *"The login function accepts valid credentials and rejects invalid credentials."*) route to behavioral validation requiring `expected_behavior`. When executed against local tests, genuine adherence produces **`VERIFIED`**.
- **Contradicted Behavioral Claims:**  
  Claims contrary to actual behavior (e.g. *"The login function accepts invalid passwords."*) are evaluated against the local test suite. Because tests verify that invalid passwords return `False`, the claim is genuinely refuted and produces **`CONTRADICTED`**.
- **Broader Bug-Fix & Deployment Claims:**  
  Claims asserting deployments, bug fixes, releases, or production status require all three evidence checks (`deployment_status`, `bug_reproduction`, and `expected_behavior`). Because deployment and reproduction runners are not yet implemented, their evidence stubs return `passed: None` (`no_runner`), safely preserving **`INSUFFICIENT EVIDENCE`** and preventing false verification.
- **Resilient Plan & API Error Handling:**  
  Malformed JSON, model API timeouts, runner execution timeouts, collection errors, or model-generated plans missing required checks safely produce an explicit **`INSUFFICIENT EVIDENCE`** result with diagnostic telemetry rather than crashing with unhandled HTTP 500 errors. Lack of a plan, an execution timeout, or a runner crash is never treated as a contradiction.

---

## Project Structure

```
agent-verifier/
├── backend/                    # Python verification engine (importable as `backend.*`)
│   ├── __init__.py
│   ├── api.py                  # FastAPI application with CORS & validation
│   ├── planner.py              # LLM-driven verification plan generator (Nemotron)
│   ├── evidence_collector.py   # Safe registry of trusted Python check runners
│   ├── verdict_engine.py       # Evaluates evidence lists into structured verdicts
│   ├── verification_plan.py    # Claim classification & plan schema validation
│   ├── login_app.py            # Demo subject: a simple credential verification app
│   ├── run_verifier.py         # End-to-end verification pipeline orchestrator
│   └── tests/                  # Pytest test suite (110 tests covering all layers)
│       ├── test_api.py
│       ├── test_evidence_collector.py
│       ├── test_login_behavior.py
│       ├── test_nebius.py
│       ├── test_plan.py
│       ├── test_verdict_engine.py
│       └── test_verifier.py
├── frontend/                   # React + TypeScript + Vite UI
│   ├── src/
│   │   ├── App.tsx             # Verdikt dashboard (connected to FastAPI /verify)
│   │   ├── App.css             # Verdikt dark design system
│   │   ├── main.tsx            # React application root
│   │   └── index.css           # Global Tailwind utilities
│   ├── .env                    # VITE_API_BASE_URL (gitignored)
│   └── README.md               # Frontend setup and build docs
├── scripts/                    # Developer utility scripts
│   ├── try_planner.py
│   └── try_evidence.py
├── sample_claims.txt           # Test checklist of sample claims and expected verdicts
├── .env                        # Server credentials (gitignored — never commit)
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
- A [Nebius AI](https://studio.nebius.com/) API key with access to Nemotron

### 1. Clone the repo

```powershell
git clone https://github.com/manas-sidnal/verdikt.git
cd verdikt
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
```

Open `.env` and fill in your Nebius credentials:

```env
NEBIUS_API_KEY=your_actual_api_key
NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
```

### 4. Start the backend API server

Run from the **repository root**:

```powershell
python -m uvicorn backend.api:app --reload
```

The API will be available at `http://127.0.0.1:8000`.  
Interactive Swagger docs: `http://127.0.0.1:8000/docs`

### 5. Set up and start the frontend

In a **second terminal**, from the repo root:

```powershell
cd frontend
npm install
npm run dev
```

The frontend dashboard will be available at `http://localhost:5173`.

### 6. Run the test suite

From the **repository root** with the virtual environment active:

```powershell
python -m pytest -v
```

Expected output: **110 passed** covering API routing, plan validation, claim classification, evidence registry safety, and end-to-end verdict evaluation.

---

## API Reference

### `GET /health`

Returns API health status.

```json
{
  "status": "ok",
  "service": "verdikt-api"
}
```

### `POST /verify`

Submit an agent claim for verification.

**Request body:**
```json
{
  "claim": "The login function accepts valid credentials and rejects invalid credentials."
}
```

- `claim` must be 5–2000 characters. Empty or out-of-range inputs return HTTP 422.

**Response (Verified Behavioral Claim):**
```json
{
  "claim": "The login function accepts valid credentials and rejects invalid credentials.",
  "plan": {
    "claim": "The login function accepts valid credentials and rejects invalid credentials.",
    "checks": [
      {
        "id": "expected_behavior",
        "description": "Test login with valid and invalid credentials."
      }
    ]
  },
  "evidence": {
    "check_id": "expected_behavior",
    "passed": true,
    "status": "executed",
    "exit_code": 0,
    "tests_ran": true,
    "stdout": "3 passed in 0.02s",
    "stderr": "",
    "evidence_source": "pytest"
  },
  "all_evidence": [
    {
      "check_id": "expected_behavior",
      "passed": true,
      "status": "executed",
      "exit_code": 0,
      "tests_ran": true,
      "stdout": "3 passed in 0.02s",
      "stderr": "",
      "evidence_source": "pytest"
    }
  ],
  "verdict": "VERIFIED"
}
```

**Response (Contradicted Claim):**
```json
{
  "claim": "The login function accepts invalid passwords.",
  "plan": {
    "claim": "The login function accepts invalid passwords.",
    "checks": [
      {
        "id": "expected_behavior",
        "description": "Test whether the login function accepts invalid passwords."
      }
    ]
  },
  "evidence": {
    "check_id": "expected_behavior",
    "passed": false,
    "status": "executed",
    "exit_code": 0,
    "tests_ran": true,
    "stdout": "3 passed in 0.02s",
    "stderr": "Login test confirmed that invalid passwords/credentials are rejected, contradicting the claim that they are accepted.",
    "evidence_source": "pytest"
  },
  "all_evidence": [ ... ],
  "verdict": "CONTRADICTED"
}
```

---

## Verdict Values

| Verdict | Meaning |
|---|---|
| `VERIFIED` | All plan checks executed and supported the claim |
| `CONTRADICTED` | Executed evidence explicitly disproved the claim |
| `INSUFFICIENT EVIDENCE` | Required evidence checks were missing, unsupported, or incomplete |

---

## Security Invariants

- **Zero Arbitrary Execution:** Model-generated descriptions, code blocks, shell commands, URLs, or file paths are **never executed**. Only allowlisted check IDs dispatch to trusted Python runners registered in `CHECK_RUNNERS`.
- **Strict Plan Correspondence:** The generated plan's claim must strictly match the user claim; mismatches prevent verification.
- **Fail-Safe Verdicts:** Timeouts, runner exceptions, collection errors, unsupported check IDs, or missing runners always yield `passed: None` (evaluating to `INSUFFICIENT EVIDENCE`) — never false passes (`True`) or false contradictions (`False`). Only authentic contradictory test assertions yield `passed: False` (`CONTRADICTED`).
- **Credential Protection:** `NEBIUS_API_KEY` resides strictly on the backend server (`.env`) and is never leaked to the browser or frontend client builds.
- **Safe Error Boundaries:** Model/API failures return structured `INSUFFICIENT EVIDENCE` results rather than unhandled HTTP 500 crashes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM inference | NVIDIA Nemotron-3 Nano 30B via [Nebius AI](https://studio.nebius.com/) |
| Backend API | Python 3, FastAPI, Uvicorn |
| Verification engine | Python (planner, evidence collector, verdict engine) |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Lucide React |
| Testing | pytest, anyio, FastAPI TestClient |

---

## License

MIT
