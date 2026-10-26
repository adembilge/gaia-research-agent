"""Gradio entry point, deployable directly as a public Hugging Face Space."""

import json
import os
import tempfile
from pathlib import Path

import gradio as gr

from gaia_agent.agent import Agent
from gaia_agent.config import Settings, safe_error
from gaia_agent.evaluation import Evaluation, status_text, table_rows


def authorize(profile):
    space_id = os.getenv("SPACE_ID", "")
    if not space_id:
        return  # local server binds to 127.0.0.1
    owner = space_id.split("/")[0]
    allowed = {owner, *filter(None, (u.strip() for u in os.getenv("ALLOWED_HF_USERS", "").split(",")))}
    if not profile or profile.username not in allowed:
        raise gr.Error(
            "Log in with the Space owner's account, or ask the owner to add your username to ALLOWED_HF_USERS."
        )


def run_evaluation(run_dir, profile: gr.OAuthProfile | None):
    authorize(profile)
    settings = Settings.from_env()
    directory = Path(run_dir) if run_dir else Path(tempfile.mkdtemp(prefix="evaluation-", dir=run_root()))
    evaluator = Evaluation(settings, directory)
    try:
        for state in evaluator.run():
            yield str(directory), status_text(state), table_rows(state), str(evaluator.path), state
    except Exception as exc:
        raise gr.Error(safe_error(exc, settings.token)) from None


def run_root():
    root = Path("runs").resolve()
    root.mkdir(exist_ok=True)
    return str(root)


def submit_answers(run_dir, local_username, allow_partial, profile: gr.OAuthProfile | None):
    authorize(profile)
    if not run_dir:
        raise gr.Error("Run the evaluation first.")
    username = profile.username if profile else local_username.strip()
    space_id = os.getenv("SPACE_ID", "") or os.getenv("AGENT_SPACE_ID", "")
    if not space_id:
        raise gr.Error(
            "Set AGENT_SPACE_ID=username/space-name locally, or deploy this app to a public Space."
        )
    settings = Settings.from_env()
    try:
        result = Evaluation(settings, Path(run_dir)).submit(
            username, f"https://huggingface.co/spaces/{space_id}/tree/main", allow_partial=allow_partial
        )
        return json.dumps(result, indent=2)
    except Exception as exc:
        raise gr.Error(safe_error(exc, settings.token)) from None


def solve_one(question, profile: gr.OAuthProfile | None):
    authorize(profile)
    settings = Settings.from_env()
    try:
        if not question.strip():
            raise ValueError("Enter a question first.")
        result = Agent(settings).solve(question)
        return result["answer"], result
    except Exception as exc:
        raise gr.Error(safe_error(exc, settings.token)) from None


def build_app():
    with gr.Blocks(title="GAIA Research Agent") as demo:
        gr.Markdown("# GAIA Research Agent\nHugging Face Agents Course · Final project")
        gr.Markdown(
            "Configure `OPENAI_API_KEY` in your Space secrets or local `.env`. Generate and review answers, then submit them to the course leaderboard. Model calls use your OpenAI API credits. Hugging Face tokens are used separately for gated course files and deployment."
        )
        if os.getenv("SPACE_ID"):
            gr.LoginButton()
        run_dir = gr.State("")
        result_state = gr.State({})
        with gr.Tab("Course evaluation"):
            gr.Markdown(
                "**1. Generate** answers to the 20 course questions. **2. Review** answers and the downloadable tool log. **3. Submit** to receive your actual score. Resume retries failed questions and reuses completed answers."
            )
            with gr.Row():
                run_button = gr.Button("Generate / resume answers", variant="primary")
                stop_button = gr.Button("Stop after current task")
                new_button = gr.Button("Start fresh")
            status = gr.Textbox(label="Progress", value="Ready. No evaluation score yet.", interactive=False)
            results = gr.Dataframe(
                headers=["Task ID", "Question", "Status", "Answer", "Error"],
                datatype=["str"] * 5,
                interactive=False,
                wrap=True,
            )
            log_file = gr.File(label="Download answers, sources, tool observations and token counts")
            with gr.Accordion("Inspect run details", open=False):
                details = gr.JSON()
            local_username = gr.Textbox(
                label="Hugging Face username (local runs only)", visible=not bool(os.getenv("SPACE_ID"))
            )
            allow_partial = gr.Checkbox(
                label="Allow partial submission (unresolved questions count as incorrect)", value=False
            )
            submit_button = gr.Button("Submit answers to leaderboard")
            submission = gr.Textbox(label="Official scoring response", lines=6, interactive=False)
            event = run_button.click(
                run_evaluation,
                [run_dir],
                [run_dir, status, results, log_file, result_state],
                api_name=False,
                concurrency_limit=1,
                concurrency_id="inference",
            )
            stop_button.click(fn=None, cancels=[event], api_name=False)
            new_button.click(
                lambda: ("", "Ready for a fresh run.", [], None, {}, {}),
                outputs=[run_dir, status, results, log_file, result_state, details],
                cancels=[event],
                api_name=False,
            )
            result_state.change(lambda state: state, [result_state], [details], api_name=False)
            submit_button.click(
                submit_answers,
                [run_dir, local_username, allow_partial],
                [submission],
                api_name=False,
                concurrency_limit=1,
                concurrency_id="inference",
            )
        with gr.Tab("Try a question"):
            question = gr.Textbox(
                label="Question", lines=4, placeholder="Ask a research or reasoning question..."
            )
            solve_button = gr.Button("Solve", variant="primary")
            answer = gr.Textbox(label="Answer", interactive=False)
            trace = gr.JSON(label="Evidence and usage")
            solve_button.click(
                solve_one,
                [question],
                [answer, trace],
                api_name=False,
                concurrency_limit=1,
                concurrency_id="inference",
            )
    return demo


if __name__ == "__main__":
    build_app().queue(default_concurrency_limit=1).launch(
        server_name="0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1",
        server_port=int(os.getenv("PORT", "7860")),
        share=False,
    )
