import os
import re
from pathlib import Path
from uuid import UUID

import httpx

from .net import fetch_url

API_URL = "https://agents-course-unit4-scoring.hf.space"


class CourseClient:
    def __init__(self, token=None):
        self.token = token or os.getenv("HF_DATASET_TOKEN") or os.getenv("HF_TOKEN")
        self.attachment_sources = {}

    def questions(self) -> list[dict]:
        response = httpx.get(f"{API_URL}/questions", timeout=30)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise ValueError("The course API returned no questions.")
        seen = set()
        for row in rows:
            UUID(row["task_id"])
            if row["task_id"] in seen or not isinstance(row.get("question"), str):
                raise ValueError("The course API returned invalid or duplicate questions.")
            seen.add(row["task_id"])
        return rows

    def attachment(self, question: dict, directory: Path) -> Path | None:
        if not question.get("file_name"):
            return None
        task_id = str(UUID(question["task_id"]))
        suffix = Path(question["file_name"]).suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            raise ValueError("Invalid attachment extension.")
        source = f"{API_URL}/files/{task_id}"
        try:
            data, _, _ = fetch_url(source)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {403, 404}:
                raise
            if not self.token:
                raise ValueError(
                    "Course attachment endpoint is unavailable. For the official dataset fallback, accept access at https://huggingface.co/datasets/gaia-benchmark/GAIA and configure HF_DATASET_TOKEN (or HF_TOKEN) with dataset read access."
                ) from None
            from huggingface_hub import hf_hub_download
            from huggingface_hub.errors import GatedRepoError

            # Download the exact attachment only. Never read metadata.jsonl, answers, or annotations.
            filename = f"2023/validation/{task_id}{suffix}"
            try:
                cached = hf_hub_download(
                    "gaia-benchmark/GAIA", filename, repo_type="dataset", token=self.token
                )
            except GatedRepoError:
                raise ValueError(
                    "GAIA attachment access was denied. Accept the dataset access conditions and give HF_DATASET_TOKEN read access to gaia-benchmark/GAIA."
                ) from None
            data = Path(cached).read_bytes()
            source = f"hf://datasets/gaia-benchmark/GAIA/{filename}"
        if len(data) > 25 * 1024 * 1024:
            raise ValueError("Attachment exceeds the 25 MiB size limit.")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{task_id}{suffix}"
        target.write_bytes(data)
        self.attachment_sources[task_id] = source
        return target

    def submit(self, username: str, agent_code: str, answers: list[dict]) -> dict:
        if not username.strip() or not re.fullmatch(
            r"https://huggingface\.co/spaces/[\w.-]+/[\w.-]+/tree/main/?", agent_code
        ):
            raise ValueError("Provide a username and a public Hugging Face Space code URL ending /tree/main.")
        if not answers or len({a["task_id"] for a in answers}) != len(answers):
            raise ValueError("Answers must be nonempty and task IDs must be unique.")
        for answer in answers:
            UUID(answer["task_id"])
            if not isinstance(answer.get("submitted_answer"), str) or not answer["submitted_answer"].strip():
                raise ValueError("Every submitted answer must be a nonempty string.")
        # Do not automatically retry POST: a timeout may occur after the leaderboard was updated.
        response = httpx.post(
            f"{API_URL}/submit",
            json={"username": username.strip(), "agent_code": agent_code, "answers": answers},
            timeout=90,
        )
        response.raise_for_status()
        return response.json()
