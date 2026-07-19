# AnomX — Real-Time Trader Anomaly Detection Engine

**AnomX SOC 2026 | Final Project | ForexGuard Prototype**

---

## 1. What I built and why

At a forex brokerage, hundreds of things happen every second: logins, deposits, trades,
withdrawals, failed login attempts. Almost all of it is normal. Buried in that noise are a
small number of events that aren't — a login from a new country right after a deposit, a burst
of failed logins, a trade far bigger than anything that user has ever placed before.

I built AnomX to catch that small number automatically, rather than relying on a human
watching a dashboard. It looks at every event as it arrives, decides whether it fits the
pattern of that user's normal behavior, and — if it doesn't — produces a plain-English alert
explaining what triggered it and how severe it is.

This document walks through the decisions behind how it's put together: why the pipeline is
structured the way it is, why I picked the models I picked, why the numbers in `config.yaml`
are what they are, and what's still rough around the edges. The step-by-step "how to run it"
mechanics live in `RUN.md` — this file is about the *reasoning*, not the commands.

---

## 2. How the pieces fit together

I built this in five layers, each one feeding the next. This follows the same order the
mentorship program introduced the concepts in, week by week:

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
│                          4. Live Serving Layer (Weeks 9–10)                          │
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

**Why I structured it this way:**

- I deliberately kept training **offline and separate** from serving. The models train once on
  historical `features.csv`, get frozen into `.pkl` / `.pt` files, and the live system only ever
  *loads* those frozen artifacts — it never retrains on the fly. I did this because a live
  scoring engine that's silently re-training itself is a real production hazard: you lose the
  ability to say "this exact model version made this exact decision," which matters a lot in a
  compliance context.
- I put a **message broker (Redpanda) in the middle** instead of just calling the model in a
  loop, because that's the honest shape of the real problem — trading platforms don't hand you
  a CSV, they hand you a continuous stream. `producer.py` replays `features.csv` row-by-row with
  a small delay to simulate that stream, so the rest of the system behaves exactly like it would
  against a real live feed.
- I made sure both the **streaming consumer and the FastAPI app call the exact same
  `ForexGuardScorer` class** rather than each having their own copy of the scoring logic. Two
  independent implementations of "how do we decide if this is anomalous" would eventually drift
  apart and disagree with each other — I wanted one source of truth.

---

## 3. What's inside each file

```
.
├── README.md                     ← this file — decisions and reasoning
├── model_notes.md                ← why these specific models, in depth
├── RUN.md                        ← condensed step-by-step run commands (Windows/PowerShell)
├── docker-compose.yml            ← starts a local single-node Redpanda broker
├── requirements.txt               ← pinned Python dependencies
├── .gitignore                     ← keeps large/generated files out of git
│
├── configs/
│   └── config.yaml                ← every tunable number lives here (dataset size, model
│                                     hyperparameters, rolling windows, streaming delay, etc.)
│                                     I centralized these on purpose so a value is only ever
│                                     defined in one place.
│
├── data/
│   ├── generate_events.py         ← builds the synthetic dataset (Week 3)
│   ├── feature_engineering.py     ← turns raw events into ML-ready features (Week 4)
│   ├── raw/events.csv             ← the synthetic dataset (~50,000 events, 500 users)
│   └── processed/
│       ├── features.csv           ← output of feature_engineering.py
│       └── features_with_scores.csv ← features.csv with both models' scores attached
│
├── models/
│   ├── isolation_forest.py        ← trains/evaluates the Isolation Forest (Week 5–6)
│   ├── lstm_autoencoder.py        ← trains/evaluates the LSTM Autoencoder (Week 7–8)
│   ├── scorer.py                  ← ForexGuardScorer — the class that scores a live event
│   │                                 and turns it into a human-readable alert
│   └── trained/                   ← the frozen, saved model files
│       ├── isolation_forest.pkl
│       ├── lstm_autoencoder.pt
│       ├── lstm_scaler.pkl
│       └── lstm_threshold.pkl
│
├── notebook/
│   └── isolation_forest_hyperparam_search.ipynb  ← the exploratory search I used to land
│                                                    on the Isolation Forest hyperparameters
│
├── stream_config.py               ← one shared place for broker address, topic name, file
│                                     paths — both producer.py and consumer.py import from
│                                     here so the two scripts can't silently fall out of sync
├── producer.py                    ← reads features.csv, publishes each row as a JSON
│                                     message to Redpanda (Week 9)
├── consumer.py                    ← subscribes to Redpanda, scores every event, prints an
│                                     alert whenever something looks anomalous (Week 9)
│
├── main.py                        ← FastAPI app: GET /health, POST /score (Week 10)
├── schemas.py                     ← Pydantic request/response models for the API
├── test_client.py                 ← sends a handful of hand-crafted test events to the
│                                     running API — I wrote this so the API's behavior could
│                                     be demonstrated without needing Postman
└── utils/
    ├── logger.py                  ← shared logging setup (timestamps, consistent format)
    └── helpers.py                 ← reserved for shared code; currently unused
```

