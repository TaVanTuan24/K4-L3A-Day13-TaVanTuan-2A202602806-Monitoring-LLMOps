from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

DEFAULT_LOG_PATH = Path("data/logs.jsonl")
WINDOW_MINUTES = 60


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile; trả 0.0 khi danh sách rỗng."""
    if not values:
        return 0.0
    items = sorted(values)
    index = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[index])


def load_records(path: str | Path = DEFAULT_LOG_PATH) -> list[dict[str, Any]]:
    """Đọc toàn bộ structured log từ data/logs.jsonl."""
    log_path = Path(path)
    if not log_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Tính metric cho 6 panel dashboard từ danh sách log records."""
    responses = [r for r in records if r.get("event") == "response_sent"]
    received = [r for r in records if r.get("event") == "request_received"]
    failed = [r for r in records if r.get("event") == "request_failed"]

    latencies = [r["latency_ms"] for r in responses if r.get("latency_ms") is not None]
    ttfts = [r["ttft_ms"] for r in responses if r.get("ttft_ms") is not None]
    costs = [float(r["cost_usd"]) for r in responses if r.get("cost_usd") is not None]
    tokens_in = [r["tokens_in"] for r in responses if r.get("tokens_in") is not None]
    tokens_out = [r["tokens_out"] for r in responses if r.get("tokens_out") is not None]
    quality = [r["quality_score"] for r in responses if r.get("quality_score") is not None]

    error_breakdown: Counter[str] = Counter()
    for r in failed:
        error_breakdown[r.get("error_type") or "unknown"] += 1

    retrieval_ok = 0
    retrieval_total = 0
    for r in responses:
        if r.get("tool_name") == "retrieval":
            retrieval_total += 1
            if r.get("tool_success") is True:
                retrieval_ok += 1

    error_rate_pct = (len(failed) / len(received) * 100.0) if received else 0.0
    retrieval_success_pct = (
        (retrieval_ok / retrieval_total * 100.0) if retrieval_total else 100.0
    )

    request_count = len(received)
    requests_per_minute = request_count / WINDOW_MINUTES

    return {
        "latency": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "ttft_p95": percentile(ttfts, 95),
        },
        "traffic": {
            "request_count": request_count,
            "requests_per_minute": round(requests_per_minute, 3),
        },
        "errors": {
            "error_rate_pct": round(error_rate_pct, 2),
            "error_breakdown": dict(error_breakdown),
            "retrieval_success_pct": round(retrieval_success_pct, 2),
        },
        "cost": {
            "total_cost_usd": round(sum(costs), 6),
        },
        "tokens": {
            "tokens_in": sum(tokens_in),
            "tokens_out": sum(tokens_out),
        },
        "quality": {
            "mean_quality_score": round(mean(quality), 4) if quality else 0.0,
        },
    }