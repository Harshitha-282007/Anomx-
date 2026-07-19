# schemas.py
#
# AnomX FastAPI — Pydantic Request and Response Models
#
# Pydantic models define the exact shape (structure and types) of data
# entering and leaving the API. FastAPI uses these to:
#   • Automatically parse and validate incoming JSON request bodies
#   • Serialise Python objects to JSON response bodies
#   • Generate the interactive /docs documentation
#
# If a client sends data that does not match the schema, FastAPI returns
# a 422 Unprocessable Entity error automatically — no manual validation needed.
#
# ─────────────────────────────────────────────────────────────────────────────

from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Request Model
#
# The client sends one event to POST /score. The event should contain the
# 46 features the model was trained on, plus metadata fields (user_id, etc.).
#
# Most feature fields are Optional with a default of 0.0. This is intentional:
# in a real stream, not every event type will have all features populated.
# Missing features are handled by safe_value() inside the scorer.
# ─────────────────────────────────────────────────────────────────────────────

class EventRequest(BaseModel):
    """
    Represents a single behavioral event to be scored.

    Metadata fields (user_id, event_type, timestamp) are used for
    identification and logging. All numeric fields feed into the model.
    """

    # ── Event Metadata ────────────────────────────────────────────────────────
    user_id:    str = Field(..., description="Unique user identifier, e.g. 'U0042'")
    event_id:   Optional[str] = Field(None, description="Unique event identifier")
    event_type: Optional[str] = Field(None, description="Type of event: login, trade, withdrawal, etc.")
    timestamp:  Optional[str] = Field(None, description="ISO 8601 timestamp of the event")

    # ── Time Features ─────────────────────────────────────────────────────────
    hour_of_day:  Optional[float] = Field(0.0, description="Hour when event occurred (0–23)")
    day_of_week:  Optional[float] = Field(0.0, description="Day of week (0=Monday, 6=Sunday)")
    is_weekend:   Optional[float] = Field(0.0, description="1 if weekend, 0 if weekday")

    # ── Login / Session Features ──────────────────────────────────────────────
    login_success:            Optional[float] = Field(0.0, description="1 if login succeeded, 0 if failed")
    failed_attempts:          Optional[float] = Field(0.0, description="Number of failed login attempts")
    timezone_gap_hours:       Optional[float] = Field(0.0, description="Hours difference from user's usual timezone")
    session_duration_mins:    Optional[float] = Field(0.0, description="Duration of the session in minutes")
    page_clicks:              Optional[float] = Field(0.0, description="Number of page clicks in the session")
    click_rate_per_min:       Optional[float] = Field(0.0, description="Clicks per minute during session")
    account_age_days:         Optional[float] = Field(0.0, description="Days since account was created")

    # ── Trade Features ────────────────────────────────────────────────────────
    lot_size:                 Optional[float] = Field(0.0, description="Size of the trade in lots")
    trade_volume:             Optional[float] = Field(0.0, description="Trade volume in base currency")
    pnl:                      Optional[float] = Field(0.0, description="Profit or loss for the trade")
    margin_used:              Optional[float] = Field(0.0, description="Margin used for the trade")
    trade_duration_seconds:   Optional[float] = Field(0.0, description="How long the trade position was held")
    trade_volume_vs_baseline: Optional[float] = Field(0.0, description="Trade volume relative to user baseline")
    is_night_trade:           Optional[float] = Field(0.0, description="1 if trade occurred during night hours")

    # ── Financial Transaction Features ────────────────────────────────────────
    amount:                   Optional[float] = Field(0.0, description="Transaction amount")
    is_immediate_withdrawal:  Optional[float] = Field(0.0, description="1 if withdrawal immediately followed deposit")

    # ── Temporal Gap Features ─────────────────────────────────────────────────
    time_since_last_event_sec:   Optional[float] = Field(0.0)
    time_since_last_login_sec:   Optional[float] = Field(0.0)
    time_since_last_deposit_sec: Optional[float] = Field(0.0)

    # ── Rolling Window Features ───────────────────────────────────────────────
    roll_5_trade_vol_mean:    Optional[float] = Field(0.0)
    roll_5_trade_vol_std:     Optional[float] = Field(0.0)
    roll_5_pnl_mean:          Optional[float] = Field(0.0)
    roll_10_trade_vol_mean:   Optional[float] = Field(0.0)
    roll_10_trade_vol_std:    Optional[float] = Field(0.0)
    roll_10_pnl_mean:         Optional[float] = Field(0.0)
    roll_30_trade_vol_mean:   Optional[float] = Field(0.0)
    roll_30_trade_vol_std:    Optional[float] = Field(0.0)
    roll_30_pnl_mean:         Optional[float] = Field(0.0)
    roll_5_click_rate_mean:   Optional[float] = Field(0.0)
    roll_10_click_rate_mean:  Optional[float] = Field(0.0)
    roll_30_click_rate_mean:  Optional[float] = Field(0.0)

    # ── Burst Features ────────────────────────────────────────────────────────
    burst_count_5min:  Optional[float] = Field(0.0, description="Events from this user in last 5 minutes")
    burst_count_30min: Optional[float] = Field(0.0, description="Events from this user in last 30 minutes")

    # ── Device / Geographic Diversity Features ────────────────────────────────
    unique_ips_last_10_logins:      Optional[float] = Field(0.0)
    unique_countries_last_10_logins: Optional[float] = Field(0.0)
    unique_devices_last_10_logins:   Optional[float] = Field(0.0)
    rolling_failed_attempts_5:       Optional[float] = Field(0.0)

    # ── Deposit / Withdrawal Features ─────────────────────────────────────────
    roll_5_deposit_sum:          Optional[float] = Field(0.0)
    withdrawal_to_deposit_ratio: Optional[float] = Field(0.0)

    # ── Z-Score Features ──────────────────────────────────────────────────────
    trade_vol_zscore:       Optional[float] = Field(0.0)
    pnl_zscore:             Optional[float] = Field(0.0)
    amount_zscore:          Optional[float] = Field(0.0)
    session_duration_zscore: Optional[float] = Field(0.0)

    # ── Pydantic Config ────────────────────────────────────────────────────────
    model_config = {"extra": "allow"}
    # extra="allow" means extra fields in the request body are accepted
    # (not validated, just passed through). This is useful if the event
    # contains additional fields we do not need for scoring.


