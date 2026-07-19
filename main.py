# main.py
#
# AnomX — FastAPI Application
#
# This is the main entry point for the AnomX anomaly detection API.
# It exposes a /score endpoint that accepts a single event as JSON,
# runs it through the trained LSTM Autoencoder scorer, and returns
# an anomaly score with human-readable explanation.
#
# Prerequisites:
#   1. Model artifacts from Week 7-8 must exist at MODEL_PATH
#      (lstm_autoencoder.pt, lstm_scaler.pkl, lstm_threshold.pkl)
#   2. Dependencies installed: pip install -r requirements.txt
#
# Usage:
#   uvicorn main:app --reload
#   uvicorn main:app --host 0.0.0.0 --port 8000
#
# Then visit:
#   http://localhost:8000/docs     — interactive API explorer
#   http://localhost:8000/health   — health check
#
# ─────────────────────────────────────────────────────────────────────────────

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Import our Pydantic request/response schemas
from schemas import EventRequest, ScoreResponse, FeatureDetail, HealthResponse

# Import shared config
from stream_config import MODEL_PATH

# ─────────────────────────────────────────────────────────────────────────────
# Import the scorer from the local repository layout
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = HERE
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from models.scorer import ForexGuardScorer
    SCORER_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Could not import ForexGuardScorer: {e}")
    SCORER_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Application State
#
# We store the scorer in a module-level variable so it is shared across all
# requests. Loading the model once at startup is critical for performance —
# if we loaded it on every request, the API would be extremely slow.
# ─────────────────────────────────────────────────────────────────────────────

scorer: Optional[ForexGuardScorer] = None


# ─────────────────────────────────────────────────────────────────────────────
# Application Lifecycle
#
# FastAPI's lifespan context manager runs startup and shutdown code.
# This is the modern equivalent of @app.on_event("startup").
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load the model when the server starts up; clean up when it shuts down.

    The 'yield' separates startup (code before yield) from shutdown (code after).
    Everything before yield runs before the first request is accepted.
    Everything after yield runs after the server begins its shutdown sequence.
    """
    global scorer

    # ── Startup ───────────────────────────────────────────────────────────────
    print("[INFO] AnomX API starting up...")

    if not SCORER_AVAILABLE:
        print("[WARN] ForexGuardScorer could not be imported. /score endpoint will be unavailable.")
    else:
        model_dir = Path(MODEL_PATH)
        if not model_dir.exists():
            print(f"[WARN] Model directory not found: {model_dir.resolve()}")
            print("       Train the model in week7-8 first, then restart this server.")
        else:
            try:
                print(f"[INFO] Loading model from: {model_dir.resolve()}")
                scorer = ForexGuardScorer(model_path=str(model_dir))
                print("[INFO] ✅ ForexGuardScorer loaded and ready.")
            except Exception as e:
                print(f"[ERROR] Failed to load scorer: {e}")
                scorer = None

    yield  # Server is now running and accepting requests

    # ── Shutdown ──────────────────────────────────────────────────────────────
    print("[INFO] AnomX API shutting down.")
    scorer = None


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AnomX — Trader Behavior Anomaly Detection API",
    description=(
        "Real-time anomaly scoring for trading events using an LSTM Autoencoder. "
        "Built as part of the AnomX SOC 2026 mentorship program (Weeks 9–10)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the server status and whether the model is loaded.",
)
def health_check() -> HealthResponse:
    """
    Simple health check endpoint.

    Returns HTTP 200 with {"status": "ok"} if the server is running.
    The model_loaded field tells you whether scoring is available.

    Use this to verify the server is up before sending scoring requests.
    """
    return HealthResponse(
        status="ok",
        model_loaded=(scorer is not None),
    )


@app.post(
    "/score",
    response_model=ScoreResponse,
    summary="Score an Event",
    description=(
        "Accept a single behavioral event and return an anomaly score with explanation. "
        "Requires the model to be loaded (check /health first)."
    ),
    responses={
        503: {"description": "Model not loaded — check server logs"},
        422: {"description": "Invalid request body — check field types"},
    },
)
def score_event(event: EventRequest) -> ScoreResponse:
    """
    Score a single behavioral event.

    This is the main endpoint of the AnomX API. It accepts a JSON body
    containing one event (a user action such as a login, trade, or withdrawal)
    and returns an anomaly score, severity level, and human-readable reasons.

    The LSTM Autoencoder maintains a per-user sliding window of the last 10
    events. Scoring only produces a meaningful result once 10 events have been
    seen for a given user. Before that, a score of 0.0 is returned (normal).

    Args:
        event: A Pydantic EventRequest object (parsed from the JSON body).

    Returns:
        A ScoreResponse containing the scoring result.

    Raises:
        HTTPException 503: If the model has not been loaded yet.
    """
    # Check that the scorer is available
    if scorer is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Scorer is not loaded. "
                "Check that model artifacts exist at MODEL_PATH and restart the server."
            ),
        )

    # TODO for mentees:
    # The scorer expects a plain Python dict, not a Pydantic object.
    # model_dump() converts the Pydantic model to a dict.
    # This is equivalent to calling event.dict() in Pydantic v1.
    event_dict = event.model_dump()

    # Call the scorer — this is the same function used in consumer.py
    try:
        result = scorer.score(event_dict)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Scoring failed: {str(e)}"
        )

    # Convert the list of top_features dicts to FeatureDetail objects
    # so that the response validates against the ScoreResponse schema
    top_features = [
        FeatureDetail(
            feature=f["feature"],
            raw_value=float(f.get("raw_value", 0.0)),
            scaled_value=float(f.get("scaled_value", 0.0)),
        )
        for f in result.get("top_features", [])
    ]

    return ScoreResponse(
        user_id=result.get("user_id", ""),
        event_id=result.get("event_id"),
        event_type=result.get("event_type"),
        timestamp=result.get("timestamp"),
        anomaly_score=float(result.get("anomaly_score", 0.0)),
        lstm_score=float(result.get("lstm_score", 0.0)),
        is_anomaly=bool(result.get("is_anomaly", False)),
        severity=result.get("severity", "LOW"),
        verdict=result.get("verdict", "✅ NORMAL"),
        reasons=result.get("reasons", []),
        top_features=top_features,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Run directly (alternative to uvicorn CLI)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,   # auto-restart on file changes
        log_level="info",
    )
