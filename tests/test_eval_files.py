"""The eval files are only run by hand (they call Gemini), so at least make
sure they stay loadable by ADK."""

import json
import pathlib

from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet

EVAL_DIR = pathlib.Path(__file__).parent / "eval"


def test_eval_set_parses_and_seeds_writer_state():
    eval_set = EvalSet.model_validate_json((EVAL_DIR / "briefing.evalset.json").read_text())

    assert len(eval_set.eval_cases) == 3
    for case in eval_set.eval_cases:
        assert case.rubrics
        contexts = json.loads(case.session_input.state["briefing_contexts"])
        assert all({"event", "docs", "past_meeting_trends"} <= set(c) for c in contexts)


def test_eval_config_parses():
    EvalConfig.model_validate_json((EVAL_DIR / "test_config.json").read_text())


def test_writer_agent_module_loads():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "writer_agent_under_test", EVAL_DIR / "writer_agent" / "agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.root_agent.name == "briefing_writer"
