from __future__ import annotations

import json
from datetime import datetime, timezone

from app.dashboard import compute_metrics, filter_window, load_records, percentile


def test_percentile_nearest_rank() -> None:
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([], 95) == 0.0


def test_compute_metrics_panels(tmp_path) -> None:
    path = tmp_path / "logs.jsonl"
    now = datetime(2026, 8, 10, 0, 5, 0, tzinfo=timezone.utc)
    records = [
        {
            "ts": "2026-08-10T00:00:00Z",
            "level": "info",
            "service": "api",
            "event": "request_received",
            "correlation_id": "req-aaaaaaaa",
            "user_id_hash": "aaa",
            "session_id": "s01",
            "feature": "qa",
            "model": "claude-sonnet-4-5",
        },
        {
            "ts": "2026-08-10T00:00:01Z",
            "level": "info",
            "service": "api",
            "event": "response_sent",
            "correlation_id": "req-aaaaaaaa",
            "latency_ms": 100,
            "ttft_ms": 50,
            "cost_usd": 0.001,
            "tokens_in": 50,
            "tokens_out": 80,
            "quality_score": 0.8,
            "tool_name": "retrieval",
            "tool_success": True,
        },
        {
            "ts": "2026-08-10T00:00:02Z",
            "level": "info",
            "service": "api",
            "event": "response_sent",
            "correlation_id": "req-bbbbbbbb",
            "latency_ms": 200,
            "ttft_ms": 120,
            "cost_usd": 0.002,
            "tokens_in": 60,
            "tokens_out": 90,
            "quality_score": 0.9,
            "tool_name": "retrieval",
            "tool_success": True,
        },
        {
            "ts": "2026-08-10T00:00:03Z",
            "level": "error",
            "service": "api",
            "event": "request_failed",
            "correlation_id": "req-cccccccc",
            "error_type": "RuntimeError",
            "tool_name": "retrieval",
            "tool_success": False,
        },
    ]
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )

    metrics = compute_metrics(load_records(path), now=now)

    assert metrics["latency"]["p95"] == 200
    assert metrics["traffic"]["request_count"] == 1
    assert metrics["errors"]["error_rate_pct"] == 100.0
    # retrieval attempts: 2 success (response_sent) + 1 fail (request_failed)
    assert metrics["errors"]["retrieval_success_pct"] == round(2 / 3 * 100.0, 2)
    assert metrics["errors"]["error_breakdown"] == {"RuntimeError": 1}
    assert metrics["cost"]["total_cost_usd"] == 0.003
    assert metrics["tokens"]["tokens_in"] == 110
    assert metrics["tokens"]["tokens_out"] == 170
    assert metrics["quality"]["mean_quality_score"] == 0.85


def test_retrieval_success_counts_request_failed() -> None:
    # request_failed do retrieval lỗi phải làm giảm retrieval success.
    now = datetime(2026, 8, 10, 0, 5, 0, tzinfo=timezone.utc)
    records = [
        {
            "ts": "2026-08-10T00:00:00Z",
            "event": "request_received",
            "correlation_id": "req-x",
        },
        {
            "ts": "2026-08-10T00:00:01Z",
            "event": "request_failed",
            "correlation_id": "req-x",
            "error_type": "RuntimeError",
            "tool_name": "retrieval",
            "tool_success": False,
        },
    ]
    metrics = compute_metrics(records, now=now)
    assert metrics["errors"]["retrieval_success_pct"] == 0.0


def test_window_filters_out_records_older_than_60_minutes() -> None:
    now = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
    records = [
        # ngoài cửa sổ 60 phút (61 phút trước)
        {
            "ts": "2026-08-09T22:59:00Z",
            "event": "request_received",
            "correlation_id": "req-old",
        },
        # trong cửa sổ (1 phút trước)
        {
            "ts": "2026-08-09T23:59:00Z",
            "event": "request_received",
            "correlation_id": "req-new",
        },
        {
            "ts": "2026-08-09T23:59:01Z",
            "event": "response_sent",
            "correlation_id": "req-new",
            "latency_ms": 150,
            "ttft_ms": 60,
            "cost_usd": 0.001,
            "tokens_in": 40,
            "tokens_out": 70,
            "quality_score": 0.85,
            "tool_name": "retrieval",
            "tool_success": True,
        },
    ]

    filtered = filter_window(records, now=now)
    assert len(filtered) == 2

    metrics = compute_metrics(records, now=now)
    assert metrics["traffic"]["request_count"] == 1
    assert metrics["cost"]["total_cost_usd"] == 0.001