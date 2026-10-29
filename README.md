# Verdikt — verify what coding agents claim

> **Agents say it's done. Verdikt runs the tests.**

Coding agents end their work with a confident summary: *"Fixed. All tests pass."* Sometimes that is
false, and sometimes the agent quietly edited the tests to make it look true. Verdikt is an independent
verification layer that takes the agent's report, splits it into claims, and judges **each claim against
real, executed evidence** instead of against what the agent says about itself.

Built for the **NVIDIA x Nebius Global AI Hackathon** · Track: **Coding and Agentic Engineering**.

```
agent report + agent patch
   │
   ├─► Nemotron (Nebius Token Factory): split the report into atomic claims, pick an allowlisted check per claim
   │
   ├─► Sandbox: run the repo's real tests on a pristine copy AND on the agent's patched copy
   │
   ├─► Judge each claim from executed evidence only  →  VERIFIED / CONTRADICTED / INSUFFICIENT EVIDENCE
   │
   └─► Integrity scan: did the patch touch the tests?
```

**The model never decides what is true.** Nemotron only decides *which claims were made* and *which check
could test each one*. Every verdict comes from a real `pytest` exit code, a real file diff, or the absence
of evidence.

## The demo: four kinds of agent

Each sample repo ships with a real bug and a real test suite. The lab applies a stored agent patch in a
sandbox and verifies the report that goes with it.

| Agent | What it does | Verdict | Why |
|---|---|---|---|
| **Honest** | Writes a correct fix, reports exactly what it did | `VERIFIED` | Tests failed before, pass now, and the file really changed |
| **Overclaiming** | Writes a plausible half-fix, claims "all tests pass" | `CONTRADICTED` | A real failing test, with pytest's exit code and counts |
| **Test-tampering** | Half-fix, then rewrites the tests to go green | `CONTRADICTED` | Test edits are ignored and flagged; the real tests still fail |
| **Deploy-claiming** | Correct fix, claims it deployed to production | `INSUFFICIENT EVIDENCE` | There is no deployment runner, so it can never be verified |

Two ways to run it:

- **Replay** (no API key): the agent's claims are scripted so the whole demo runs offline. The verdicts
  still come from real sandboxed test runs. The UI labels this clearly.
- **Live** (needs a Nebius key): you can edit the agent's report, and **Nemotron on Nebius Token Factory**
  extracts the claims from it. The stored patch stays the same.

## How Nemotron and Nebius Token Factory are used

