# Validation record

Checked locally on **October 26, 2026**, using Python 3.12 on Windows.

## Confirmed

- **48 automated tests passed** (`python -m pytest -q`, final run: 6.84 seconds).
- Ruff lint and formatting checks passed.
- `pip check` reported no broken requirements.
- The Gradio app constructed successfully without inference credentials.
- The local server returned HTTP 200 for its HTML and configuration; the configuration title was `GAIA Research Agent`. The restarted app displays the OpenAI configuration instructions.
- Stockfish 19 was installed from the official Stockfish GitHub release. A live synthetic mate-in-one position returned a mating SAN move and `#+1`. The local executable path is kept in `.env` and excluded from source archives.
- The live course API returned 20 questions.
- A live public web search returned six results.
- The webpage reader extracted 4,493 characters from the assignment page.
- The PDF reader extracted 39,795 characters from an arXiv paper.
- OpenAI `gpt-4.1` completed a live calculator tool-call round trip and returned `42`.
- OpenAI `gpt-4.1` correctly identified a synthetic solid-red image.
- OpenAI `gpt-transcribe` transcribed a locally synthesized WAV as "The answer is 42."
- The live inference checks made four API calls; see [validation/openai-smoke.json](validation/openai-smoke.json).
- The Hugging Face token authenticated successfully, but its inference account returned HTTP 402 with no remaining credits. Inference has now been switched to OpenAI. Hugging Face remains separate for course data and deployment.

The tests cover native tool-call round trips and malformed arguments, preservation of failed-attempt evidence, bounded arithmetic, spreadsheet row selection and exact decimal sums, missing formula caches, attachment path containment, private URL blocking, YouTube URL validation, token redaction, checkpoint reuse, retrying failed tasks, changed questions/configuration, full versus explicitly partial submission, repeated-submission caching, app construction, Space-owner authorization, provider credential separation, endpoint validation, OpenAI transcription payloads, the OpenAI completion-token parameter, and terminal account/quota failures.

Tests use synthetic tasks and mocked model/scoring responses. They do **not** measure GAIA accuracy. The mock score in a unit test is a test fixture only.

## Upstream attachment issue

During live checks, all five course attachment endpoints returned **HTTP 404** (`No file path associated with task_id`). The official GAIA dataset's attachment URL returned **HTTP 401**, with `GatedRepo`, without credentials; gated access was also denied when tested with the configured Hugging Face token. The account must first have GAIA dataset access.

The implementation includes a fallback to the exact attachment in `gaia-benchmark/GAIA`. The fallback's path selection, source provenance, and missing-access error were tested with fixtures. Actual gated downloads remain unverified until an authorized dataset-read token is configured. No benchmark answer metadata was downloaded.

The raw read-only smoke report is [validation/live-smoke.json](validation/live-smoke.json). Re-run it with `python scripts/smoke_live.py`; the new report is saved under `runs/live-smoke/`.

## Official assignment result

On October 26, 2026, the official course `/submit` endpoint returned **45.0%: 9/20 correct**, from 13 submitted answers. Its response confirmed: **High score updated on leaderboard.** This exceeds the course's 30% target. The exact response is preserved in [validation/official-score.json](validation/official-score.json). The passing result does not establish that every generated answer is correct.

The complete agent source is public at [adamitistime/gaia-research-agent](https://huggingface.co/spaces/adamitistime/gaia-research-agent/tree/main). It is hosted as a static source mirror; the evaluated Python agent ran locally. A Gradio deployment attempt was rejected because the account requires PRO for that hosting. No secrets were uploaded.

## Remaining limitations

- The first evaluation generated 13 answers and seven errors: five gated attachment failures and two unresolved questions. The scorer confirmed nine correct in aggregate and did not identify individual correct or incorrect answers. Per-question evidence is saved under `runs/openai-evaluation/`; a summary is in [validation/evaluation-summary.json](validation/evaluation-summary.json).
- OAuth behavior in a running hosted Gradio Space is not verified. The public source mirror is deployed and the Python backend works locally.
- Live YouTube captions, downloads, or video interpretation. Availability depends on YouTube and the runtime IP.

The assignment has a verified passing score. Gated attachment access and the unresolved questions remain opportunities to improve the score; they are not needed for the achieved pass.
