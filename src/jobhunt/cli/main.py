"""
Command-line interface.

Thin by design: parse arguments, call a use case, render the result. No
business logic lives here — that's in application/. Two commands for JT-1:
`run` (fetch and store openings) and `list` (show what's stored).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from jobhunt.bootstrap import Application, build_application
from jobhunt.config.settings import ConfigError, load_settings

_DEFAULT_CONFIG_PATH = Path("config.yaml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobhunt", description="Personal job search helper.")
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_CONFIG_PATH,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Fetch current openings and store new ones.")
    subparsers.add_parser("list", help="List jobs collected so far.")

    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1

    app = build_application(settings)

    if args.command == "run":
        return _run(app)
    if args.command == "list":
        return _list(app)
    return 1


def _run(app: Application) -> int:
    result = app.fetch_jobs.fetch(app.settings.companies)
    print(f"Found {result.total_found} job(s); {result.new_jobs} new.")
    if result.failures:
        print(f"{len(result.failures)} company(ies) failed:")
        for failure in result.failures:
            print(f"  - {failure.company}: {failure.reason}")
    return 0


def _list(app: Application) -> int:
    jobs = app.repository.list_jobs()
    if not jobs:
        print("No jobs stored yet. Run 'jobhunt run' first.")
        return 0
    print(f"{len(jobs)} job(s) stored:\n")
    for job in jobs:
        location = job.location or "—"
        posted = job.posted_at.date().isoformat() if job.posted_at else "—"
        print(f"  {job.title}  @ {job.company}  ({location})  posted {posted}")
        print(f"    {job.url}")
    return 0
