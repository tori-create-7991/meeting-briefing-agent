from types import SimpleNamespace

from google.adk.agents import SequentialAgent

from meeting_briefing_agent import agent
from meeting_briefing_agent.fetcher import STATE_KEY


def render(writer, state):
    return writer.instruction(SimpleNamespace(state=state))


def test_root_agent_runs_fetcher_then_writer():
    assert isinstance(agent.root_agent, SequentialAgent)
    assert [a.name for a in agent.root_agent.sub_agents] == [
        "context_fetcher",
        "briefing_writer",
    ]


def test_build_writer_uses_language_and_model():
    writer = agent.build_writer(language="ja", model="m")

    assert writer.model == "m"
    assert writer.tools == []
    assert "language: ja" in render(writer, {})


def test_writer_instruction_embeds_contexts_verbatim():
    writer = agent.build_writer()
    contexts = '[{"event": {"summary": "{not_a_placeholder} 定例"}}]'

    text = render(writer, {STATE_KEY: contexts})

    assert f"<briefing_contexts>\n{contexts}\n</briefing_contexts>" in text


def test_writer_instruction_defaults_to_empty_list():
    assert "<briefing_contexts>\n[]\n</briefing_contexts>" in render(agent.build_writer(), {})


def test_root_agent_reads_model_and_language_from_env(monkeypatch):
    monkeypatch.setenv("BRIEFING_MODEL", "custom-model")
    monkeypatch.setenv("BRIEFING_LANGUAGE", "en")

    writer = agent.build_root_agent().sub_agents[1]

    assert writer.model == "custom-model"
    assert "language: en" in render(writer, {})


def test_root_agent_defaults(monkeypatch):
    monkeypatch.delenv("BRIEFING_MODEL", raising=False)
    monkeypatch.delenv("BRIEFING_LANGUAGE", raising=False)

    writer = agent.build_root_agent().sub_agents[1]

    assert writer.model == "gemini-3.5-flash"
    assert "language: ja" in render(writer, {})
