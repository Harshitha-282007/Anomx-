# AnomX — Real-Time Trader Behavior Anomaly Detection Engine

> Summer of Code 2026 • IIT Bombay

AnomX is a real-time anomaly detection engine for forex trading platforms. It detects suspicious trader behaviour by learning normal user activity from historical events and scoring incoming events in real time using unsupervised machine learning.

The project simulates an end-to-end production pipeline—from synthetic data generation and feature engineering to model training, event streaming, and online inference through a REST API.

---

## Features

- Synthetic forex trading dataset generator with configurable fraud injection
- Behavioural feature engineering pipeline
- Isolation Forest for point anomaly detection
- LSTM Autoencoder for sequential anomaly detection
- Real-time event streaming using Redpanda (Kafka API)
- FastAPI inference service
- Human-readable anomaly explanations
- Modular architecture with configurable pipeline

---

# Project Architecture

```
                          Synthetic Data Generator
                                     │
                                     ▼
                              Raw Events Dataset
                                     │
                                     ▼
                          Feature Engineering Pipeline
                                     │
                                     ▼
                            Engineered Features
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
          Isolation Forest                 LSTM Autoencoder
                    │                                 │
                    └──────────────┬──────────────────┘
                                   ▼
                           Saved Model Artifacts
                                   │
              ┌────────────────────┴───────────────────┐
              ▼                                        ▼
      Streaming Consumer                      FastAPI Server
              │                                        │
              └──────────────► ForexGuardScorer ◄──────┘
                                   │
                                   ▼
                      Human-readable Anomaly Alerts
```

---

# Repository Structure

```
AnomX/
│
├── configs/
│   └── config.yaml
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── generate_events.py
│   └── feature_engineering.py
│
├── models/
│   ├── isolation_forest.py
│   ├── lstm_autoencoder.py
│   ├── scorer.py
│   └── trained/
│
├── notebook/
│
├── producer.py
├── consumer.py
├── stream_config.py
│
├── main.py
├── schemas.py
│
├── docker-compose.yml
├── requirements.txt
├── RUN.md
└── README.md
```

---

# Dataset

The project generates a synthetic forex trading dataset consisting of user activities such as

- Login
- Trade
- Deposit
- Withdrawal
- Session
- KYC Updates

Each user is assigned a behavioural profile, and a configurable fraction of users are injected with realistic fraud scenarios.

Implemented anomaly scenarios include:

- IP hopping
- Wash trading
- Deposit–withdrawal cycling
- Bot trading
- Structuring
- Brute-force login attacks
- Dormant account withdrawals
- Consistent winning behaviour
- Device switching
- Suspicious KYC manipulation

---

# Feature Engineering

The feature engineering pipeline converts raw events into behavioural features suitable for anomaly detection.

Examples include

### Temporal Features

- Time since previous event
- Time since previous login
- Time since previous deposit

### Rolling Statistics

- Rolling trade volume
- Rolling PnL
- Rolling click rate

### Login Behaviour

- Unique IPs
- Unique countries
- Unique devices
- Rolling failed login attempts

### Financial Behaviour

- Rolling deposit totals
- Withdrawal-to-deposit ratio

### Burst Detection

- Events in last 5 minutes
- Events in last 30 minutes

### Behaviour Deviation

- User-specific z-scores
- Session statistics

---

# Machine Learning Models

## Isolation Forest

Used to identify point anomalies by isolating observations that significantly differ from normal behaviour.

---

## LSTM Autoencoder

Learns sequences of normal user behaviour and detects anomalies using reconstruction error.

The LSTM Autoencoder powers the live inference pipeline because behavioural fraud is often expressed as suspicious sequences of otherwise legitimate actions.

---

# Streaming Pipeline

Producer

- Reads engineered feature dataset
- Publishes events to Redpanda

Consumer

- Subscribes to streaming events
- Loads trained models
- Scores every incoming event
- Produces anomaly explanations

The streaming consumer and REST API both use the same scoring engine to ensure consistent predictions.

---

# REST API

The project exposes a FastAPI application.

### Health Check

```
GET /health
```

### Score Event

```
POST /score
```

Returns

- anomaly prediction
- anomaly score
- severity
- explanation

---

# Installation

Clone the repository

```bash
git clone https://github.com/<your-username>/anomx.git
cd anomx
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate

Windows

```powershell
.venv\Scripts\activate
```

Linux/macOS

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Running the Project

## 1. Generate synthetic dataset

```bash
python data/generate_events.py
```

---

## 2. Generate engineered features

```bash
python data/feature_engineering.py
```

---

## 3. Train models

Isolation Forest

```bash
python models/isolation_forest.py
```

LSTM Autoencoder

```bash
python models/lstm_autoencoder.py
```

---

## 4. Start Redpanda

```bash
docker compose up
```

---

## 5. Start FastAPI

```bash
uvicorn main:app --reload
```

Swagger UI

```
http://localhost:8000/docs
```

---

## 6. Start Streaming Demo

Producer

```bash
python producer.py
```

Consumer

```bash
python consumer.py
```

---

# Configuration

Most project parameters are configurable through

```
configs/config.yaml
```

This includes

- dataset size
- random seed
- anomaly fraction
- rolling window sizes
- model hyperparameters
- streaming configuration

---

# Tech Stack

| Category | Tools |
|-----------|------|
| Language | Python |
| ML | Scikit-learn, PyTorch |
| Data | Pandas, NumPy |
| API | FastAPI |
| Streaming | Redpanda / Kafka |
| Containerisation | Docker |
| Configuration | YAML |

---

# Future Improvements

- Online learning
- SHAP-based explanations
- Ensemble anomaly scoring
- Dashboard for live monitoring
- Graph-based fraud detection
- Real trading data integration

---

# Documentation

- `RUN.md` – Detailed execution guide
- `model.md` – Model selection and implementation notes

---

# License

Developed as part of the IIT Bombay Summer of Code 2026 programme.