---

## 4. Decisions I made, and why

### 4.1 Isolation Forest `contamination` — why `0.013`

`contamination` tells the Isolation Forest what fraction of the training data to expect as
outliers — it's the single biggest lever controlling how aggressively it flags things.

I didn't just set this to match the dataset's overall anomaly-injection rate (~5%). Most of an
"anomalous user's" events are still completely ordinary — a user flagged as a wash trader still
logs in normally almost every time; only a handful of their trade events are actually the
suspicious ones. So the *event-level* anomaly rate sitting inside the data is meaningfully lower
than the *user-level* injection rate I configured in `generate_events.py`. I used
`notebook/isolation_forest_hyperparam_search.ipynb` to search a grid of contamination values
around the measured event-level rate and picked the one that maximized ROC-AUC (the label is
only used here for evaluation — the model itself never sees it during `.fit()`).

> ⚠️ **Open item:** the notebook currently references `configs/data.yaml` / `configs/model.yaml`,
> which don't exist — the project only has a single `configs/config.yaml`. I need to update the
> notebook's config-loading cells before it can be re-run end-to-end. Until then, `0.013` is
> carried over from an earlier run of that (currently broken) notebook rather than something
> freshly reproducible from this repo as it stands.

### 4.2 Severity thresholds — CRITICAL / HIGH / MEDIUM / LOW

The LSTM's anomaly score is a **reconstruction error (MSE)** — a raw number with no fixed,
universal scale. It's whatever scale falls out of *this* data and *this* trained model, so a
generic fixed cutoff (e.g. "6.0 = critical") only means anything once it's been checked against
how *my* scores actually distribute.

**Current status:** I carried the fixed cutoffs (`>6` CRITICAL, `>4` HIGH, `>2` MEDIUM, else
LOW) directly from the project brief's illustrative example, and I haven't yet recalibrated
them against my own score distribution. I already know this needs fixing — when I checked the
actual `lstm_score` column, MEDIUM and HIGH barely get used, because almost every score that
crosses 2.0 also crosses 6.0. The fix I'm planning is to compute the 98th / 99.5th / 99.9th
percentile cutoffs from the *training* score distribution and save them alongside
`lstm_threshold.pkl`, so severity is always relative to what "normal" looks like for this
specific model, not a number borrowed from an example.

### 4.3 Why the LSTM Autoencoder is the default model behind the live API

Both models are trained and saved, but `main.py` and `scorer.py` only wire up the LSTM
Autoencoder for live scoring — that was a deliberate choice, not an oversight. The reasoning is
in `model_notes.md`, but in short: the LSTM looks at *sequences* of a user's behavior, which
matters because a lot of real fraud here is a sequence of individually-plausible events, not a
single suspicious one.

### 4.4 Why kafka-python is still pinned to `1.4.7`

I'm keeping this version for now rather than upgrading. It's worth noting for whoever's reading
this that on Python 3.12 it fails on import (`ModuleNotFoundError: No module named
'kafka.vendor.six.moves'`), so it needs either Python 3.10/3.11, or swapping to
`kafka-python-ng` (a maintained, drop-in-compatible fork) if staying on 3.12+.

---

## 5. Where things stand — known rough edges

I'd rather be upfront about these than have them discovered later:

1. **`kafka-python==1.4.7` doesn't import cleanly on Python 3.12** (see 4.4). Streaming won't
   run on 3.12+ until this is addressed.
2. **Severity thresholds aren't percentile-calibrated yet** (see 4.2) — MEDIUM/HIGH are
   currently under-used.
3. **`.gitignore` is empty.** Large generated files (`.pt`, `.pkl`, `features*.csv`) should be
   excluded from version control going forward; they're included in this submission for
   convenience/reproducibility only.
4. **`scorer.py`'s `_explain()` only maps 6 of the ~46 features** to a specific human-readable
   reason. Anything outside that list falls back to a generic explanation ("Behavior deviates
   from historical pattern") instead of naming the actual feature involved.

---

## 6. Questions I kept coming back to while building this

1. Why use a message broker instead of reading straight from a database? (Think about what
   happens if 10,000 events land in the same second.)
2. What happens if the consumer crashes halfway through a stream — how does the broker's
   concept of an "offset" help recover?
3. Why does the model need to load once at startup instead of on every request?
4. What does a compliance analyst actually need from an alert to act on it in under 10 seconds?
5. If this had to scale to 10,000 events/second, which part of the architecture would I change
   first?

---

*AnomX SOC 2026 | Final Project | ForexGuard Prototype*
