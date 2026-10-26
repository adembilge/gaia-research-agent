"""Explicit upload helper. Never includes .env, local runs, or the virtual environment."""

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from huggingface_hub import HfApi
from huggingface_hub.errors import RepositoryNotFoundError


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Publish this project as a public Hugging Face Space")
    parser.add_argument("repo_id", help="Your username/space-name")
    parser.add_argument("--update", action="store_true", help="Explicitly allow updating an existing Space")
    parser.add_argument(
        "--sdk",
        choices=["gradio", "static"],
        default="gradio",
        help="Static publishes a free source mirror; the Python agent runs locally",
    )
    args = parser.parse_args()
    token = os.getenv("HF_DEPLOY_TOKEN") or os.getenv("HF_TOKEN")
    if not token:
        parser.error("Set HF_DEPLOY_TOKEN (write access) or HF_TOKEN in .env first.")
    api = HfApi(token=token)
    try:
        info = api.space_info(args.repo_id)
    except RepositoryNotFoundError:
        info = None
    if info and not args.update:
        parser.error("Space already exists. Use --update only if you intend to update its files.")
    if info and info.private:
        parser.error("The course needs public source code. Choose a new public Space instead.")
    api.create_repo(args.repo_id, repo_type="space", space_sdk=args.sdk, private=False, exist_ok=True)
    source_root = Path(__file__).resolve().parent
    patterns = [
        "app.py",
        "gaia_agent/*.py",
        "README.md",
        "VALIDATION.md",
        "validation/*.json",
        ".env.example",
        "requirements.in",
        "requirements-dev.txt",
        "pyproject.toml",
        "tests/*.py",
        "scripts/*.py",
        "start.ps1",
        "deploy.py",
        "requirements.txt",
        "requirements.lock.txt",
        "packages.txt",
        "LICENSE",
    ]
    secrets = [
        v.encode()
        for k, v in dotenv_values(source_root / ".env").items()
        if v and (k.endswith("_TOKEN") or k.endswith("_KEY"))
    ]
    with tempfile.TemporaryDirectory(prefix="gaia-source-upload-") as folder:
        stage = Path(folder)
        for pattern in patterns:
            for source in source_root.glob(pattern):
                if any(secret in source.read_bytes() for secret in secrets):
                    parser.error("A source file contains a configured secret; upload refused.")
                target = stage / source.relative_to(source_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        if args.sdk == "static":
            readme = (stage / "README.md").read_text(encoding="utf-8")
            readme = readme.replace("sdk: gradio", "sdk: static").replace(
                "app_file: app.py", "app_file: index.html"
            )
            readme = "\n".join(
                line
                for line in readme.splitlines()
                if not line.startswith(("sdk_version:", "python_version:", "hf_oauth:"))
            )
            marker = "# GAIA Research Agent"
            readme = readme.replace(
                marker,
                marker
                + "\n\nThis Space is a **public source mirror**. The Python agent runs locally, or in a Gradio Space with eligible hosting. Static hosting does not run Python or hold inference secrets.",
                1,
            )
            (stage / "README.md").write_text(readme, encoding="utf-8")
            code_url = f"https://huggingface.co/spaces/{args.repo_id}/tree/main"
            score_html = ""
            score_path = source_root / "validation" / "official-score.json"
            if score_path.exists():
                score = json.loads(score_path.read_text(encoding="utf-8"))
                score_html = f"<p><strong>Official result: {float(score['score']):g}% — {int(score['correct_count'])}/20 correct.</strong> Passing target: 30%. <a href='https://huggingface.co/spaces/{args.repo_id}/blob/main/validation/official-score.json'>View scoring response</a>.</p>"
            (stage / "index.html").write_text(
                f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GAIA Research Agent · Source</title><style>body{{font:18px/1.6 system-ui;max-width:760px;margin:8vh auto;padding:24px;color:#182b3a;background:#f4f7f9}}a{{color:#005ea8}}code,pre{{background:#e7edf1;padding:4px 8px;border-radius:5px}}pre{{white-space:pre-wrap;padding:18px}}small{{color:#53616d}}</style><small>Hugging Face Agents Course · Final assignment</small><h1>GAIA Research Agent</h1>{score_html}<p>Public source code for an agent using OpenAI text, vision and speech models, evidence tools, checkpointed evaluation and the official course scoring API.</p><p>This is a source mirror. The Python backend runs locally; this static page does not run inference or store API keys.</p><p><a href="{code_url}" target="_blank" rel="noopener">Browse complete source code</a> · <a href="https://huggingface.co/spaces/{args.repo_id}/blob/main/README.md" target="_blank" rel="noopener">Setup instructions</a></p><pre>python -m pip install -r requirements.txt\n# Set OPENAI_API_KEY in a local .env file\npython app.py\npython -m gaia_agent evaluate --run-dir runs/my-run</pre><p>Answers are generated from tools and evidence. No benchmark answer key is embedded. The official scoring response determines whether the assignment passes.</p></html>''',
                encoding="utf-8",
            )
        api.upload_folder(
            repo_id=args.repo_id,
            repo_type="space",
            folder_path=folder,
            commit_message="Implement GAIA agent and course evaluation workflow",
        )
    print(f"Published: https://huggingface.co/spaces/{args.repo_id}")
    if args.sdk == "gradio":
        print(
            "Add OPENAI_API_KEY as a Space secret, and HF_DATASET_TOKEN if needed for gated attachments, then restart the Space."
        )
    else:
        print("Source mirror published. Run inference locally; no secrets were uploaded.")


if __name__ == "__main__":
    main()
