# consumer.py
#
# AnomX Streaming Pipeline — Event Consumer
#
# This script subscribes to the Redpanda/Kafka topic and processes each
# arriving event through the anomaly scoring pipeline. For every event flagged
# as anomalous, it prints a structured alert to the terminal.
#
# Prerequisites:
#   1. Redpanda is running: docker compose up -d
#   2. The scoring model artifacts from Week 7-8 exist at MODEL_PATH
#   3. Dependencies installed: pip install -r requirements.txt
#
# Usage:
#   python consumer.py
#
# Run this in one terminal while producer.py runs in another.
# Press Ctrl+C to stop.
#
# ─────────────────────────────────────────────────────────────────────────────

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from kafka import KafkaConsumer
from kafka.errors import KafkaError

# Import shared config
from stream_config import (
    BROKER_ADDRESS,
    TOPIC_NAME,
    CONSUMER_GROUP_ID,
    MODEL_PATH,
    MESSAGE_ENCODING,
)

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
    print("       Make sure the repository layout is intact and models/scorer.py is present.")
    SCORER_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Alert formatting
# ─────────────────────────────────────────────────────────────────────────────

def format_alert(result: dict) -> str:
    """
    Format a scorer result dictionary as a human-readable alert string.

    Args:
        result: The dictionary returned by ForexGuardScorer.score()

    Returns:
        A formatted multi-line string suitable for printing to the terminal.
    """
    # Severity emoji for quick visual scanning
    severity_icon = {
        "CRITICAL": "🔴",
        "HIGH":     "🟠",
        "MEDIUM":   "🟡",
        "LOW":      "🟢",
    }.get(result.get("severity", "LOW"), "⚪")

    lines = [
        "",
        "=" * 60,
        f"  {result.get('verdict', '?')}  {severity_icon} {result.get('severity', '?')}",
        "=" * 60,
        f"  User ID    : {result.get('user_id', 'N/A')}",
        f"  Event Type : {result.get('event_type', 'N/A')}",
        f"  Timestamp  : {result.get('timestamp', 'N/A')}",
        f"  LSTM Score : {result.get('anomaly_score', 0):.4f}",
        "",
        "  Reasons:",
    ]
    for reason in result.get("reasons", []):
        lines.append(f"    • {reason}")

    lines.append("")
    lines.append("  Top Contributing Features:")
    for feat in result.get("top_features", [])[:3]:
        lines.append(
            f"    • {feat['feature']:<35} raw={feat['raw_value']:.2f}  scaled={feat['scaled_value']:.2f}"
        )

    lines.append("=" * 60)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main consumer loop
# ─────────────────────────────────────────────────────────────────────────────

def run_consumer() -> None:
    """
    Connect to the broker, subscribe to TOPIC_NAME, and process messages.

    For each message:
      1. Deserialise JSON bytes → Python dict
      2. Pass to scorer.score(event)
      3. If is_anomaly is True, print a formatted alert
      4. Always print a short status line so you can see events flowing

    The consumer runs indefinitely until interrupted with Ctrl+C.
    """

    # ── Load the model ────────────────────────────────────────────────────────
    scorer = None
    if SCORER_AVAILABLE:
        model_dir = Path(MODEL_PATH)
        if not model_dir.exists():
            print(f"[WARN] Model directory not found: {model_dir.resolve()}")
            print("       Scoring will be skipped. Run week7-8/lstm_autoencoder.py first.")
        else:
            print(f"[INFO] Loading ForexGuardScorer from: {model_dir.resolve()}")
            try:
                scorer = ForexGuardScorer(model_path=str(model_dir))
                print("[INFO] Scorer loaded successfully.")
            except Exception as e:
                print(f"[WARN] Failed to load scorer: {e}")
                print("       Events will be displayed but not scored.")

    # ── Connect to broker ─────────────────────────────────────────────────────
    print(f"[INFO] Connecting to broker: {BROKER_ADDRESS}")
    print(f"[INFO] Subscribing to topic: {TOPIC_NAME}")
    print(f"[INFO] Consumer group: {CONSUMER_GROUP_ID}")
    print("[INFO] Waiting for events... (press Ctrl+C to stop)")
    print("-" * 60)

    # TODO for mentees:
    # Look at the consumer configuration carefully.
    # auto_offset_reset="earliest" means: if this consumer group has never
    # committed an offset before, start from the very beginning of the topic.
    # Change it to "latest" if you only want to see NEW messages published
    # after the consumer starts.

    consumer = KafkaConsumer(
        TOPIC_NAME,
        bootstrap_servers=[BROKER_ADDRESS],
        group_id=CONSUMER_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        auto_commit_interval_ms=1000,
        # consumer_timeout_ms=5000,  # uncomment to stop after 5s of no messages
    )

    # ── Event processing loop ─────────────────────────────────────────────────
    events_received = 0
    anomalies_detected = 0

    try:
        for message in consumer:
            # message.value is bytes; decode to JSON string, then to dict
            try:
                event = json.loads(message.value.decode(MESSAGE_ENCODING))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"[ERROR] Failed to deserialise message at offset {message.offset}: {e}")
                continue

            events_received += 1

            # Print a brief status line for every event so we see activity
            user_id     = event.get("user_id", "?")
            event_type  = event.get("event_type", "?")
            timestamp   = event.get("timestamp", "?")
            offset      = message.offset
            print(f"[offset={offset:>6}] {timestamp}  user={user_id:<8}  type={event_type:<12}", end="")

            # ── Score the event ───────────────────────────────────────────────
            if scorer is not None:
                try:
                    result = scorer.score(event)

                    if result.get("is_anomaly"):
                        anomalies_detected += 1
                        print(f"  score={result['anomaly_score']:.3f}  ← ANOMALY")
                        print(format_alert(result))
                    else:
                        score = result.get("anomaly_score", 0.0)
                        print(f"  score={score:.3f}  (normal)")

                except Exception as e:
                    print(f"  [scorer error: {e}]")
            else:
                # Scorer not available — just display the event
                amount = event.get("amount", 0)
                print(f"  amount={amount:.2f}  (no scorer)")

    except KeyboardInterrupt:
        print("\n[INFO] Consumer stopped by user.")

    finally:
        consumer.close()
        print(f"\n[DONE] Processed {events_received:,} events, detected {anomalies_detected:,} anomalies.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_consumer()