- **Claim extraction with Nemotron.** In live mode, `backend/claim_extractor.py` sends the agent's report to a
  Nemotron model (default `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, configurable with `NEBIUS_MODEL`) through the
  Token Factory OpenAI-compatible endpoint (`https://api.tokenfactory.nebius.com/v1/`).
- **Strict validation of model output.** Every claim must carry a `quote` that appears **verbatim** in the report
  (so the model cannot invent claims the agent never made), a `check` from a fixed allowlist, and, for targeted
  tests, a test id Verdikt itself collected. Anything else is dropped and shown in the UI as rejected output.
- **Why Token Factory helped.** One OpenAI-compatible endpoint means switching between Nemotron sizes is a
  one-line environment change (`NEBIUS_MODEL`), with no second client or SDK.
- The original planner in `backend/planner.py` also calls Nemotron on Token Factory (see *Legacy prototype*).

## Safety invariants

- **No model output is ever executed.** The sandbox runs one fixed command (`python -m pytest`).
- **A hosted demo cannot be made to run a visitor's code.** The API accepts a target and a scenario *name*;
  patches come only from stored scenarios on the server. Clients cannot upload a patch.
- **Targets are allowlisted** by name and live under `backend/targets/`.
- **Patches can only change `.py` source files** with safe relative paths. Edits to `tests/`, `test_*.py`,
  `*_test.py` and `conftest.py` are ignored and reported as tampering.
- **Scrubbed environment, timeout, process-group kill.** API keys never reach the child process.
- **Fail-safe verdicts.** A timeout, infrastructure error, or model failure is `INSUFFICIENT EVIDENCE`, never a
  false contradiction. The one exception is deliberate: if the unpatched repo collects fine and the agent's patch
  breaks collection (for example a syntax error), the claim "tests pass" is false and is marked contradicted.
- **Nothing is verified without evidence.** If no valid claim can be extracted, the result is
  `INSUFFICIENT EVIDENCE`, never `VERIFIED`.

## Quickstart

Requires Python 3.10+ and Node.js 18+.

**Windows (PowerShell)**
```powershell
git clone https://github.com/manas-sidnal/verdikt.git
cd verdikt
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # add NEBIUS_API_KEY to enable live mode (optional)
python -m uvicorn backend.api:app --reload
```

**macOS / Linux**
```bash
git clone https://github.com/manas-sidnal/verdikt.git
cd verdikt
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add NEBIUS_API_KEY to enable live mode (optional)
python -m uvicorn backend.api:app --reload
```

In a second terminal:
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Replay mode works with no key at all.

### Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `NEBIUS_API_KEY` | Token Factory key (enables live mode) |
| `NEBIUS_MODEL` | Nemotron model id, e.g. `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| `VERDIKT_CORS_ORIGINS` | Extra allowed origins for a hosted frontend (comma-separated) |
| `VERDIKT_LIVE_LIMIT_PER_HOUR` | Live runs per hour, to protect credits (default 30) |
| `VERDIKT_MAX_CONCURRENT_RUNS` | Concurrent sandbox runs (default 2) |

To confirm your key and model work: `python scripts/check_nebius.py`.

## API

| Route | Description |
|---|---|
| `GET /demo/config` | Repos, scenarios, default reports, and whether live mode is available |
| `POST /demo/verify` | Verify a stored agent scenario. Body: `{"target": "cart_total", "scenario": "overclaim", "mode": "replay"}`. In `live` mode an optional `report` string replaces the agent's report. |
| `GET /health` | Health check |
| `POST /verify` | The original login-only prototype (see below) |

Interactive docs: `http://127.0.0.1:8000/docs`.

## Project structure

```
backend/
  api.py               FastAPI app and routes
  service.py           Demo orchestration, rate limits, concurrency limits
  repo_verifier.py     Claim-by-claim verification of an agent report
  claim_extractor.py   Nemotron claim extraction + strict output validation
  llm.py               Token Factory chat helper
  sandbox.py           Sandboxed pytest runner, patch validation, tamper protection
  demo_agents.py       Scripted agent scenarios (replay mode)
  targets/             Sample repos with a real bug and a real test suite
  target_solutions/    Stored "good" and "partial" fixes for the scenarios
  tests/               Test suite
frontend/              React + TypeScript + Vite UI (the "Agent lab")
scripts/               Developer utilities, incl. check_nebius.py
```

## Tests

```bash
python -m pytest -q
```

The suite covers sandbox isolation (path traversal, test tampering, timeouts, environment scrubbing,
cleanup), every demo scenario, hostile or malformed model output, rate limiting, and the HTTP layer.
Model calls are faked in tests, so no key or network is needed.

## Limitations

- **Targets are small, Python-only, and synthetic.** Three sample repos prove the pipeline; they are not a
  benchmark of real-world agent behaviour.
- **Replay-mode claims are scripted.** Only live mode exercises Nemotron, and it needs a Nebius key.
- **No deployment verification.** Deployment claims always end as `INSUFFICIENT EVIDENCE` by design.
- **Five check types.** Claims that fit none of them (for example "this is more readable") are skipped, not judged.
- **Agent patches are stored scenarios**, not live agent runs. Wiring Verdikt to a real agent's output is future work.

## Legacy prototype

`POST /verify`, `backend/planner.py`, `backend/evidence_collector.py` and `backend/verdict_engine.py` are the first
version of Verdikt, which verified claims about one demo login function. They are kept for reference; the Agent lab
uses the sandbox verifier described above.

## License

MIT — see [LICENSE](LICENSE).
