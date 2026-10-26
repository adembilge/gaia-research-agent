import json

import pytest

from gaia_agent.config import InferenceAccountError, Settings
from gaia_agent.evaluation import Evaluation

TASK_A = "8e867cd7-cff9-4e6c-867a-ff5ddc2550be"
TASK_B = "a1e91b78-d3d8-4675-bb8d-62741b4b68a6"


class FakeCourse:
    def __init__(self):
        self.rows = [
            {"task_id": TASK_A, "question": "First?", "file_name": ""},
            {"task_id": TASK_B, "question": "Second?", "file_name": ""},
        ]
        self.submissions = []

    def questions(self):
        return self.rows

    def attachment(self, question, directory):
        return None

    def submit(self, username, code, answers):
        self.submissions.append(answers)
        return {"score": 50, "correct_count": 1, "total_attempted": 2}


class CountingAgent:
    def __init__(self):
        self.calls = []
        self.fail = True

    def solve(self, question, attachments):
        self.calls.append(question)
        if self.fail and question == "Second?":
            raise ValueError("temporary failure")
        return {"answer": "Example answer", "trace": [], "usage": {}}


def test_resume_retries_failure_without_rerunning_success(tmp_path):
    agent = CountingAgent()
    course = FakeCourse()
    evaluation = Evaluation(Settings(token="fake"), tmp_path, course, lambda: agent)
    states = list(evaluation.run())
    assert states[-1]["items"][TASK_B]["status"] == "error"
    with pytest.raises(ValueError, match="Complete all"):
        evaluation.submit("user", "https://huggingface.co/spaces/user/agent/tree/main")
    assert course.submissions == []
    agent.fail = False
    list(evaluation.run())
    assert agent.calls == ["First?", "Second?", "Second?"]
    result = evaluation.submit("user", "https://huggingface.co/spaces/user/agent/tree/main")
    assert result["score"] == 50
    evaluation.submit("user", "https://huggingface.co/spaces/user/agent/tree/main")
    assert len(course.submissions) == 1
    assert "fake" not in (tmp_path / "results.json").read_text()
    assert set(json.loads((tmp_path / "submission.json").read_text())["answers"][0]) == {
        "task_id",
        "submitted_answer",
    }


def test_changed_configuration_does_not_reuse_cache(tmp_path):
    course, agent = FakeCourse(), CountingAgent()
    list(Evaluation(Settings(token="fake"), tmp_path, course, lambda: agent).run())
    with pytest.raises(ValueError, match="configuration changed"):
        list(Evaluation(Settings(token="fake", model="another-model"), tmp_path, course, lambda: agent).run())


def test_changed_question_is_recomputed(tmp_path):
    course, agent = FakeCourse(), CountingAgent()
    evaluation = Evaluation(Settings(token="fake"), tmp_path, course, lambda: agent)
    list(evaluation.run())
    course.rows[0] = {**course.rows[0], "question": "Changed?"}
    list(evaluation.run())
    assert "Changed?" in agent.calls


def test_partial_run_cannot_be_submitted_as_full_run(tmp_path):
    course, agent = FakeCourse(), CountingAgent()
    evaluation = Evaluation(Settings(token="fake"), tmp_path, course, lambda: agent)
    list(evaluation.run(limit=1))
    with pytest.raises(ValueError, match="Complete all"):
        evaluation.submit("user", "https://huggingface.co/spaces/user/agent/tree/main")


def test_partial_submission_requires_explicit_opt_in(tmp_path):
    course, agent = FakeCourse(), CountingAgent()
    evaluation = Evaluation(Settings(token="fake"), tmp_path, course, lambda: agent)
    list(evaluation.run(limit=1))
    evaluation.submit("user", "https://huggingface.co/spaces/user/agent/tree/main", allow_partial=True)
    assert len(course.submissions[0]) == 1
    assert course.submissions[0][0]["task_id"] == TASK_A


def test_billing_failure_stops_run_and_saves_checkpoint(tmp_path):
    class UnfundedAgent:
        def __init__(self):
            self.calls = []

        def solve(self, question, attachments):
            self.calls.append(question)
            raise InferenceAccountError("No credits (HTTP 402)")

    course, agent = FakeCourse(), UnfundedAgent()
    evaluation = Evaluation(Settings(token="fake"), tmp_path, course, lambda: agent)
    with pytest.raises(InferenceAccountError):
        list(evaluation.run())
    state = json.loads((tmp_path / "results.json").read_text())
    assert agent.calls == ["First?"]
    assert state["items"][TASK_A]["status"] == "error"
    assert "402" in state["stopped_reason"]
    assert "finished_at" not in state
