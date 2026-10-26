from types import SimpleNamespace

import pytest

from gaia_agent.agent import Agent, normalize_answer
from gaia_agent.config import Settings


class FakeModel:
    def __init__(self, responses):
        self.settings = Settings(token="test-token", max_steps=2)
        self.responses = iter(responses)
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        self.messages = []

    def chat(self, messages, tools=None):
        self.messages = list(messages)
        self.usage["calls"] += 1
        return next(self.responses)


def response(answer=None, name=None, arguments=None):
    calls = (
        None
        if not name
        else [SimpleNamespace(id="call1", function=SimpleNamespace(name=name, arguments=arguments))]
    )
    return SimpleNamespace(content=answer, tool_calls=calls)


def test_actual_tool_result_reaches_model():
    model = FakeModel(
        [response(name="calculator", arguments='{"expression":"6 * 7"}'), response("FINAL ANSWER: 42")]
    )
    result = Agent(model.settings, model).solve("What is 6 * 7?")
    assert result["answer"] == "42"
    assert result["trace"][0]["observation"] == {"ok": True, "result": 42}
    assert '"result": 42' in model.messages[-1]["content"]
    assert result["usage"]["calls"] == 2


def test_malformed_tool_call_can_be_recovered():
    model = FakeModel([response(name="calculator", arguments="not json"), response("42")])
    result = Agent(model.settings, model).solve("Compute an answer")
    assert result["trace"][0]["observation"]["ok"] is False
    assert result["answer"] == "42"


def test_budget_requires_final_without_more_tools():
    model = FakeModel([response(name="calculator", arguments='{"expression":"2+2"}'), response("4")])
    settings = Settings(token="test-token", max_steps=1)
    result = Agent(settings, model).solve("2+2")
    assert result["budget_exhausted"] is True
    assert result["answer"] == "4"


@pytest.mark.parametrize("value", ["", "UNKNOWN", "x" * 4001])
def test_invalid_answers_are_not_successful(value):
    with pytest.raises(ValueError):
        normalize_answer(value)


def test_formatting_does_not_change_semantics():
    assert normalize_answer("```text\nFINAL ANSWER: 1, 2, 3\n```") == "1, 2, 3"
    assert normalize_answer("001.20") == "001.20"
    assert normalize_answer("Qh4#") == "Qh4#"


def test_failed_attempt_retains_evidence_and_usage():
    model = FakeModel([response(name="calculator", arguments='{"expression":"2+2"}'), response("UNKNOWN")])
    agent = Agent(model.settings, model)
    with pytest.raises(ValueError):
        agent.solve("Unanswerable")
    assert agent.last_attempt["trace"][0]["observation"]["result"] == 4
    assert agent.last_attempt["usage"]["calls"] == 2
