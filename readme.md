# AnomX SOC 2026 — Final Project

## AnomX Prototype: Real-Time Trader Anomaly Detection Engine

---

> **This is your final deliverable for the AnomX mentorship program.**
>
> Everything you have built across Weeks 3–10 — synthetic data generation, feature engineering, Isolation Forest, LSTM Autoencoder, Redpanda streaming, and FastAPI — comes together here into a single, cohesive, production-style system.
>
> You are not being asked to learn anything new. You are being asked to **connect what you already know** into something that works end-to-end.

---

## Table of Contents

1. [Background & Motivation](#1-background--motivation)
2. [What You Will Build](#2-what-you-will-build)
3. [System Architecture](#3-system-architecture)
4. [Dataset Requirements](#4-dataset-requirements)
5. [Feature Engineering Requirements](#5-feature-engineering-requirements)
6. [Modeling Requirements](#6-modeling-requirements)
7. [Streaming Requirements](#7-streaming-requirements)
8. [API Requirements](#8-api-requirements)
9. [Alert Design](#9-alert-design)
10. [Deliverables Checklist](#10-deliverables-checklist)
11. [Evaluation Criteria](#11-evaluation-criteria)


---

## 1. Background & Motivation

Forex brokerages handle thousands of user actions every minute: logins from different devices, large deposits followed by immediate withdrawals, unusual trading volumes in the middle of the night, cascading failed login attempts before a successful one from a new country.

Most fraud does not look like a single suspicious event. It looks like a **pattern** — a sequence of individually plausible actions that, taken together, reveal intent.

Traditional rule-based systems (e.g., "flag any withdrawal over $50,000") are easy to circumvent and generate enormous false-positive rates. Modern compliance teams need a smarter approach: one that learns what *normal* looks like and automatically flags anything that deviates from it.

That is exactly what **ForexGuard** is.

You are building a real-time anomaly detection engine for a forex brokerage. The system monitors user activity across two surfaces:

- **Client Portal** — logins, KYC changes, deposits, withdrawals, session activity
- **Trading Terminal** — trade volume, lot sizes, margin usage, P&L patterns

When the engine detects suspicious behavior, it generates a **human-readable alert** that a compliance analyst can act on immediately.

---

## 2. What You Will Build

You will build a working prototype of the ForexGuard system. It must:

| Capability | Description |
|------------|-------------|
| **Data** | Use (or extend) the synthetic dataset from Week 3–4 (~50,000 events) |
| **Features** | Apply the feature engineering pipeline from Week 4 |
| **Models** | Train both a classical model and a deep learning model from Weeks 5–8 |
| **Streaming** | Replay events through a Redpanda broker using the pipeline from Weeks 9–10 |
| **API** | Serve anomaly scores via a FastAPI endpoint from Week 10 |
| **Alerts** | Return human-readable, explainable alerts for flagged events |

This is not a research project. The goal is a **working system** — one you can demo live by running it and showing events flow through it end-to-end.

---

## 3. System Architecture

Your final system must follow this architecture. Each component maps directly to a week of the program.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    AnomX — Final System Architecture                  │
│                                                                            │
│  ┌─────────────┐    ┌──────────────────────┐    ┌────────────────────┐    │
│  │  Week 3     │    │  Week 4              │    │  Weeks 5–8         │    │
│  │  Synthetic  │───►│  Feature Engineering │───►│  Model Training    │    │
│  │  Dataset    │    │  (46+ features)      │    │  - Isolation Forest│    │
│  │  50K events │    │                      │    │  - LSTM Autoencoder│    │
│  └─────────────┘    └──────────────────────┘    └────────┬───────────┘    │
│                                                           │ saved artifacts│
│                                                           ▼                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Weeks 9–10: Live Serving Layer                   │  │
│  │                                                                     │  │
│  │  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │  │
│  │  │ producer.py │─►│ Redpanda Broker  │─►│ consumer.py / API    │  │  │
│  │  │             │  │ (Docker)         │  │ ForexGuardScorer     │  │  │
│  │  │ Replays     │  │ anomx-events     │  │ LSTM + IF scoring    │  │  │
│  │  │ features.csv│  │ topic            │  │                      │  │  │
│  │  └─────────────┘  └──────────────────┘  └──────────┬───────────┘  │  │
│  │                                                     │              │  │
│  │                          ┌──────────────────────────┘              │  │
│  │                          ▼                                          │  │
│  │               ┌─────────────────────┐                              │  │
│  │               │   FastAPI (main.py) │                              │  │
│  │               │   POST /score       │ ← any client can call this   │  │
│  │               │   GET  /health      │                              │  │
│  │               │   → score + reasons │                              │  │
│  │               └─────────────────────┘                              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Dataset Requirements

You will use the synthetic dataset generated in Week 3. If you need to extend or regenerate it, the minimum requirements are:

### Volume
- **~50,000 total events** across all event types
- **At least 200 unique users**
- **Anomaly rate: 5–15%** (clearly labelled with `is_anomalous` and `anomaly_type`)

### Event Types Required

#### Client Portal Events
| Field | Description |
|-------|-------------|
| Login timestamps | When the user logged in |
| Login success / failure | Whether the attempt succeeded |
| IP address | May change across events |
| Country / device | Geographic and device diversity |
| Session duration | How long they stayed active |
| Page clicks | Activity level during session |
| KYC status changes | Account modifications |
| Deposit amount | Amount deposited |
| Withdrawal amount | Amount withdrawn |
| Withdrawal timing | Time between deposit and withdrawal |

#### Trading Terminal Events
| Field | Description |
|-------|-------------|
| Trade volume | Size of the trade |
| Lot size | Position size |
| Instrument | Currency pair or asset |
| PnL | Profit or loss |
| Margin used | Leverage applied |
| Trade duration | How long the position was held |
| Trade timing | Time of day |

### Anomaly Types to Include

Your dataset must include at least the following anomaly patterns:

1. **Credential stuffing** — Many failed logins from multiple IPs in a short window
2. **Account takeover** — Sudden login from a new country/device after a long gap
3. **Rapid deposit-withdrawal** — Large deposit immediately followed by withdrawal
4. **Unusual trading** — Abnormally large lot sizes or trade volumes at unusual hours
5. **Session anomaly** — Extremely short or extremely long sessions with high click rates

---

## 5. Feature Engineering Requirements

Apply the feature engineering pipeline from Week 4. Your feature set must include **at minimum** the following categories. You may add more.

### Time-Based Features
- `hour_of_day` — hour when event occurred (0–23)
- `day_of_week` — day of week (0=Monday)
- `is_weekend` — binary flag
- `is_night_trade` — binary flag for trades outside business hours
- `time_since_last_event_sec` — seconds since previous event for this user
- `time_since_last_login_sec` — seconds since last login
- `time_since_last_deposit_sec` — seconds since last deposit

### Session / Login Features
- `login_success` — binary
- `failed_attempts` — number of failed attempts before success
- `timezone_gap_hours` — deviation from user's typical timezone
- `session_duration_mins` — session length
- `page_clicks` — total clicks in session
- `click_rate_per_min` — clicks per minute

### Trading Features
- `lot_size`, `trade_volume`, `pnl`, `margin_used`, `trade_duration_seconds`
- `trade_volume_vs_baseline` — volume relative to user's rolling average

### Financial Features
- `amount` — deposit or withdrawal amount
- `is_immediate_withdrawal` — 1 if withdrawal within N hours of deposit
- `withdrawal_to_deposit_ratio` — ratio of recent withdrawals to deposits

### Rolling Window Features (Critical)
For each key metric (`trade_volume`, `pnl`, `click_rate`), compute:
- 5-event rolling mean and standard deviation
- 10-event rolling mean and standard deviation
- 30-event rolling mean and standard deviation

### Behavioral Deviation Features
- `burst_count_5min` — events from this user in last 5 minutes
- `burst_count_30min` — events from this user in last 30 minutes
- `unique_ips_last_10_logins` — IP diversity score
- `unique_countries_last_10_logins` — geographic diversity
- `unique_devices_last_10_logins` — device diversity
- `rolling_failed_attempts_5` — failed logins in last 5 attempts

### Z-Score Features
- `trade_vol_zscore` — standard deviations from user's mean trade volume
- `pnl_zscore` — standard deviations from user's mean PnL
- `amount_zscore` — standard deviations from user's mean transaction amount
- `session_duration_zscore` — standard deviations from user's mean session length

---

## 6. Modeling Requirements

You must train and save **both** of the following models. The API should use the LSTM Autoencoder by default.

### 6.1 Baseline Model — Isolation Forest

From Week 5–6:
- Train on the full feature set (46+ features)
- Save the fitted pipeline (scaler + model) using `joblib`
- Evaluate with ROC-AUC, Average Precision, and a Confusion Matrix
- **Justify** your contamination parameter choice in a comment or README


### 6.2 Advanced Model — LSTM Autoencoder

From Week 7–8:
- Train only on **normal** sequences (unsupervised approach)
- Sequence length: 10 events per user
- Architecture: LSTM Encoder → Latent Vector → LSTM Decoder
- Anomaly score: mean squared reconstruction error (MSE)
- Save: model weights (`.pt`), scaler (`.pkl`), threshold (`.pkl`)
- Evaluate with ROC-AUC and a reconstruction error distribution plot


### 6.3 Model Selection Justification

In your README or a separate `model_notes.md`, answer:
1. Why is an unsupervised approach preferred for this problem?
2. What is the advantage of the LSTM Autoencoder over the Isolation Forest for sequential data?
3. What does the reconstruction error threshold represent, and how did you choose it?

---

## 7. Streaming Requirements

From Week 9:

Your system must demonstrate a working streaming pipeline. This means:

### Producer
- Reads events from `features.csv` (sorted by timestamp)
- Publishes each event as a JSON message to a Redpanda topic
- Configurable delay between events (default: 50ms)
- Handles NaN values before serialisation

### Broker
- Single-node Redpanda running via Docker Compose
- Topic: `anomx-events` (or your own name — document it)
- Started with `docker compose up -d`

### Consumer
- Subscribes to the topic
- Passes each event to the `ForexGuardScorer`
- Prints a formatted alert for every event where `is_anomaly = True`
- Continues running indefinitely (Ctrl+C to stop)

### Demo Requirement
During your final presentation, you must show **two terminals open simultaneously**:
- Terminal 1: `python producer.py` publishing events
- Terminal 2: `python consumer.py` (or `uvicorn main:app`) receiving and scoring them
- At least **one ANOMALY alert must appear** during the live demo

---

## 8. API Requirements

From Week 10:

Your FastAPI application must expose the following:

### Endpoints

#### `GET /health`
Returns whether the server is up and the model is loaded.

```json
{
  "status": "ok",
  "model_loaded": true
}
```

#### `POST /score`
Accepts a single event and returns an anomaly score with explanation.

**Request body** (abbreviated — full schema in `schemas.py`):
```json
{
  "user_id": "U0042",
  "event_type": "withdrawal",
  "amount": 98000.0,
  "hour_of_day": 3,
  "failed_attempts": 0,
  "unique_ips_last_10_logins": 4,
  "withdrawal_to_deposit_ratio": 12.4,
  "...": "... (all 46 features)"
}
```

**Response**:
```json
{
  "user_id": "U0042",
  "event_type": "withdrawal",
  "anomaly_score": 7.32,
  "is_anomaly": true,
  "severity": "CRITICAL",
  "verdict": "🚨 ANOMALY",
  "reasons": [
    "Unusual transaction amount",
    "Abnormal withdrawal behaviour"
  ],
  "top_features": [
    { "feature": "amount",                     "raw_value": 98000.0, "scaled_value": 5.21 },
    { "feature": "withdrawal_to_deposit_ratio", "raw_value": 12.4,    "scaled_value": 4.87 }
  ]
}
```

### Requirements
- Model must be loaded **once at startup** (not on every request)
- Use Pydantic models for both request and response
- `/docs` must be accessible and show all endpoints correctly
- Return HTTP 503 if the model is not loaded
- Return HTTP 422 if the request body is invalid

---

## 9. Alert Design

Every anomaly flagged by your system must produce a **human-readable alert**. A good alert answers four questions instantly:

1. **Who?** — Which user triggered it
2. **What?** — What type of event
3. **How bad?** — Severity level (LOW / MEDIUM / HIGH / CRITICAL)
4. **Why?** — Two or three plain-English reasons

### Severity Thresholds

Define severity based on your anomaly score distribution. As a reference starting point:

| Score Range | Severity |
|-------------|----------|
| score > 6.0 | CRITICAL |
| score > 4.0 | HIGH     |
| score > 2.0 | MEDIUM   |
| score ≤ 2.0 | LOW      |

You must justify your thresholds in the README (e.g., based on percentile of training score distribution).

### Feature Contribution Explainability

For each alert, identify the **top 3–5 features** with the highest absolute scaled deviation from normal. Map each feature name to a plain-English description.

Example mappings:

| Feature Name | Human-Readable Description |
|---|---|
| `amount` | Unusual transaction amount |
| `withdrawal_to_deposit_ratio` | Abnormal withdrawal behaviour |
| `failed_attempts` | Multiple failed login attempts |
| `burst_count_5min` | High activity burst detected |
| `unique_countries_last_10_logins` | Logins from multiple countries |
| `hour_of_day` | Activity at unusual time of day |

You do **not** need to implement SHAP for this project. The scaled-magnitude approach from `Explainable_Alerts.md` is sufficient.

---

## 10. Deliverables Checklist

Use this checklist to confirm your project is complete before submission.

### Code & Structure
- [ ] Clean GitHub repository (public or shared with mentor)
- [ ] `README.md` at the root explaining setup, architecture, and how to run
- [ ] `docker-compose.yml` for running Redpanda locally
- [ ] `requirements.txt` (all dependencies pinned)
- [ ] Code is commented and readable

### Data & Features
- [ ] Synthetic dataset with ~50,000 events
- [ ] At least 5 anomaly types represented
- [ ] Feature engineering pipeline producing 30+ features
- [ ] `features.csv` (processed) committed or reproducible via a script

### Models
- [ ] Isolation Forest trained and saved (`isolation_forest.pkl`)
- [ ] LSTM Autoencoder trained and saved (`lstm_autoencoder.pt`, `lstm_scaler.pkl`, `lstm_threshold.pkl`)
- [ ] Evaluation report for both models (ROC-AUC, confusion matrix)
- [ ] Model selection justification written

### Streaming
- [ ] `producer.py` publishes events to Redpanda
- [ ] `consumer.py` reads events and scores them
- [ ] `docker-compose.yml` starts Redpanda correctly
- [ ] At least one anomaly alert visible in consumer output

### API
- [ ] FastAPI app with `GET /health` and `POST /score`
- [ ] Request body validated with Pydantic
- [ ] Response includes score, severity, reasons, and top_features
- [ ] `/docs` accessible in browser
- [ ] `test_client.py` or equivalent demonstrates a working call

---

## 11. Evaluation Criteria

Your final project will be evaluated on the following dimensions:

| Dimension | Weight | What We Are Looking For |
|-----------|--------|------------------------|
| **System Completeness** | 25% | Does the full pipeline run end-to-end without errors? |
| **Model Quality** | 20% | Are ROC-AUC targets met? Is model selection justified? |
| **Feature Engineering** | 15% | Are features meaningful and correctly computed? |
| **Code Quality** | 15% | Is the code readable, commented, and well-structured? |
| **Alert Design** | 15% | Are alerts human-readable and actionable? |
| **Presentation & Explanation** | 10% | Can you explain what the system does and why it works? |




### Repository Structure (Recommended)

```
AnomX_SOC-YourRoll/
│
├── README.md                   ← Setup instructions + architecture overview
├── docker-compose.yml          ← Redpanda broker
├── requirements.txt            ← All dependencies
├── .gitignore                  ← Exclude .pt, .pkl, large CSVs
│
├── data/
│   ├── generate_dataset.py     ← Synthetic data generator (Week 3)
│   └── feature_engineering.py ← Feature pipeline (Week 4)
│
├── models/
│   ├── isolation_forest.py     ← IF training and evaluation (Week 5-6)
│   ├── lstm_autoencoder.py     ← LSTM training and evaluation (Week 7-8)
│   └── scorer.py               ← ForexGuardScorer class
│
├── streaming/
│   ├── stream_config.py        ← Shared config
│   ├── producer.py             ← Event producer (Week 9)
│   └── consumer.py             ← Event consumer (Week 9)
│
└── api/
    ├── main.py                 ← FastAPI app (Week 10)
    ├── schemas.py              ← Pydantic models (Week 10)
    └── test_client.py          ← Test script (Week 10)
```

*AnomX SOC 2026 | Final Project | AnomX Prototype*
