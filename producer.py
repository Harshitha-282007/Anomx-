# producer.py
#
# AnomX Streaming Pipeline — Event Producer
#
# This script reads rows from the features.csv dataset and publishes each row
# as a JSON message to a Redpanda/Kafka topic. It simulates a live trading
# platform streaming events to the broker in real time.
#
# Prerequisites:
#   1. Redpanda is running: docker compose up -d
#   2. Dependencies installed: pip install -r requirements.txt
#
# Usage:
#   python producer.py
#   python producer.py --delay 0.1     # 100ms between events
#   python producer.py --max 200       # stop after 200 events
#
# ─────────────────────────────────────────────────────────────────────────────

import json
import math
import time
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pandas as pd
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, KafkaError

# Import shared config so we keep settings in one place
from stream_config import (
    BROKER_ADDRESS,
    TOPIC_NAME,
    PRODUCER_DELAY_SECONDS,
    MAX_EVENTS,
    FEATURES_CSV_PATH,
    MESSAGE_ENCODING,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: clean NaN / Inf values before JSON serialisation
# ─────────────────────────────────────────────────────────────────────────────

def clean_event(event: dict) -> dict:
    """
    Replace NaN and Inf values with 0.0.

    Standard JSON does not support NaN or Infinity. Python's json.dumps()
    raises ValueError if you try to serialise them. This function replaces
    them with 0.0 — consistent with how scorer.py handles missing values.

    Args:
        event: Dictionary representing one event (a row from features.csv).

    Returns:
        A new dictionary with NaN/Inf values replaced by 0.0.
    """
    cleaned = {}
    for key, value in event.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            cleaned[key] = 0.0
        else:
            cleaned[key] = value
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Helper: ensure the topic exists before publishing
# ─────────────────────────────────────────────────────────────────────────────

def ensure_topic_exists(broker: str, topic: str) -> None:
    """
    Create the Kafka topic if it does not already exist.

    Redpanda can auto-create topics on first publish, but explicitly creating
    it is safer and works even if auto-create is disabled.

    Args:
        broker: Broker address, e.g. "localhost:9092"
        topic:  Topic name, e.g. "anomx-events"
    """
    admin = KafkaAdminClient(bootstrap_servers=[broker])
    new_topic = NewTopic(
        name=topic,
        num_partitions=1,       # one partition is enough for a local demo
        replication_factor=1,   # single broker → can only replicate to 1
    )
    try:
        admin.create_topics([new_topic])
        print(f"[INFO] Created topic: {topic}")
    except TopicAlreadyExistsError:
        print(f"[INFO] Topic already exists: {topic}")
    finally:
        admin.close()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a KafkaProducer
# ─────────────────────────────────────────────────────────────────────────────

def build_producer(broker: str) -> KafkaProducer:
    """
    Create and return a KafkaProducer connected to the given broker.

    We do NOT use a value_serializer here — we manually convert each event
    to JSON bytes before calling producer.send(). This gives us full control
    over encoding and lets us handle NaN values ourselves.

    Args:
        broker: Broker address, e.g. "localhost:9092"

    Returns:
        A connected KafkaProducer instance.
    """
    return KafkaProducer(
        bootstrap_servers=[broker],
        acks=1,                 # wait for the leader broker to acknowledge
        retries=3,              # retry 3 times on transient errors
        request_timeout_ms=10000,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main producer logic
# ─────────────────────────────────────────────────────────────────────────────

def run_producer(
    csv_path: str = FEATURES_CSV_PATH,
    delay: float = PRODUCER_DELAY_SECONDS,
    max_events: int = MAX_EVENTS,
) -> None:
    """
    Load features.csv and publish each row as a JSON message to the topic.

    Events are published in chronological order (sorted by timestamp).
    After publishing, a small delay simulates realistic event throughput.

    Args:
        csv_path:   Path to features.csv from Week 4.
        delay:      Seconds to wait between publishing events.
        max_events: Stop after this many events. None = publish all.
    """
    # ── Load the dataset ──────────────────────────────────────────────────────
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"[ERROR] Features CSV not found at: {csv_file.resolve()}")
        print("        Update FEATURES_CSV_PATH in stream_config.py to point to your data.")
        return

    print(f"[INFO] Loading dataset from: {csv_file.resolve()}")
    df = pd.read_csv(csv_file)

    # Sort by timestamp so we replay events in chronological order
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
    print(f"[INFO] Loaded {len(df):,} events across {df['user_id'].nunique():,} users.")

    # Apply max_events limit
    if max_events is not None:
        df = df.head(max_events)
        print(f"[INFO] Limiting to first {max_events} events.")

    # ── Connect to broker ─────────────────────────────────────────────────────
    print(f"[INFO] Connecting to broker: {BROKER_ADDRESS}")
    ensure_topic_exists(BROKER_ADDRESS, TOPIC_NAME)
    producer = build_producer(BROKER_ADDRESS)
    print(f"[INFO] Connected. Publishing to topic: {TOPIC_NAME}")
    print(f"[INFO] Delay between events: {delay:.3f}s")
    print("-" * 60)

    # ── Publish events ────────────────────────────────────────────────────────
    published = 0
    errors = 0

    for idx, row in df.iterrows():
        # Convert row to plain Python dict (not numpy types)
        event = row.to_dict()

        # Clean NaN / Inf values so json.dumps() does not raise
        event = clean_event(event)

        # Serialise to UTF-8 JSON bytes
        message_bytes = json.dumps(event).encode(MESSAGE_ENCODING)

        # TODO for mentees:
        # Understand what happens here. producer.send() is non-blocking —
        # it queues the message internally and sends it in a background thread.
        # producer.flush() would wait for all queued messages to be delivered.

        try:
            producer.send(
                topic=TOPIC_NAME,
                value=message_bytes,
                key=str(event.get("user_id", "unknown")).encode(MESSAGE_ENCODING),
            )
            published += 1

            # Print a progress update every 50 events
            if published % 50 == 0:
                print(f"[INFO] Published {published:,} events...")

            # Throttle to simulate realistic throughput
            if delay > 0:
                time.sleep(delay)

        except KafkaError as e:
            print(f"[ERROR] Failed to publish event {idx}: {e}")
            errors += 1

    # Flush any remaining buffered messages before exiting
    print("[INFO] Flushing producer buffer...")
    producer.flush()
    producer.close()

    print("-" * 60)
    print(f"[DONE] Published {published:,} events to topic '{TOPIC_NAME}'.")
    if errors > 0:
        print(f"[WARN] {errors} events failed to publish.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="AnomX Event Producer — streams events from features.csv to Redpanda"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=PRODUCER_DELAY_SECONDS,
        help=f"Seconds between events (default: {PRODUCER_DELAY_SECONDS})"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=MAX_EVENTS,
        help="Maximum number of events to publish (default: all)"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=FEATURES_CSV_PATH,
        help=f"Path to features CSV (default: {FEATURES_CSV_PATH})"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_producer(
        csv_path=args.csv,
        delay=args.delay,
        max_events=args.max,
    )
