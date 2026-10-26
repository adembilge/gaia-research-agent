import argparse
import json
import shutil
from pathlib import Path

from .agent import Agent
from .config import Settings, safe_error
from .course import CourseClient
from .evaluation import Evaluation, status_text


def main():
    parser = argparse.ArgumentParser(description="Hugging Face Agents Course final project")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "doctor", help="Check local configuration and live course API without using inference credits"
    )
    solve = commands.add_parser("solve", help="Solve one custom question")
    solve.add_argument("question")
    evaluate = commands.add_parser("evaluate", help="Generate answers and save checkpoints; does not submit")
    evaluate.add_argument("--run-dir", type=Path, default=Path("runs/default"))
    evaluate.add_argument("--limit", type=int)
    submit = commands.add_parser("submit", help="Submit a completed run to the course leaderboard")
    submit.add_argument("--run-dir", type=Path, default=Path("runs/default"))
    submit.add_argument("--username", required=True)
    submit.add_argument("--space-id", required=True, help="username/space-name of your public code Space")
    submit.add_argument(
        "--allow-partial",
        action="store_true",
        help="Submit available answers; missing questions count as incorrect",
    )
    args = parser.parse_args()
    settings = Settings.from_env()
    try:
        if args.command == "doctor":
            questions = CourseClient().questions()
            print(
                json.dumps(
                    {
                        "inference_provider": settings.provider,
                        "inference_key": "configured" if settings.token else "missing",
                        "settings": settings.public(),
                        "course_questions": len(questions),
                        "stockfish": bool(
                            shutil.which("stockfish")
                            or __import__("os").getenv("STOCKFISH_PATH")
                            or Path("/usr/games/stockfish").exists()
                        ),
                        "inference_tested": False,
                    },
                    indent=2,
                )
            )
        elif args.command == "solve":
            print(json.dumps(Agent(settings).solve(args.question), ensure_ascii=False, indent=2))
        elif args.command == "evaluate":
            for state in Evaluation(settings, args.run_dir).run(limit=args.limit):
                print(status_text(state), flush=True)
        elif args.command == "submit":
            result = Evaluation(settings, args.run_dir).submit(
                args.username,
                f"https://huggingface.co/spaces/{args.space_id}/tree/main",
                allow_partial=args.allow_partial,
            )
            print(json.dumps(result, indent=2))
    except Exception as exc:
        parser.exit(1, safe_error(exc, settings.token) + "\n")


if __name__ == "__main__":
    main()
