import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .agent import Agent
from .config import InferenceAccountError, safe_error
from .course import CourseClient


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def implementation_digest():
    root = Path(__file__).parent
    return digest({p.name: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.py"))})


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
    temporary.replace(path)


class Evaluation:
    def __init__(self, settings, folder: Path, course=None, agent_factory=None):
        self.settings = settings
        self.folder = folder
        self.path = folder / "results.json"
        self.course = course or CourseClient()
        self.agent_factory = agent_factory or (lambda: Agent(settings))

    def run(self, limit=None, resume=True):
        self.settings.validate()
        questions = self.course.questions()
        if limit is not None:
            if not 1 <= limit <= len(questions):
                raise ValueError(f"limit must be between 1 and {len(questions)}.")
            questions = questions[:limit]
        fingerprint = digest({"settings": self.settings.public(), "implementation": implementation_digest()})
        if resume and self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("fingerprint") != fingerprint:
                raise ValueError(
                    "Code or model configuration changed. Start a new run directory to avoid reusing stale answers."
                )
        else:
            state = {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "fingerprint": fingerprint,
                "settings": self.settings.public(),
                "items": {},
            }
        state["question_ids"] = [q["task_id"] for q in questions]
        state.pop("stopped_reason", None)
        atomic_json(self.path, state)
        yield state
        agent = self.agent_factory()
        for question in questions:
            task_id = question["task_id"]
            question_hash = digest(question)
            old = state["items"].get(task_id, {})
            if resume and old.get("status") == "done" and old.get("question_hash") == question_hash:
                continue
            state["active_task"] = task_id
            atomic_json(self.path, state)
            yield state
            agent.last_attempt = {}
            terminal_error = None
            try:
                attachment = self.course.attachment(question, self.folder / "attachments")
                result = agent.solve(question["question"], [attachment] if attachment else [])
                state["items"][task_id] = {
                    "task_id": task_id,
                    "question": question["question"],
                    "question_hash": question_hash,
                    "status": "done",
                    "attachment_sha256": hashlib.sha256(attachment.read_bytes()).hexdigest()
                    if attachment
                    else None,
                    "attachment_source": getattr(self.course, "attachment_sources", {}).get(task_id),
                    **result,
                }
            except Exception as exc:
                state["items"][task_id] = {
                    **getattr(agent, "last_attempt", {}),
                    "task_id": task_id,
                    "question": question["question"],
                    "question_hash": question_hash,
                    "status": "error",
                    "error": safe_error(exc, self.settings.token),
                }
                if isinstance(exc, InferenceAccountError):
                    state["stopped_reason"] = safe_error(exc, self.settings.token)
                    state.pop("finished_at", None)
                    terminal_error = exc
            state.pop("active_task", None)
            atomic_json(self.path, state)
            yield state
            if terminal_error:
                raise terminal_error
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(self.path, state)
        yield state

    def submit(self, username: str, agent_code: str, allow_partial=False):
        state = json.loads(self.path.read_text(encoding="utf-8"))
        questions = self.course.questions()
        answers = []
        for question in questions:
            item = state["items"].get(question["task_id"], {})
            if item.get("status") != "done" or item.get("question_hash") != digest(question):
                if allow_partial:
                    continue
                raise ValueError(
                    "Complete all current course questions successfully before submitting. Resume to retry failures."
                )
            answers.append({"task_id": question["task_id"], "submitted_answer": item["answer"]})
        if not answers:
            raise ValueError("There are no successful current answers to submit.")
        payload = {"username": username, "agent_code": agent_code, "answers": answers}
        payload_hash = digest(payload)
        if state.get("submission_payload_hash") == payload_hash and "submission" in state:
            return state["submission"]
        atomic_json(self.folder / "submission.json", payload)
        result = self.course.submit(username, agent_code, answers)
        state["submission"] = result
        state["submission_payload_hash"] = payload_hash
        atomic_json(self.path, state)
        return result


def table_rows(state):
    return [
        [item["task_id"], item["question"], item["status"], item.get("answer", ""), item.get("error", "")]
        for task_id in state.get("question_ids", [])
        if (item := state.get("items", {}).get(task_id))
    ]


def status_text(state):
    items = [state.get("items", {}).get(task_id, {}) for task_id in state.get("question_ids", [])]
    done = sum(item.get("status") == "done" for item in items)
    errors = sum(item.get("status") == "error" for item in items)
    active = f" Working on {state['active_task']}." if state.get("active_task") else ""
    if state.get("stopped_reason"):
        return f"{done}/{len(items)} answered; run stopped. {state['stopped_reason']}"
    return f"{done}/{len(items)} answered; {errors} errors.{active} Answers generated; score is unknown until submission."
