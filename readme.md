# AnomX — Real-Time Trader Anomaly Detection Engine

**Summer of Code 2026 | IIT Bombay**

AnomX is a real-time anomaly detection system for forex trading platforms. It detects suspicious trader behaviour from streaming events using unsupervised machine learning and exposes the same inference engine through both a streaming consumer and a REST API.

> **Additional documentation**
>
> - `RUN.md` – concise execution commands
> - `model_notes.md` – model comparison, evaluation metrics and implementation notes

---

# Table of Contents

1. Overview
2. Architecture
3. Repository Structure
4. Prerequisites
5. Installation
6. Configuration
7. Running the Project
8. API
9. Sample Workflow
10. Design Decisions
11. Limitations

---

# 1. Overview

The project simulates a production-style fraud detection pipeline.

Instead of relying on manually written rules, AnomX learns normal user behaviour from historical trading events and scores every incoming event against that baseline.

The pipeline consists of five stages:

1. Generate synthetic forex events.
2. Engineer behavioural features.
3. Train anomaly detection models.
4. Stream events through Redpanda.
5. Score events in real time.

Training is performed offline. During inference, previously trained models are loaded once and reused for all predictions.

---

# 2. Architecture

```text
                 Synthetic Event Generation
                           │
                           ▼
                  data/raw/events.csv
                           │
                           ▼
                  Feature Engineering
                           │
                           ▼
             data/processed/features.csv
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
    Isolation Forest              LSTM Autoencoder
            │                             │
            └──────────────┬──────────────┘
                           ▼
                  Saved Model Artifacts
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
     consumer.py                     FastAPI (main.py)
          │                                 │
          └──────────────► ForexGuardScorer ◄──────────────┘
                           │
                           ▼
                    Anomaly Alerts
```

### Architecture Notes

- Dataset generation, feature engineering and model training are completely offline.
- Both the streaming consumer and FastAPI server use the same `ForexGuardScorer` implementation to ensure identical scoring logic.
- Redpanda is used as the message broker to simulate a real event stream.

---

# 3. Repository Structure

```text
.
├── README.md
├── RUN.md
├── model_notes.md
├── requirements.txt
├── docker-compose.yml
│
├── configs/
│   └── config.yaml
│
├── data/
│   ├── generate_events.py
│   ├── feature_engineering.py
│   ├── raw/                 # generated dataset
│   └── processed/           # engineered features
│
├── models/
│   ├── isolation_forest.py
│   ├── lstm_autoencoder.py
│   ├── scorer.py
│   └── trained/             # generated model artifacts
│
├── notebook/
│
├── producer.py
├── consumer.py
├── stream_config.py
├── main.py
├── schemas.py
├── test_client.py
└── utils/
```

---

# 4. Prerequisites

- Python 3.10 or 3.11
- Docker Desktop (or Docker Engine)
- Git

> Python 3.12 is currently not recommended because `kafka-python==1.4.7` is incompatible.

---

# 5. Installation

Clone the repository

```bash
git clone <repository-url>
cd anomx
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate it

Windows

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Verify installation

```bash
python -c "import fastapi, torch, sklearn; print('Environment OK')"
```

---

# 6. Configuration

Project configuration is centralized in

```text
configs/config.yaml
```

Important settings include:

- dataset size
- number of simulated users
- anomaly fraction
- rolling-window sizes
- model hyperparameters
- streaming configuration

Any changes to these values should be made before regenerating the dataset or retraining the models.

---

# 7. Running the Project

## Step 1 — Generate synthetic events (optional)

Skip this step if generated data is already included.

```bash
python data/generate_events.py
```

Output:

```text
data/raw/events.csv
```

---

## Step 2 — Build engineered features (optional)

```bash
python data/feature_engineering.py
```

Output:

```text
data/processed/features.csv
```

---

## Step 3 — Train models (optional)

Isolation Forest

```bash
python models/isolation_forest.py
```

LSTM Autoencoder

```bash
python models/lstm_autoencoder.py
```

Trained models are saved under

```text
models/trained/
```

---

## Step 4 — Start Redpanda

```bash
docker compose up -d
```

Verify that the broker is running before continuing.

---

## Step 5 — Start the API

```bash
uvicorn main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## Step 6 — Run the streaming pipeline

Open two terminals.

Producer

```bash
python producer.py
```

Consumer

```bash
python consumer.py
```

The producer publishes engineered events to Redpanda.

The consumer reads each event, scores it using the trained models, and prints anomaly alerts.

---

## Step 7 — Test the API (optional)

```bash
python test_client.py
```

---

## Step 8 — Stop services

```bash
docker compose down
```

---

# 8. API

## Health

```
GET /health
```

## Score

```
POST /score
```

The API loads the trained models during startup and returns anomaly predictions together with severity and explanation.

---

# 9. Sample Workflow

```
generate_events.py
        │
        ▼
events.csv
        │
        ▼
feature_engineering.py
        │
        ▼
features.csv
        │
        ▼
Train Models
        │
        ▼
Start Redpanda
        │
        ▼
Run producer.py
        │
        ▼
Run consumer.py
        │
        ▼
Receive anomaly alerts
```

---

# 10. Design Decisions

- Training and inference are separated to keep deployed models reproducible.
- The same scoring engine is shared between streaming inference and the REST API.
- The LSTM Autoencoder is used for live inference because it models behavioural sequences rather than isolated events.
- Configuration values are centralized in `configs/config.yaml`.

Further implementation details and evaluation results are available in `model_notes.md`.

---

# 11. Current Limitations

- Python 3.12 is not supported with the current Kafka client.
- The dataset is synthetically generated.
- Explanation mapping currently covers only a subset of engineered features.
- Model retraining is offline; online learning is not implemented.

---

## License

Developed as part of IIT Bombay Summer of Code 2026.
