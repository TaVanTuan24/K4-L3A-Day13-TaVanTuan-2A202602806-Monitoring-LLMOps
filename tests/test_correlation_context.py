from __future__ import annotations

import asyncio
import json
import re

import httpx

from app import logging_config
from app.main import app
from app.middleware import CORRELATION_ID_PATTERN, generate_correlation_id

CID_RE = re.compile(r"^req-[0-9a-f]{8}$")


def test_generate_correlation_id_format() -> None:
    cid = generate_correlation_id()
    assert CID_RE.match(cid)
    assert CORRELATION_ID_PATTERN.match(cid)


def test_generate_correlation_id_is_unique() -> None:
    ids = {generate_correlation_id() for _ in range(200)}
    assert len(ids) == 200


def test_response_headers_echo_valid_correlation_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")
    transport = httpx.ASGITransport(app=app)

    async def run() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.get("/health")
            r2 = await client.get("/health", headers={"x-request-id": "not-valid"})
            r3 = await client.get("/health", headers={"x-request-id": "req-abcdef12"})
            return r1, r2, r3

    r1, r2, r3 = asyncio.run(run())

    assert CID_RE.match(r1.headers["x-request-id"])
    assert "x-response-time-ms" in r1.headers

    assert CID_RE.match(r2.headers["x-request-id"])
    assert r2.headers["x-request-id"] != "not-valid"

    assert r3.headers["x-request-id"] == "req-abcdef12"


def test_chat_logs_enriched_and_isolated(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    transport = httpx.ASGITransport(app=app)

    async def run() -> tuple[httpx.Response, httpx.Response]:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.post(
                "/chat",
                json={
                    "user_id": "u01",
                    "session_id": "s01",
                    "feature": "qa",
                    "message": "My phone is 0987654321, what is refund?",
                },
            )
            r2 = await client.post(
                "/chat",
                json={
                    "user_id": "u02",
                    "session_id": "s02",
                    "feature": "summary",
                    "message": "Explain monitoring",
                },
            )
            return r1, r2

    r1, r2 = asyncio.run(run())

    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    received = [r for r in rows if r.get("event") == "request_received"]
    assert len(received) == 2

    sessions = {r["session_id"] for r in received}
    assert sessions == {"s01", "s02"}

    for record in received:
        assert re.match(r"^req-[0-9a-f]{8}$", record["correlation_id"])
        assert record["user_id_hash"] and "u01" not in record["user_id_hash"]
        assert record["feature"] in {"qa", "summary"}
        assert record["model"] == "claude-sonnet-4-5"
        assert record["env"]

    # Raw phone phải bị scrub trước khi ghi log.
    raw = json.dumps(rows, ensure_ascii=False)
    assert "0987654321" not in raw