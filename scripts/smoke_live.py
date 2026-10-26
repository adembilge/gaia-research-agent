"""Read-only live integration checks. No inference calls or leaderboard submissions."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from gaia_agent.config import Settings, safe_error
from gaia_agent.course import CourseClient
from gaia_agent.evaluation import atomic_json
from gaia_agent.tools import Tools


def main():
    folder = Path("runs/live-smoke")
    settings = Settings.from_env()
    tools = Tools(SimpleNamespace(settings=settings))
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "inference_tested": False,
        "leaderboard_submitted": False,
        "checks": {},
    }
    course = CourseClient()
    questions = course.questions()
    atomic_json(folder / "questions.json", questions)
    report["checks"]["course_api"] = {"ok": len(questions) == 20, "question_count": len(questions)}
    for question in questions:
        if not question.get("file_name"):
            continue
        name = question["file_name"]
        try:
            path = course.attachment(question, folder / "attachments")
            tools.files[path.name] = path
            item = {
                "ok": True,
                "bytes": path.stat().st_size,
                "extension": path.suffix,
                "source": course.attachment_sources[question["task_id"]],
            }
            if path.suffix in {".py", ".xlsx"}:
                item["extracted_characters"] = tools.read_file(path.name)["total_characters"]
                item["ok"] = item["extracted_characters"] > 0
            report["checks"][name] = item
        except Exception as exc:
            report["checks"][name] = {"ok": False, "error": safe_error(exc)}
    for name, action in {
        "web_search": lambda: tools.web_search("Hugging Face official agents course"),
        "web_reader": lambda: tools.read_web("https://huggingface.co/learn/agents-course/unit4/hands-on"),
        "pdf_reader": lambda: tools.read_web("https://arxiv.org/pdf/1706.03762"),
    }.items():
        try:
            result = action()
            report["checks"][name] = {
                "ok": bool(result),
                "result_count_or_characters": len(result)
                if isinstance(result, list)
                else result["total_characters"],
            }
        except Exception as exc:
            report["checks"][name] = {"ok": False, "error": safe_error(exc)}
    model_checks = (
        {
            "reasoning_model": settings.model,
            "vision_model": settings.vision_model,
            "audio_model": settings.asr_model,
        }
        if settings.provider == "huggingface"
        else {}
    )
    report["inference_provider"] = settings.provider
    for name, model in model_checks.items():
        try:
            response = httpx.get(
                f"https://huggingface.co/api/models/{model}",
                params={"expand": "inferenceProviderMapping"},
                timeout=30,
            )
            response.raise_for_status()
            providers = response.json().get("inferenceProviderMapping", {})
            report["checks"][name] = {
                "ok": any(p.get("status") == "live" for p in providers.values()),
                "model": model,
                "providers": providers,
            }
        except Exception as exc:
            report["checks"][name] = {"ok": False, "model": model, "error": safe_error(exc)}
    atomic_json(folder / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
