---
title: GAIA Research Agent
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.30.0
python_version: "3.12"
app_file: app.py
pinned: false
hf_oauth: true
license: mit
short_description: Evidence-seeking agent for the Agents Course final project
---

# GAIA Research Agent

A complete implementation for the [Hugging Face Agents Course final assignment](https://huggingface.co/learn/agents-course/unit4/hands-on), replacing the [template's fixed-answer agent](https://huggingface.co/spaces/agents-course/Final_Assignment_Template/tree/main) with a tool-calling research agent.

The course uses 20 GAIA Level 1 questions and a 30% target. This project generates answers from questions and evidence; it contains no hardcoded benchmark answers or answer-key retrieval. **Official result on October 26, 2026: 45% (9/20 correct), above the course passing threshold.** Thirteen generated answers were submitted; unresolved questions still counted against the full 20-question score. The leaderboard was updated for `adamitistime`. The exact response is saved in [validation/official-score.json](validation/official-score.json). See [VALIDATION.md](VALIDATION.md) for test scope and remaining limitations.

## Run locally on Windows

Python 3.12 is required. The workspace already has a virtual environment with dependencies installed.

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY` to your OpenAI API key and keep `INFERENCE_PROVIDER=openai`. Store secrets in the local file or Space settings, never in source code.
3. Start the app:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open [the local app](http://127.0.0.1:7860). On a fresh checkout, run `powershell -ExecutionPolicy Bypass -File .\start.ps1` to create the environment, install the pinned dependencies, and launch the app.

Text, image, and speech inference use the OpenAI API and its billing. The app can display its interface without a key, but solving requires one. Your Hugging Face token is kept separate for gated dataset access and optional Space deployment. Restart the local app after changing `.env`.

## Attachment availability

The live course API's `/questions` route worked during validation on October 26, 2026, but **all five `/files/{task_id}` requests returned 404**. The client therefore supports this fallback:

1. It first requests the course API's file endpoint.
2. If the endpoint returns 403 or 404, it downloads the exact attachment from `gaia-benchmark/GAIA`, at `2023/validation/<task_id>.<extension>`.
3. It never downloads the dataset's answer metadata or annotations.

To use the fallback, request/accept access on the [official GAIA dataset page](https://huggingface.co/datasets/gaia-benchmark/GAIA) yourself. Give your token read access to that gated dataset. You can put a separate read token in `HF_DATASET_TOKEN`; otherwise `HF_TOKEN` is used. Inference permission alone may not grant gated dataset reads. If attachments remain unavailable, other questions still run; explicit partial submission is available.

## Deploy to Hugging Face Spaces

Hugging Face rejected this account's Gradio hosting request with HTTP 402 because PRO is required for hosted Gradio/Docker Spaces. A **free public static source mirror** is deployed at [adamitistime/gaia-research-agent](https://huggingface.co/spaces/adamitistime/gaia-research-agent). The agent runs locally and uses that Space's public code URL for the official submission. The source mirror does not run Python or store inference keys.

Publish the same free source mirror with:

```powershell
.\.venv\Scripts\python.exe deploy.py YOUR_USERNAME/gaia-research-agent --sdk static
```

For accounts with eligible Gradio hosting, create a **public Gradio Space** using Python 3.12 and upload:

- `app.py`
- the `gaia_agent/` directory
- `requirements.txt` and `requirements.lock.txt`
- `packages.txt` (installs Stockfish on the Space)
- `README.md`, `VALIDATION.md`, `validation/`, and `LICENSE`

Alternatively use the included uploader with a write-capable token stored locally as `HF_DEPLOY_TOKEN`:

```powershell
.\.venv\Scripts\python.exe deploy.py YOUR_USERNAME/gaia-research-agent
```

The uploader refuses to update an existing Space unless you supply `--update`. It uploads only an explicit source-file allowlist. `.env`, runs, downloaded attachments, and the virtual environment are excluded.

In the Space's **Settings → Variables and secrets**:

- Add `OPENAI_API_KEY` as a **secret**. The default `INFERENCE_PROVIDER` is `openai`.
- Add `HF_DATASET_TOKEN` as a secret if you use a separate gated-dataset read token.
- Optionally add `MODEL_ID`, `VISION_MODEL_ID`, or `ASR_MODEL_ID` as variables.
- For an organization-owned Space, put your personal username in `ALLOWED_HF_USERS`. Other trusted users can be comma-separated there too.

The README enables Hugging Face OAuth. Log in with the Space owner's account before generating answers. Only the owner and explicitly allowed users can invoke inference, keeping a public Space from exposing your credits to anonymous visitors. Public visitors can still inspect the code.

The deploy script scans the upload against configured secret values and does not transfer local secrets. Add secrets only when deploying the running Gradio backend; a static source mirror needs none. Publish the Space before submitting so the leaderboard can link to your public implementation.

## Evaluation and submission

In the app:

1. Click **Generate / resume answers**. The runner fetches the current questions, downloads attachments, and runs the agent once per task.
2. Review answers and download `results.json`. It contains source URLs, tool calls, observations, attachment hashes, token counts, timing, and errors. It does not contain credentials or model-internal reasoning fields.
3. Retry failures with **Generate / resume answers**. Successful unchanged questions are reused. Changed questions are recomputed. Changed implementation or model configuration requires a new run.
4. Click **Submit answers to leaderboard** to obtain the official score. By default every current question must have an answer. To submit the answers available despite failures, select **Allow partial submission**. Unanswered questions still count against the full 20-question score.

Generating answers never automatically updates the leaderboard. Submission is a separate deliberate action. A successful submission response is saved; repeating the same payload returns the saved response. A timed-out POST is not automatically retried because it may already have reached the server.

Each browser session receives its own temporary run directory, and checkpoints survive interrupted tasks within that session. On free Spaces, disk can disappear on restart and Gradio browser state is not a persistent account history. Download completed logs before restarting. CLI run directories can be reopened explicitly.

### Command line

```powershell
# Readiness check: course API and configuration, no inference calls
.\.venv\Scripts\python.exe -m gaia_agent doctor

# Try one inexpensive reasoning question to validate your token/model
.\.venv\Scripts\python.exe -m gaia_agent solve "What is 6 multiplied by 7? Give only the number."

# Try one course task; then resume the same directory for the remaining tasks
.\.venv\Scripts\python.exe -m gaia_agent evaluate --limit 1 --run-dir runs/my-run
.\.venv\Scripts\python.exe -m gaia_agent evaluate --run-dir runs/my-run

# Submit after the code is public and answers have been reviewed
.\.venv\Scripts\python.exe -m gaia_agent submit --run-dir runs/my-run --username YOUR_USERNAME --space-id YOUR_USERNAME/gaia-research-agent

# If necessary, explicitly submit successful tasks despite unresolved questions
.\.venv\Scripts\python.exe -m gaia_agent submit --run-dir runs/my-run --username YOUR_USERNAME --space-id YOUR_USERNAME/gaia-research-agent --allow-partial
```

For local UI submission, set `AGENT_SPACE_ID=YOUR_USERNAME/gaia-research-agent` in `.env` and enter your username in the UI. On Spaces, the app derives the code URL from `SPACE_ID` and the username from OAuth.

## How the agent works

The agent uses the OpenAI chat API with native tool calls. Requests use the documented `max_completion_tokens` parameter; audio files use the OpenAI transcription API. Its bounded loop asks the model for either tool calls or a short final answer, executes tools, returns observations, and repeats. The prompt requests the exact answer format used by the course scorer. Formatting cleanup only removes wrapping code fences or a `FINAL ANSWER:` prefix; it does not rewrite names, numbers, or punctuation.

Default models, verified with live OpenAI calls on October 26, 2026:

| Purpose | Model | Configuration |
| --- | --- | --- |
| Reasoning and tool calls | `gpt-4.1` | `MODEL_ID` |
| Images and video frames | `gpt-4.1` | `VISION_MODEL_ID` |
| Speech recognition | `gpt-transcribe` | `ASR_MODEL_ID` |

The default text and vision model supports image input and function calling: see the [official GPT-4.1 documentation](https://developers.openai.com/api/docs/models/gpt-4.1). Speech recognition follows the [official file-transcription guide](https://developers.openai.com/api/docs/guides/speech-to-text). Model IDs remain configurable. Account-level authentication, permission, billing, or quota failures stop the run immediately and save a checkpoint.

Optional Hugging Face inference support remains available: set `INFERENCE_PROVIDER=huggingface`, `MODEL_BASE_URL=https://router.huggingface.co/v1`, `MODEL_ID=openai/gpt-oss-120b`, `VISION_MODEL_ID=Qwen/Qwen2.5-VL-72B-Instruct`, and `ASR_MODEL_ID=openai/whisper-large-v3`, with an inference-enabled `HF_TOKEN`. The client validates the selected provider's endpoint before sending credentials, preventing an OpenAI key from being sent to the Hugging Face router or vice versa.

| Tool | Purpose |
| --- | --- |
| `web_search`, `read_web` | Search, read HTML/PDFs, follow primary-source links, paginate long text |
| `read_file` | Read PDF/XLSX/DOCX/PPTX/text/CSV and Python source attachments |
| `spreadsheet_sum` | Sum explicitly selected cells using decimal arithmetic; report every included value |
| `calculator`, `text_operation` | Bounded arithmetic, reverse text, sort lists |
| `inspect_image` | Send an attachment or public image to the vision model |
| `transcribe_audio` | Transcribe an audio attachment through OpenAI (or the optional Hugging Face provider) |
| `youtube_transcript` | Retrieve timestamped captions |
| `inspect_video` | Download a short YouTube video; transcribe audio or inspect chosen frames |
| `analyze_chess` | Analyze a verified FEN with Stockfish and return SAN plus evaluation |

The model sees registered attachment names, not unrestricted filesystem access. There is no shell or arbitrary Python execution tool. Python attachments are read and reasoned through; complex source programs may exceed this approach. This choice avoids treating downloaded code as trusted instructions.

Other practical limits: scanned PDFs need OCR that is not implemented; spreadsheet formulas use existing cached values and are not recalculated; workbook reads are capped at 2,000 rows and 80 columns; webpage/PDF text is capped at 600,000 characters; videos are capped at ten minutes and 75 MiB; at most 12 video frames are inspected per tool call. Sparse frame sampling cannot guarantee an exact visual maximum. YouTube can block captions/downloads from data-center IPs. Stockfish quality depends on correct visual transcription of the board.

For local chess analysis, install [Stockfish](https://stockfishchess.org/download/) and set `STOCKFISH_PATH` to its executable. Spaces installs it via `packages.txt`.

## Files and verification

`app.py` contains the UI; `gaia_agent/agent.py` the loop; `tools.py` the tools; `course.py` the assignment API and attachment fallback; `evaluation.py` checkpoints and submission; `model.py` the OpenAI/Hugging Face model client. `deploy.py` publishes source files explicitly.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/smoke_live.py
```

The smoke script reads live questions, attempts attachments, checks search/web/PDF extraction and, in Hugging Face mode, model provider mappings, and saves a report under `runs/live-smoke/`. It never invokes inference or submits answers. Unit tests use synthetic fixtures and mocked models/scoring; their pass rate is not benchmark accuracy.
