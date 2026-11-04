from types import SimpleNamespace

import google.auth
from google.adk.agents import SequentialAgent
from google.adk.models import Gemini
from google.auth.credentials import AnonymousCredentials

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
    monkeypatch.delenv("BRIEFING_MODEL_LOCATION", raising=False)

    writer = agent.build_root_agent().sub_agents[1]

    assert writer.model == "custom-model"
    assert "language: en" in render(writer, {})


def test_root_agent_defaults(monkeypatch):
    monkeypatch.delenv("BRIEFING_MODEL", raising=False)
    monkeypatch.delenv("BRIEFING_LANGUAGE", raising=False)
    monkeypatch.delenv("BRIEFING_MODEL_LOCATION", raising=False)

    writer = agent.build_root_agent().sub_agents[1]

    assert writer.model == "gemini-3.5-flash"
    assert "language: ja" in render(writer, {})


def test_build_writer_sends_model_calls_to_the_given_location():
    writer = agent.build_writer(model="m", location="global")

    assert isinstance(writer.model, Gemini)
    assert writer.model.model == "m"
    assert writer.model.client_kwargs == {"location": "global"}


def test_root_agent_reads_model_location_from_env(monkeypatch):
    monkeypatch.setenv("BRIEFING_MODEL", "custom-model")
    monkeypatch.setenv("BRIEFING_MODEL_LOCATION", "global")

    writer = agent.build_root_agent().sub_agents[1]

    assert isinstance(writer.model, Gemini)
    assert writer.model.model == "custom-model"
    assert writer.model.client_kwargs == {"location": "global"}


def test_model_location_overrides_the_runtime_location(monkeypatch):
    # Agent Runtime pins GOOGLE_CLOUD_LOCATION to the agent's region, while
    # Gemini 3 models are served only from "global".
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setattr(
        google.auth, "default", lambda *a, **k: (AnonymousCredentials(), "p")
    )

    client = agent.build_model("m", "global").api_client

    assert client._api_client.location == "global"