# ─────────────────────────────────────────────────────────────────────────────
# Feature Detail Model
#
# Represents one feature in the top_features list of a ScoreResponse.
# ─────────────────────────────────────────────────────────────────────────────

class FeatureDetail(BaseModel):
    """A single feature with its raw and scaled values."""
    feature:      str   = Field(..., description="Feature name")
    raw_value:    float = Field(..., description="Original (unscaled) value")
    scaled_value: float = Field(..., description="Standardised value (z-score)")


# ─────────────────────────────────────────────────────────────────────────────
# Response Model
#
# The API returns one ScoreResponse per request. This is what the client
# (test_client.py, downstream services, dashboards) will receive.
# ─────────────────────────────────────────────────────────────────────────────

class ScoreResponse(BaseModel):
    """
    The complete anomaly scoring result for a single event.

    Includes the raw score, boolean flag, severity level, human-readable
    reasons, and the top features that contributed to the decision.
    """

    # ── Event identity ────────────────────────────────────────────────────────
    user_id:    str           = Field(..., description="User who generated the event")
    event_id:   Optional[str] = Field(None, description="Original event identifier")
    event_type: Optional[str] = Field(None, description="Event type (login, trade, withdrawal, ...)")
    timestamp:  Optional[str] = Field(None, description="Timestamp of the original event")

    # ── Scoring result ────────────────────────────────────────────────────────
    anomaly_score: float = Field(..., description="Raw LSTM reconstruction error (higher = more anomalous)")
    lstm_score:    float = Field(..., description="Same as anomaly_score (LSTM model output)")
    is_anomaly:    bool  = Field(..., description="True if the event exceeds the anomaly threshold")

    # ── Interpretation ────────────────────────────────────────────────────────
    severity: str       = Field(..., description="Severity level: LOW, MEDIUM, HIGH, or CRITICAL")
    verdict:  str       = Field(..., description="Human-readable verdict, e.g. '🚨 ANOMALY' or '✅ NORMAL'")
    reasons:  list[str] = Field(default_factory=list, description="Plain-English reasons for the flag")

    # ── Feature attribution ───────────────────────────────────────────────────
    top_features: list[FeatureDetail] = Field(
        default_factory=list,
        description="Top features by absolute scaled deviation from the training distribution"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Response
# ─────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response model for the GET /health endpoint."""
    status:       str  = Field(..., description="'ok' if the server is healthy")
    model_loaded: bool = Field(..., description="True if the scoring model is loaded and ready")
