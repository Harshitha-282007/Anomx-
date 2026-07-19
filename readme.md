# AnomX — Real-Time Trader Anomaly Detection Engine

**AnomX SOC 2026 | Final Project | ForexGuard Prototype**

A real-time system that watches trader behavior event-by-event and flags fraud as it happens —
unusual logins, wash trading, deposit/withdrawal cycling, and more — with a plain-English reason
attached to every alert.

> 📄 For the full model comparison (real ROC-AUC/precision numbers, per-anomaly-type breakdown,
> and threshold justification), see **[`model_notes.md`](./model_notes.md)**.
> For condensed copy-paste run commands, see **[`RUN.md`](./RUN.md)**.

---

## Table of Contents
1. [Problem & Approach](#1-problem--approach)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Setup](#4-setup)
5. [Configuration](#5-configuration)
6. [How to Run](#6-how-to-run)
7. [Key Design Decisions](#8-key-design-decisions)

---

## 1. Problem & Approach

At a forex brokerage, hundreds of events happen every second — logins, deposits, trades,
withdrawals, failed login attempts. Almost all of it is normal. Buried in that noise are a
small number of events that aren't: a login from a new country right after a deposit, a burst
of failed logins, a trade far bigger than anything that user has ever placed before. A human
analyst can't watch every event by hand, and simple threshold rules ("flag withdrawals over
$50k") are easy to game and produce too many false positives.

AnomX takes a different approach: it learns what *normal* looks like per user, from historical
behavior, without ever being told in advance which events are fraudulent (unsupervised
learning — see [Section 8.1](#81-why-unsupervised)). It then scores every new event in real
time against that learned notion of normal, and produces a human-readable alert — with a
severity level and specific reasons — whenever something deviates enough to matter.

---

## 2. Architecture

The system is built in five layers, each one feeding the next:

```
┌──────────────────────┐     ┌───────────────────────┐     ┌───────────────────────────┐
│   1. Synthetic Data   │────▶│  2. Feature Engineering │────▶│   3. Model Training        │
│  generate_events.py   │     │  feature_engineering.py │     │  isolation_forest.py       │
│  → data/raw/events.csv│     │  → data/processed/       │     │  lstm_autoencoder.py       │
│                       │     │     features.csv         │     │  → models/trained/*.pkl/.pt│
└──────────────────────┘     └───────────────────────┘     └────────────┬──────────────┘
                                                                          │
                                                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              4. Live Serving Layer                                   │
│                                                                                       │
│   producer.py  ──publishes JSON events──▶  Redpanda broker (Docker, topic:           │
│   (reads features.csv,                      "anomx-events")                          │
│    replays it like a live feed)                        │                              │
│                                                          ▼                              │
│                                              consumer.py  ──uses──▶  ForexGuardScorer  │
│                                              (subscribes to topic,     (models/scorer.py)│
│                                               prints alerts to        loads LSTM model   │
│                                               the terminal)           once at startup    │
│                                                                                       │
│   Separately, any client can also call:                                             │
│                                              main.py (FastAPI)                        │
│                                              POST /score   → same ForexGuardScorer     │
│                                              GET  /health                              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Why it's built this way:**

- **Training is offline and frozen, not live.** Models train once on historical
  `features.csv`, get saved to disk (`.pkl` / `.pt`), and the live system only ever *loads*
  those frozen artifacts — it never retrains on the fly. This means every scoring decision is
  traceable to a specific, fixed model version, which matters in a compliance context.
- **A message broker sits in the middle of serving**, rather than calling the model in a
  simple loop, because that's the honest shape of the real problem: trading platforms hand you
  a continuous stream, not a static file. `producer.py` replays `features.csv` row-by-row with
  a configurable delay to simulate that stream.
- **The streaming consumer and the FastAPI app call the exact same `ForexGuardScorer`
  class.** Two independent copies of the scoring logic would eventually drift out of sync with
  each other — there's a single source of truth for "what counts as anomalous."

---

## 3. Repository Structure

```
.
├── README.md                     ← this file
├── model_notes.md                ← full model comparison, with real computed numbers
├── RUN.md                        ← condensed run commands
├── docker-compose.yml            ← starts a local single-node Redpanda broker
├── requirements.txt               ← pinned Python dependencies
├── .gitignore
│
├── configs/
│   └── config.yaml                ← every tunable number (dataset size, model
│                                     hyperparameters, rolling windows, streaming delay)
│
├── data/
│   ├── generate_events.py         ← builds the synthetic dataset
│   ├── feature_engineering.py     ← raw events → ML-ready features
│   ├── raw/events.csv             ← synthetic dataset (~50,000 events, 500 users)
│   └── processed/
│       ├── features.csv
│       └── features_with_scores.csv
│
├── models/
│   ├── isolation_forest.py        ← trains/evaluates the Isolation Forest
│   ├── lstm_autoencoder.py        ← trains/evaluates the LSTM Autoencoder
│   ├── scorer.py                  ← ForexGuardScorer — scores a live event, builds an alert
│   └── trained/                   ← frozen, saved model files
│       ├── isolation_forest.pkl
│       ├── lstm_autoencoder.pt
│       ├── lstm_scaler.pkl
│       └── lstm_threshold.pkl
│
├── notebook/
│   └── isolation_forest_hyperparam_search.ipynb
│
├── stream_config.py               ← shared broker address / topic / paths for producer+consumer
├── producer.py                    ← replays features.csv onto the Redpanda topic
├── consumer.py                    ← subscribes to the topic, scores events, prints alerts
│
├── main.py                        ← FastAPI app: GET /health, POST /score
├── schemas.py                     ← Pydantic request/response models
├── test_client.py                 ← sends sample events to the running API
└── utils/
    ├── logger.py
    └── helpers.py
```

---

## 4. Setup

**Prerequisites:**
- Python **3.10 or 3.11** (see [Known Limitations](#9-known-limitations) re: 3.12+)
- Docker Desktop (or Docker Engine on Linux)
- ~500 MB free disk space

**Install steps** (run from the project root):

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

Verify the install:
```bash
python -c "import fastapi, torch, sklearn, kafka; print('OK')"
```

---

## 5. Configuration

All tunable values live in **`configs/config.yaml`** — nothing is hardcoded elsewhere. Notable
settings:

| Key | Value | What it controls |
|---|---|---|
| `data.n_events` | 50000 | Size of the synthetic dataset |
| `data.n_users` | 500 | Number of simulated users |
| `data.anomaly_fraction` | 0.05 | Fraction of users with an injected fraud pattern |
| `features.rolling_windows` | [5, 10, 30] | Rolling-window sizes for feature engineering |
| `model.isolation_forest.contamination` | 0.013 | Expected outlier fraction (see [8.2](#82-isolation-forest-contamination--0013)) |
| `model.lstm_autoencoder.sequence_length` | 10 | Events per sequence the LSTM looks at |
| `model.lstm_autoencoder.threshold_percentile` | 98 | Anomaly cutoff (see [8.3](#83-lstm-anomaly-threshold--98th-percentile)) |
| `streaming.delay_seconds` | 0.1 | Delay between events the producer publishes |

To regenerate data or retrain a model with different settings, edit this file first — every
downstream script reads from it, so there's one place to change a value.

---

## 6. How to Run

The trained models and processed data are already included in this submission, so **Steps 1–2
below can be skipped** unless you want to regenerate everything from scratch.

### Step 1 (optional) — Regenerate the dataset and features
```bash
python data/generate_events.py          # → data/raw/events.csv
python data/feature_engineering.py      # → data/processed/features.csv
```

### Step 2 (optional) — Retrain the models
```bash
python models/isolation_forest.py       # trains + evaluates Isolation Forest
python models/lstm_autoencoder.py       # trains + evaluates LSTM Autoencoder
```
Each script prints an evaluation report (ROC-AUC, Average Precision, confusion matrix) as it
runs.

### Step 3 — Start the message broker
```bash
docker compose up -d
docker compose ps        # confirm the "redpanda" service is healthy before continuing
```

### Step 4 — Start the API
```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```
Open **http://127.0.0.1:8000/docs** — FastAPI's interactive docs page, generated from
`schemas.py`, with a "Try it out" button for `GET /health` and `POST /score`.

Quick check:
```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok","model_loaded":true}
```

### Step 5 — Run the live streaming demo
Open **two terminals**.

**Terminal 1 — producer** (simulates events arriving live):
```bash
python producer.py --max 500 --delay 0.05
```

**Terminal 2 — consumer** (watches the stream and scores each event):
```bash
python consumer.py
```

Within a few seconds you should see the consumer print an alert whenever an anomalous event
streams past — see [Section 7](#7-sample-output) for what that looks like. Press `Ctrl+C` in
the consumer terminal to stop.

### Step 6 (optional) — Exercise the API directly
```bash
python test_client.py
```
Sends a handful of hand-crafted example events (normal and anomalous) straight to `POST
/score` and prints the responses, without needing Postman or manual `curl` commands.

### Step 7 — Shut down
```bash
docker compose down
```

---

## 8. Key Design Decisions

- Training and inference are separated to keep deployed models reproducible.
- The same scoring engine is shared between streaming inference and the REST API.
- The LSTM Autoencoder is used for live inference because it models behavioural sequences rather than isolated events.
- Configuration values are centralized in `configs/config.yaml`.

Further implementation details and evaluation results are available in `model_notes.md`.

---

*AnomX SOC 2026 | Final Project | ForexGuard Prototype*
