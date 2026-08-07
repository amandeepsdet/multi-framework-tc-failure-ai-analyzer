"""Offline unit tests for the engine facade, stores, and QA assistant."""

from __future__ import annotations

import pytest

from qa_ai_engine import AIConfig, AIEngine
from qa_ai_engine.history_store import HistoryStore
from qa_ai_engine.prompt_builder import PromptBuilder
from qa_ai_engine.vector_store import JSONVectorStore
from qa_ai_engine.embeddings import HashEmbedder
from qa_ai_engine.assistant import ChatEngine, QAAssistant


@pytest.fixture
def tmp_config(tmp_path) -> AIConfig:
    """An AIConfig whose output dirs are isolated to a temp folder."""
    cfg = AIConfig(
        enabled=True,
        provider="heuristic",
        history_dir=tmp_path / "failure_history",
        reports_dir=tmp_path / "ai_reports",
        vector_dir=tmp_path / "vector_db",
        dashboard_dir=tmp_path / "reports",
    )
    cfg.ensure_dirs()
    return cfg


@pytest.mark.ai
def test_prompt_builder_injects_tokens() -> None:
    builder = PromptBuilder()
    out = builder.build("root_cause", {"test_name": "TC-07", "exception_type": "AssertionError"})
    assert "TC-07" in out
    assert "{{TEST_NAME}}" not in out


@pytest.mark.ai
def test_prompt_builder_preserves_json_braces() -> None:
    builder = PromptBuilder()
    out = builder.build("root_cause", {"test_name": "x"})
    # Example JSON braces in the template must survive rendering.
    assert '"category"' in out


@pytest.mark.ai
def test_json_vector_store_search(tmp_path) -> None:
    store = JSONVectorStore(tmp_path / "v.json", HashEmbedder(128))
    store.add("1", "backend returned HTTP 500 empty response", {"category": "Backend"})
    store.add("2", "login username password field", {"category": "UI"})
    hits = store.search("HTTP 500 backend failure", top_k=2)
    assert hits and hits[0].metadata["category"] == "Backend"


@pytest.mark.ai
def test_history_store_save_and_load(tmp_config: AIConfig) -> None:
    from qa_ai_engine.models import FailureRecord

    store = HistoryStore(tmp_config)
    store.save(FailureRecord(test_name="test_login", failure="boom"))
    assert store.count() == 1
    assert store.by_test("login")


@pytest.mark.ai
def test_engine_analyze_record_offline(tmp_config: AIConfig) -> None:
    from qa_ai_engine.models import Evidence, FailureRecord

    engine = AIEngine(tmp_config)
    record = FailureRecord(
        test_name="test_dashboard",
        evidence=Evidence(network=[{"method": "GET", "url": "/api/x", "status": 500}]),
    )
    outcome = engine.analyze_record(record, persist=True)
    assert outcome.analysis.category.value == "Backend"
    assert outcome.bug_report.title
    assert outcome.history_path is not None
    # Per-test HTML reports are no longer generated; one consolidated dashboard is
    # produced per execution instead.
    engine.begin_execution(run_name="unit-run")
    engine.append_failure(outcome, nodeid=record.test_name)
    engine.append_success("test_that_passed")
    paths = engine.finish_execution()
    assert "html" in paths and paths["html"].exists()
    assert paths["html"].name == "ai_failure_analysis.html"
    assert (tmp_config.dashboard_dir / "ai_failure_analysis.json").exists()
    assert (tmp_config.dashboard_dir / "ai_failure_analysis.md").exists()


@pytest.mark.ai
def test_engine_disabled_by_default() -> None:
    assert AIConfig().enabled is False


@pytest.mark.ai
def test_assistant_status_and_search(tmp_config: AIConfig) -> None:
    assistant = QAAssistant(AIEngine(tmp_config))
    status = assistant.status()
    assert status["provider"] == "heuristic"
    result = assistant.search("temperature failures")
    assert "results" in result


@pytest.mark.ai
def test_assistant_quality_summary(tmp_config: AIConfig) -> None:
    assistant = QAAssistant(AIEngine(tmp_config))
    out = assistant.quality_summary()
    assert "release_readiness" in out
    assert "total_failures" in out


@pytest.mark.ai
def test_assistant_compare_runs(tmp_config: AIConfig) -> None:
    assistant = QAAssistant(AIEngine(tmp_config))
    out = assistant.compare_runs()
    # With no history this returns a friendly message; the key point is it runs.
    assert isinstance(out, dict)


@pytest.mark.ai
def test_chat_router_intents() -> None:
    engine = ChatEngine()
    assert engine.route("Which tests are flaky?")["intent"] == "flaky"
    assert engine.route("Are we ready to release?")["intent"] == "release"
    assert engine.route("Generate a Jira bug")["intent"] == "bug"


@pytest.mark.ai
def test_tool_registry_describes_tools() -> None:
    assistant = QAAssistant()
    described = assistant.registry.describe_all()
    names = {t["name"] for t in described}
    assert "AnalyzeFailureTool" in names and "ReleaseReadinessTool" in names
