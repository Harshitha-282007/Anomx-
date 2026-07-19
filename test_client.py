# test_client.py
#
# AnomX API — Test Client
#
# This script sends test events to the running FastAPI /score endpoint
# and prints the results in a readable format.
#
# Prerequisites:
#   1. The API is running: uvicorn main:app --reload
#   2. Dependencies installed: pip install -r requirements.txt
#
# Usage:
#   python test_client.py
#   python test_client.py --url http://localhost:8000
#   python test_client.py --csv ../data/features.csv --n 20
#
# The script can run in two modes:
#   1. Test mode (default): sends a set of predefined hand-crafted events
#   2. CSV mode (--csv flag): loads real events from features.csv and sends them
#
# ─────────────────────────────────────────────────────────────────────────────

import json
import math
import time
import argparse

import requests
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_API_URL = "http://localhost:8000"
SCORE_ENDPOINT  = "/score"
HEALTH_ENDPOINT = "/health"


# ─────────────────────────────────────────────────────────────────────────────
# Predefined test events
#
# These are hand-crafted events designed to trigger different scoring outcomes.
# They do NOT come from the real dataset — they are illustrative examples.
# ─────────────────────────────────────────────────────────────────────────────

TEST_EVENTS = [
    # Event 1: Normal trading activity — baseline behaviour
    {
        "user_id": "U0001",
        "event_id": "TEST_001",
        "event_type": "trade",
        "timestamp": "2024-06-01T10:30:00",
        "hour_of_day": 10,
        "day_of_week": 5,
        "is_weekend": 1.0,
        "trade_volume": 1.2,
        "pnl": 450.0,
        "amount": 5000.0,
        "login_success": 1.0,
        "failed_attempts": 0.0,
        "session_duration_mins": 22.0,
        "unique_ips_last_10_logins": 1.0,
        "unique_countries_last_10_logins": 1.0,
        "withdrawal_to_deposit_ratio": 0.3,
    },
    # Event 2: Suspicious withdrawal — large amount, immediate, unusual time
    {
        "user_id": "U0042",
        "event_id": "TEST_002",
        "event_type": "withdrawal",
        "timestamp": "2024-06-01T03:14:22",
        "hour_of_day": 3,
        "day_of_week": 6,
        "is_weekend": 1.0,
        "amount": 98000.0,
        "amount_zscore": 5.2,
        "is_immediate_withdrawal": 1.0,
        "withdrawal_to_deposit_ratio": 12.4,
        "login_success": 1.0,
        "failed_attempts": 0.0,
        "unique_ips_last_10_logins": 4.0,
        "unique_countries_last_10_logins": 3.0,
        "burst_count_5min": 8.0,
    },
    # Event 3: Multiple failed logins followed by login from new country
    {
        "user_id": "U0099",
        "event_id": "TEST_003",
        "event_type": "login",
        "timestamp": "2024-06-01T14:05:11",
        "hour_of_day": 14,
        "day_of_week": 1,
        "is_weekend": 0.0,
        "login_success": 1.0,
        "failed_attempts": 7.0,
        "rolling_failed_attempts_5": 7.0,
        "unique_ips_last_10_logins": 6.0,
        "unique_countries_last_10_logins": 5.0,
        "unique_devices_last_10_logins": 4.0,
        "timezone_gap_hours": 8.0,
        "amount": 0.0,
    },
    # Event 4: Normal trade during business hours — should score low
    {
        "user_id": "U0001",
        "event_id": "TEST_004",
        "event_type": "trade",
        "timestamp": "2024-06-01T11:00:00",
        "hour_of_day": 11,
        "day_of_week": 0,
        "is_weekend": 0.0,
        "trade_volume": 1.5,
        "pnl": 200.0,
        "amount": 4000.0,
        "login_success": 1.0,
        "failed_attempts": 0.0,
        "session_duration_mins": 18.0,
        "unique_ips_last_10_logins": 1.0,
        "unique_countries_last_10_logins": 1.0,
        "withdrawal_to_deposit_ratio": 0.2,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_separator(char: str = "─", width: int = 60) -> None:
    print(char * width)


def format_response(response_json: dict, event_index: int) -> None:
    """Print a scored event response in a readable format."""
    verdict    = response_json.get("verdict", "?")
    severity   = response_json.get("severity", "?")
    score      = response_json.get("anomaly_score", 0.0)
    user_id    = response_json.get("user_id", "?")
    event_type = response_json.get("event_type", "?")
    is_anomaly = response_json.get("is_anomaly", False)

    severity_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")

    print(f"\nEvent #{event_index + 1}")
    print_separator()
    print(f"  {verdict}  {severity_icon} {severity}")
    print(f"  User       : {user_id}")
    print(f"  Event Type : {event_type}")
    print(f"  Score      : {score:.4f}")
    print(f"  Is Anomaly : {is_anomaly}")

    reasons = response_json.get("reasons", [])
    if reasons:
        print("  Reasons    :")
        for r in reasons:
            print(f"               • {r}")

    top_features = response_json.get("top_features", [])
    if top_features:
        print("  Top Features:")
        for f in top_features[:3]:
            print(f"    {f['feature']:<35}  raw={f['raw_value']:.2f}  scaled={f['scaled_value']:.2f}")

    print_separator()


# ─────────────────────────────────────────────────────────────────────────────
# API interaction
# ─────────────────────────────────────────────────────────────────────────────

def check_health(base_url: str) -> bool:
    """
    Call GET /health and return True if the server is up and the model is loaded.
    """
    url = f"{base_url}{HEALTH_ENDPOINT}"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        print(f"[INFO] Health: {data}")
        if not data.get("model_loaded"):
            print("[WARN] Model is not loaded. Score results will be unavailable.")
            return False
        return True
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Cannot connect to {url}")
        print("        Is the server running? Try: uvicorn main:app --reload")
        return False


def score_event(base_url: str, event: dict, timeout: int = 10) -> dict:
    """
    Send a POST /score request and return the parsed JSON response.

    Args:
        base_url: Base URL of the running FastAPI server.
        event:    Event dictionary to score.
        timeout:  Request timeout in seconds.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        RuntimeError: If the request fails or returns a non-200 status.
    """
    url = f"{base_url}{SCORE_ENDPOINT}"

    # TODO for mentees:
    # requests.post() sends an HTTP POST request. The json= argument
    # automatically serialises the dict to JSON and sets the Content-Type header.
    # The response object has .status_code and .json() method.

    resp = requests.post(url, json=event, timeout=timeout)

    if resp.status_code == 503:
        raise RuntimeError("Server returned 503: model not loaded.")
    if resp.status_code == 422:
        raise RuntimeError(f"Server returned 422: invalid event data.\n{resp.json()}")
    if resp.status_code != 200:
        raise RuntimeError(f"Unexpected status {resp.status_code}: {resp.text}")

    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# Test runners
# ─────────────────────────────────────────────────────────────────────────────

def run_predefined_tests(base_url: str) -> None:
    """Send all predefined TEST_EVENTS to the API and print results."""
    print(f"\nRunning {len(TEST_EVENTS)} predefined test events against {base_url}...")

    for i, event in enumerate(TEST_EVENTS):
        try:
            result = score_event(base_url, event)
            format_response(result, i)
        except RuntimeError as e:
            print(f"\nEvent #{i + 1} failed: {e}")

        time.sleep(0.1)  # small pause between requests


def run_csv_tests(base_url: str, csv_path: str, n: int, delay: float) -> None:
    """
    Load events from features.csv and send the first n events to the API.

    Args:
        base_url: API base URL.
        csv_path: Path to features.csv.
        n:        Number of events to send.
        delay:    Seconds between requests.
    """
    print(f"\nLoading events from: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {csv_path}")
        return

    df = df.sort_values("timestamp").head(n)
    print(f"Sending {len(df)} events to {base_url}...")

    anomaly_count = 0

    for i, (_, row) in enumerate(df.iterrows()):
        event = row.to_dict()

        # Clean NaN values (same approach as producer.py)
        event = {
            k: (0.0 if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
            for k, v in event.items()
        }

        try:
            result = score_event(base_url, event)
            if result.get("is_anomaly"):
                anomaly_count += 1
                format_response(result, i)
            else:
                score = result.get("anomaly_score", 0.0)
                user  = result.get("user_id", "?")
                etype = result.get("event_type", "?")
                print(f"  [{i+1:>4}] {user:<8}  {etype:<15}  score={score:.3f}  ✅ normal")

        except RuntimeError as e:
            print(f"  [{i+1:>4}] Error: {e}")

        if delay > 0:
            time.sleep(delay)

    print(f"\n[DONE] Sent {len(df)} events. Detected {anomaly_count} anomalies.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="AnomX test client — calls the FastAPI /score endpoint"
    )
    parser.add_argument("--url",   default=DEFAULT_API_URL, help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--csv",   default=None,            help="Path to features.csv (enables CSV mode)")
    parser.add_argument("--n",     type=int, default=30,    help="Number of CSV events to send (default: 30)")
    parser.add_argument("--delay", type=float, default=0.05, help="Seconds between requests (default: 0.05)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print("=" * 60)
    print("  AnomX API Test Client")
    print("=" * 60)

    # Check server health first
    server_ok = check_health(args.url)
    if not server_ok:
        print("\nServer is not ready. Exiting.")
        raise SystemExit(1)

    if args.csv:
        run_csv_tests(args.url, args.csv, args.n, args.delay)
    else:
        run_predefined_tests(args.url)

    print("\nDone!")
