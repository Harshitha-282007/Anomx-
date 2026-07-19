# Run the AnomX Application

This repository runs from the root directory. It includes:
- `main.py` — FastAPI application
- `producer.py` — Kafka/Redpanda event producer
- `consumer.py` — Kafka/Redpanda event consumer and scorer
- `docker-compose.yml` — local Redpanda broker configuration
- `requirements.txt` — Python dependencies for the root application

## 1. Install dependencies

If you do not already have a virtual environment, create and activate one:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then install the requirements:

```powershell
pip install -r requirements.txt
```

## 2. Start Redpanda

From the repo root:

```powershell
docker compose up -d
```

Verify Redpanda is healthy:

```powershell
docker compose ps
```

## 3. Start the API

Run the FastAPI application from the root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open the docs in a browser:

```text
http://127.0.0.1:8000/docs
```

## 4. Test the API

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Score request example:

```powershell
curl -X POST http://127.0.0.1:8000/score -H "Content-Type: application/json" -d @sample_event.json
```

## 5. Run the event producer

Publish dataset events to Redpanda:

```powershell
.\.venv\Scripts\python.exe producer.py --max 100 --delay 0.1
```

## 6. Run the consumer

Start the scoring consumer:

```powershell
.\.venv\Scripts\python.exe consumer.py
```

The consumer will read events from the `anomx-events` topic, score them, and print alerts.

## 7. Optional: send test events to the API

```powershell
.\.venv\Scripts\python.exe test_client.py
```

## 8. Stop the application

```powershell
docker compose down
```
