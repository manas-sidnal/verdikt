import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.run_verifier import verify_login_fix

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Verdikt API",
    description="Evidence-driven verification for AI agent claims.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
