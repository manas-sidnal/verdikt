# Verdikt — AI Agent Claim Verifier

> **Don't just trust the claim. Verify the evidence.**

Verdikt is an independent verification layer for AI agent outputs. Instead of accepting a completion message at face value, Verdikt uses **NVIDIA Nemotron** (via the Nebius AI inference platform) to plan what evidence would prove or disprove a claim, then collects that evidence independently and renders a structured verdict.

Built for the **NVIDIA x Nebius Hackathon**.

---

## How It Works

```
Agent claim -> Verification plan (Nemotron) -> Evidence collection (local tests) -> Verdict engine -> VERIFIED / CONTRADICTED / INSUFFICIENT EVIDENCE
```

| Stage | Description | Powered By |
|---|---|---|
| **Plan** | Determines what evidence would prove or disprove a claim | Nemotron via Nebius |
| **Collect** | Gathers independent results from available checks | Local test runner (pytest) |
| **Evaluate** | Compares the claim against the collected evidence | Verdict engine |
| **Deploy check** | Verifies deployment via an independent source *(planned)* | — |

---

## Project Structure

```
agent-verifier/
├── backend/                    # Python verification engine
│   ├── planner.py              # LLM-driven verification plan generator
│   ├── evidence_collector.py   # Runs independent checks and captures results
│   ├── verdict_engine.py       # Evaluates evidence and returns a verdict
│   ├── verification_plan.py    # Plan schema validation
│   ├── login_app.py            # Demo subject: a simple login function
│   ├── run_verifier.py         # End-to-end verification entry point
│   └── tests/                  # Pytest test suite
│       ├── test_login_behavior.py
│       ├── test_plan.py
│       ├── test_verdict_engine.py
│       ├── test_verifier.py
│       └── test_nebius.py
├── frontend/                   # React + TypeScript UI (Vite)
│   └── src/
│       └── App.tsx             # Verdikt dashboard
├── scripts/                    # Developer utility scripts
│   ├── try_planner.py          # Manually test the planner
│   └── try_evidence.py         # Manually test the evidence collector
├── .env.example                # Environment variable template
├── .gitignore
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Python dependencies
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the frontend)
- A [Nebius AI](https://studio.nebius.com/) API key

### 1. Clone the repo

```bash
git clone https://github.com/your-username/agent-verifier.git
cd agent-verifier
```

### 2. Set up the Python backend

```bash
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and add your NEBIUS_API_KEY
```

### 4. Run the verifier

```bash
# From the project root
python backend/run_verifier.py
```

### 5. Run the test suite

```bash
pytest
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## Developer Scripts

Run these from the project root to test individual components:

```bash
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
| Backend | Python 3, OpenAI-compatible SDK |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Testing | pytest |

---

## License

MIT
