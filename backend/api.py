import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from typing import Literal

from backend import sandbox, service
from backend.run_verifier import verify_login_fix

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Verdikt API",
    description="Evidence-driven verification for AI agent claims.",
    version="0.1.0",
)

# Local dev origins are always allowed. For a hosted frontend, set
# VERDIKT_CORS_ORIGINS to a comma-separated list, e.g.
# VERDIKT_CORS_ORIGINS=https://verdikt.example.com
_DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
_EXTRA_ORIGINS = [
    o.strip() for o in os.getenv("VERDIKT_CORS_ORIGINS", "").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _EXTRA_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class VerificationRequest(BaseModel):
    claim: str = Field(
        min_length=5,
        max_length=2000,
        description="The claim to verify. Must be between 5 and 2000 characters.",
    )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "verdikt-api",
    }


@app.post("/verify")
def verify_claim(request: VerificationRequest):
    # This route calls the model, so it shares the hourly budget that protects credits.
    if not service.allow_model_call():
        raise HTTPException(status_code=429, detail="Rate limit reached. Try again later.")
    try:
        result = verify_login_fix(request.claim)
        return result
    except Exception as exc:
        # Log full details server-side; never expose to the browser.
        logger.exception(
            "Verification failed for claim %r: %s: %s",
            request.claim[:80],
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Verification failed. Check the API server logs.",
        ) from exc


# ---------------------------------------------------------------------------
# Repo verification demo (real sandboxed evidence)
# ---------------------------------------------------------------------------

class DemoRequest(BaseModel):
    target: str = Field(min_length=1, max_length=60)
    scenario: Literal["honest", "overclaim", "tamper", "deploy"]
    mode: Literal["replay", "live"] = "replay"
    report: str | None = Field(
        default=None,
        max_length=service.MAX_REPORT_CHARS,
        description="Live mode only: custom agent report text for Nemotron to extract claims from.",
    )


@app.get("/demo/config")
def demo_config():
    return service.describe()


@app.post("/demo/verify")
def demo_verify(request: DemoRequest):
    try:
        return service.run_demo(request.target, request.scenario, request.mode, request.report)
    except (sandbox.SandboxError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except service.LiveUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except service.RateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except service.Busy as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Demo verification failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=500, detail="Verification failed. Check the API server logs."
        ) from exc
