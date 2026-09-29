from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module


class ManagedPrompt:
    version = 3
    is_fallback = False

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class TracingFakeClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.observations: list[dict] = []
        self.span_updates: list[dict] = []
        self.generation_updates: list[dict] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        self.observations.append(kwargs)
        yield None

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)

    def update_current_generation(self, **kwargs) -> None:
        self.generation_updates.append(kwargs)


def test_run_creates_retrieval_and_generation_children(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")
    client = TracingFakeClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    propagated: list[dict] = []

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="u01",
        feature="qa",
        session_id="s01",
        message="Explain traces",
        correlation_id="req-12345678",
    )

    names = [o["name"] for o in client.observations]
    as_types = [o["as_type"] for o in client.observations]
    assert names == ["retrieval", "generation"]
    assert as_types == ["retriever", "generation"]

    # Retrieval span có doc_count + query_preview (đã scrub) + correlation_id.
    retrieval_meta = client.span_updates[0]["metadata"]
    assert retrieval_meta["doc_count"] >= 1
    assert "query_preview" in retrieval_meta
    assert retrieval_meta["correlation_id"] == "req-12345678"

    # Generation không capture raw input/output (PII-safe), có model.
    generation = client.observations[1]
    assert generation["model"] == "claude-sonnet-4-5"
    assert generation.get("input") is None
    assert generation.get("output") is None

    # Generation được update usage + cost sau khi generate xong.
    gen_update = client.generation_updates[-1]
    assert gen_update["usage_details"]["input"] > 0
    assert gen_update["usage_details"]["output"] > 0
    assert gen_update["cost_details"]["input"] >= 0
    assert gen_update["cost_details"]["output"] >= 0
    assert gen_update["cost_details"]["total"] > 0


def test_run_without_observation_api_still_works(monkeypatch) -> None:
    """Khi client không có SDK v4 observation API (portable fallback)."""
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")

    class MinimalClient:
        def __init__(self) -> None:
            self.prompt = ManagedPrompt()
            self.span_updates: list[dict] = []

        def get_prompt(self, name: str, **kwargs):
            return self.prompt

        def update_current_span(self, **kwargs) -> None:
            self.span_updates.append(kwargs)

    client = MinimalClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    @contextmanager
    def record_attributes(**kwargs):
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    result = agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="u01",
        feature="qa",
        session_id="s01",
        message="Explain traces",
        correlation_id="req-abcdef12",
    )

    assert result.answer
    assert result.latency_ms >= 0
    assert client.span_updates[-1]["version"] == "3"