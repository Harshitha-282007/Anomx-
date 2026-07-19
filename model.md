# model_notes.md — Model Comparison, Backed by Actual Numbers

## 1. Headline comparison: Isolation Forest vs. LSTM Autoencoder

| | Isolation Forest | LSTM Autoencoder |
|---|---|---|
| ROC-AUC (full dataset) | **0.530** | **0.710** |
| Average Precision | **0.136** | **0.424** |
| Precision / Recall @ operating threshold | 0.36 / 0.09 | 0.87 / 0.33 (at 98th-pct threshold)|

The Isolation Forest is barely better than random guessing (0.530 ROC-AUC — 0.5 is chance
level) on this feature set. That's a much weaker result than I expected going in, and worth
being blunt about rather than describing it in the usual "solid classical baseline" language.
The LSTM Autoencoder is clearly the stronger model here — 0.71 ROC-AUC, and roughly 3x the
Average Precision.

**Why the Isolation Forest likely underperforms this much:** it scores each row independently
using the 46 features as-is, and a lot of those features (rolling means/stds, z-scores) are
already *derived from* short-term history — meaning IF is looking at pre-summarized signals
without ever seeing the raw sequence they came from. It has no way to tell *when* a summary
statistic itself resulted from an unusual pattern versus a normal one; it just sees a number
that looks statistically plausible or not, in isolation from everything else about that
sequence. This matches the theoretical argument for why sequence models should do better here
— but I want to flag that a 0.53 ROC-AUC is a genuinely poor result, not just "somewhat weaker
than the LSTM." If this were a real deployment decision, I would not ship the Isolation Forest
as a standalone detector on this feature set.

---

## 3. Is the 98th-percentile threshold actually justified?

`config.yaml` sets `threshold_percentile: 98`. I checked this against the real precision/recall
tradeoff rather than taking it on faith:

| Percentile | Cutoff (MSE) | Precision | Recall | F1 | # Flagged |
|---|---|---|---|---|---|
| 90 | 0.442 | 0.238 | 0.446 | 0.310 | 4,550 |
| 95 | 0.874 | 0.387 | 0.363 | 0.374 | 2,275 |
| **98** | **1.215** | **0.865** | **0.325** | **0.472** | **910** |
| 99 | 72.60 | 1.000 | 0.188 | 0.316 | 455 |
| 99.5 | 396.06 | 1.000 | 0.094 | 0.172 | 228 |
| 99.9 | 5,762.50 | 1.000 | 0.019 | 0.037 | 46 |

**The 98th percentile is actually the best-performing cutoff by F1** of everything I tested —
it's the point where precision jumps sharply (0.39 → 0.87) without recall collapsing yet. So
this part of the original config, at least, holds up under scrutiny rather than being an
arbitrary number.

What's more interesting is *why* there's such a sharp cliff right after it. Looking at the raw
score distribution:

```
p90: 0.44    p95: 0.87    p98: 1.21    p99: 72.60    p99.5: 396.06    p99.9: 5762.50    max: 84073.07
```

Looking at the reconstruction error distribution reveals something interesting. There is a **roughly 60× jump between the 98th and 99th percentiles** (1.21 → 72.60), indicating that the upper tail is not smooth. Instead, a relatively small group of sequences produces reconstruction errors far larger than the rest of the dataset, and the 98th-percentile threshold happens to fall in a clear gap immediately before this cluster begins.

Comparing normal and anomalous sequences confirms that this behaviour is not simply due to random variation. Normal sequences have reconstruction errors up to **2.77**, whereas anomalous sequences reach **84,073**, with the 99th percentile of anomalous sequences alone already at **25,040**. This suggests that a subset of anomalies is substantially different from normal behaviour, producing errors that are orders of magnitude larger than typical observations.

One possible explanation is that one or more input features occasionally take on extremely large values, causing the reconstruction error distribution to become heavily skewed. Identifying the exact source requires further analysis of the highest-scoring sequences, but the current distribution indicates that a small number of extreme outliers dominate the upper tail. This skew also explains why the current **CRITICAL/HIGH/MEDIUM/LOW** severity bands in `scorer.py` are poorly separated. Investigating the highest-error sequences and considering transformations such as clipping or log-scaling for the responsible features may produce a more evenly distributed anomaly score.

**Bottom line:** the **98th-percentile threshold** is well justified as the binary anomaly cutoff. It achieves the highest F1 score of all evaluated thresholds and lies in a genuine separation between typical reconstruction errors and extreme anomalies. However, it is **not** an ideal basis for defining multiple severity levels. Beyond the 98th percentile, anomaly scores span an extremely wide range—from approximately **1.2** to over **84,000**—with a handful of extreme outliers dominating the distribution. As a result, the current severity bands compress most anomalous events into the **CRITICAL** category instead of providing a meaningful progression from LOW to CRITICAL.


---
