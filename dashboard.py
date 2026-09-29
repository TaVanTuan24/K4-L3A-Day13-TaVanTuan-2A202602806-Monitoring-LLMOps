"""Dashboard runtime Day 13 — đọc data/logs.jsonl và hiển thị 6 panel.

Chạy:
    streamlit run dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard import WINDOW_MINUTES, compute_metrics, load_records  # noqa: E402

st.set_page_config(page_title="Day 13 Monitoring & LLMOps", layout="wide")

st.title("K4-L3A Day 13 — Monitoring & LLMOps Dashboard")
st.caption(
    f"Nguồn dữ liệu: `data/logs.jsonl` · Time range: {WINDOW_MINUTES} minutes · SLO/threshold theo `config/dashboard.yaml`"
)

records = load_records(REPO_ROOT / "data" / "logs.jsonl")
metrics = compute_metrics(records)

if not records:
    st.warning("Chưa có dữ liệu trong `data/logs.jsonl`. Chạy `python scripts/load_test.py` trước.")
    st.stop()

st.caption(f"{len(records)} log records loaded · {metrics['traffic']['request_count']} request_received events.")


def _frame() -> pd.DataFrame:
    df = pd.DataFrame(records)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df


def _cost_by_minute(df: pd.DataFrame) -> pd.Series:
    responses = df[df["event"] == "response_sent"].copy()
    if responses.empty or responses["ts"].isna().all():
        return pd.Series(dtype=float)
    responses = responses.dropna(subset=["ts"])
    responses["cost_usd"] = pd.to_numeric(responses["cost_usd"], errors="coerce").fillna(0.0)
    return responses.set_index("ts")["cost_usd"].resample("1min").sum().fillna(0.0)


def _traffic_by_minute(df: pd.DataFrame) -> pd.Series:
    received = df[df["event"] == "request_received"].copy()
    if received.empty or received["ts"].isna().all():
        return pd.Series(dtype=int)
    received = received.dropna(subset=["ts"])
    received["count"] = 1
    return received.set_index("ts")["count"].resample("1min").sum().fillna(0)


frame = _frame()
cost_series = _cost_by_minute(frame)
traffic_series = _traffic_by_minute(frame)

latency = metrics["latency"]
traffic = metrics["traffic"]
errors = metrics["errors"]
cost = metrics["cost"]
tokens = metrics["tokens"]
quality = metrics["quality"]

# Panel 1: Latency
st.subheader("1. Latency")
c1, c2, c3, c4 = st.columns(4)
c1.metric("P50", f"{latency['p50']:.1f} ms")
c2.metric("P95", f"{latency['p95']:.1f} ms")
c3.metric("P99", f"{latency['p99']:.1f} ms")
c4.metric("TTFT P95", f"{latency['ttft_p95']:.1f} ms")
st.caption("Unit: ms · SLO/threshold: P95 <= 3000 ms")

# Panel 2: Traffic
st.subheader("2. Traffic")
c1, c2 = st.columns(2)
c1.metric("Request count", f"{traffic['request_count']}")
c2.metric("Requests/minute", f"{traffic['requests_per_minute']:.3f}")
if not traffic_series.empty:
    st.line_chart(traffic_series)
st.caption("Unit: requests · dựa trên event `request_received`")

# Panel 3: Errors & Retrieval Success
st.subheader("3. Errors & Retrieval Success")
c1, c2 = st.columns(2)
c1.metric("Error rate", f"{errors['error_rate_pct']:.2f} %")
c2.metric("Retrieval success", f"{errors['retrieval_success_pct']:.2f} %")
if errors["error_breakdown"]:
    st.write("Error breakdown:", errors["error_breakdown"])
else:
    st.write("Error breakdown: (none)")
st.caption("Threshold: error rate <= 2 %")

# Panel 4: Cost
st.subheader("4. Cost")
st.metric("Total cost (window)", f"${cost['total_cost_usd']:.6f}")
if not cost_series.empty:
    st.bar_chart(cost_series)
st.caption("Unit: USD · cost by minute · Threshold: total <= $2.5 (per window)")

# Panel 5: Tokens
st.subheader("5. Tokens")
c1, c2 = st.columns(2)
c1.metric("Input tokens", f"{tokens['tokens_in']}")
c2.metric("Output tokens", f"{tokens['tokens_out']}")
st.caption("Unit: tokens · Threshold: sum <= 50000")

# Panel 6: Quality
st.subheader("6. Quality")
st.metric("Mean quality score", f"{quality['mean_quality_score']:.2f}")
st.caption("Unit: score 0–1 · Threshold: mean >= 0.75")