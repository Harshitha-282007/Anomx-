# stream_config.py
#
# Shared configuration for the AnomX streaming pipeline.
#
# Both producer.py and consumer.py import from this file so that
# configuration is defined in exactly one place. If you need to change
# the topic name or broker address, you only need to change it here.
#
# ─────────────────────────────────────────────────────────────────────────────

# ─── Broker Connection ────────────────────────────────────────────────────────

# Address of the Redpanda broker started by docker-compose.yml.
# Format: "host:port"
# When running from the host machine, use Redpanda's external listener.
# The docker-compose file exposes external Kafka on localhost:19092.
BROKER_ADDRESS = "localhost:19092"

# ─── Topic ────────────────────────────────────────────────────────────────────

# The Kafka topic where events are published by the producer
# and consumed by the consumer.
TOPIC_NAME = "anomx-events"

# ─── Consumer Group ───────────────────────────────────────────────────────────

# Every consumer must belong to a consumer group.
# If multiple consumers have the same group_id, Kafka/Redpanda will
# load-balance the partitions between them (each partition to one consumer).
# For our single-consumer demo, this name does not matter much,
# but it is required.
CONSUMER_GROUP_ID = "anomx-scorer-group"

# ─── Producer Settings ───────────────────────────────────────────────────────

# How many seconds to wait between publishing events.
# Set to 0.0 to publish as fast as possible.
# Set to 0.1 for ~10 events per second (good for a visible demo).
# Set to 1.0 for one event per second (very slow, good for debugging).
PRODUCER_DELAY_SECONDS = 0.05  # 50ms → ~20 events per second

# Maximum number of events to publish before stopping.
# Set to None to stream the entire dataset.
# Set to e.g. 500 for a quick test run.
MAX_EVENTS = None

# ─── Serialisation ────────────────────────────────────────────────────────────

# We use UTF-8 encoded JSON strings as the message format.
# This is human-readable and easy to debug.
# In production you might use Avro or Protobuf for efficiency.
MESSAGE_ENCODING = "utf-8"

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# ─── Dataset Path ───────────────────────────────────────────────────────────

# Path to the processed features CSV from Week 4.
# The producer reads this file row by row and publishes each row as an event.
FEATURES_CSV_PATH = str((PROJECT_ROOT / "data" / "processed" / "features.csv").resolve())

# ─── Model Path ───────────────────────────────────────────────────────────

# Path to the directory containing the trained model artifacts.
# Expected files:
#   lstm_autoencoder.pt    — PyTorch model weights
#   lstm_scaler.pkl        — fitted StandardScaler
#   lstm_threshold.pkl     — float threshold value
MODEL_PATH = str((PROJECT_ROOT / "models" / "trained").resolve())

# ─── Kafka/Redpanda Producer Config ──────────────────────────────────────────

# These settings are passed directly to the kafka-python KafkaProducer.
PRODUCER_CONFIG = {
    "bootstrap_servers": [BROKER_ADDRESS],
    "value_serializer": None,   # we handle serialisation manually in producer.py
    "acks": 1,                  # wait for leader acknowledgement before continuing
    "retries": 3,               # retry up to 3 times on transient errors
    "request_timeout_ms": 10000,
}

# ─── Kafka/Redpanda Consumer Config ──────────────────────────────────────────

# These settings are passed directly to the kafka-python KafkaConsumer.
CONSUMER_CONFIG = {
    "bootstrap_servers": [BROKER_ADDRESS],
    "group_id": CONSUMER_GROUP_ID,
    "auto_offset_reset": "earliest",   # start from the beginning if no committed offset
    "enable_auto_commit": True,        # automatically commit offsets after processing
    "auto_commit_interval_ms": 1000,   # commit every 1 second
    "value_deserializer": None,        # we handle deserialisation manually in consumer.py
}
