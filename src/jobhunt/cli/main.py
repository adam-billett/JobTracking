"""
Command-line interface.

Thin by design: parse arguments, call a use case, render the result. No
business logic lives here. Errors the domain raises on purpose (job not
found, already applied, ...) are printed as a message with exit code 1;
anything else is a bug and is allowed to show its traceback.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from jobhunt.application.track_application import TrackedJob
from jobhunt.bootstrap import Application, build_application
from jobhunt.config.settings import ConfigError, Settings, load_settings
from jobhunt.domain.errors import JobHuntError

_DEFAULT_CONFIG_PATH = Path("config.yaml")
_SHORT_ID_LENGTH = 8
_JOB_HELP = "Job id, or any unique start of it (the short id shown by `jobhunt list`)."

Builder = Callable[[Settings], Application]


def main(argv: list[str] | None = None, *, build: Builder = build_application) -> int:
    """
    Run one CLI command and return its exit code.

    `build` creates the wired-up application. The installed `jobhunt`
    command uses the real one; tests pass their own so the CLI runs against
    a fake job source and a fixed clock.
    """
    args = _parser().parse_args(argv)

    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    app = build(settings)
    try:
        return _dispatch(app, args)
    except JobHuntError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobhunt", description="Personal job search helper.")
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_CONFIG_PATH,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("run", help="Fetch current openings and store new ones.")
    commands.add_parser("list", help="List stored jobs with their short id and status.")

    show_parser = commands.add_parser("show", help="Show one job and its application details.")
    show_parser.add_argument("job", help=_JOB_HELP)

    apply_parser = commands.add_parser("apply", help="Mark a job as applied today.")
    apply_parser.add_argument("job", help=_JOB_HELP)
    apply_parser.add_argument("--link", help="Tracking or confirmation link.")
    apply_parser.add_argument("--contact", help="Contact person for this application.")

    update_parser = commands.add_parser("update", help="Save a tracking link and/or contact.")
    update_parser.add_argument("job", help=_JOB_HELP)
    update_parser.add_argument("--link", help="Tracking or confirmation link.")
    update_parser.add_argument("--contact", help="Contact person for this application.")

    note_parser = commands.add_parser("note", help="Add a dated note to a job.")
    note_parser.add_argument("job", help=_JOB_HELP)
    note_parser.add_argument("text", help="The note. Put it in quotes if it has spaces.")

    return parser


def _dispatch(app: Application, args: argparse.Namespace) -> int:
    command = args.command

    if command == "run":
        return _run(app)
    if command == "list":
        return _list(app)
    if command == "show":
        _print_details(app.track.show(args.job))
        return 0
    if command == "apply":
        tracked = app.track.apply(args.job, tracking_url=args.link, contact=args.contact)
        applied_on = _date(tracked.application.applied_at)
        print(f"Marked applied on {applied_on}: {_summary(tracked)}")
        return 0
    if command == "update":
        if args.link is None and args.contact is None:
            print("Error: give --link, --contact, or both.", file=sys.stderr)
            return 1
        tracked = app.track.update_details(args.job, tracking_url=args.link, contact=args.contact)
        print(f"Updated: {_summary(tracked)}")
        return 0
    if command == "note":
        tracked = app.track.add_note(args.job, args.text)
        print(f"Note added: {_summary(tracked)}")
        return 0
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
    tracked_jobs = app.track.list_tracked()
    if not tracked_jobs:
        print("No jobs stored yet. Run 'jobhunt run' first.")
        return 0

    print(f"{len(tracked_jobs)} job(s) stored:\n")
    for tracked in tracked_jobs:
        job = tracked.job
        print(
            f"  {_short_id(job.id)}  [{tracked.application.status}]  {job.title}"
            f"  @ {job.company}  ({job.location or '—'})  posted {_date(job.posted_at)}"
        )
        print(f"    {job.url}")
    return 0


def _print_details(tracked: TrackedJob) -> None:
    job, application = tracked.job, tracked.application
    print(f"{job.title} @ {job.company}")
    print(f"  id:        {job.id}")
    print(f"  location:  {job.location or '—'}")
    print(f"  posted:    {_date(job.posted_at)}")
    print(f"  posting:   {job.url}")
    print(f"  status:    {application.status}")
    print(f"  applied:   {_date(application.applied_at)}")
    print(f"  tracking:  {application.tracking_url or '—'}")
    print(f"  contact:   {application.contact or '—'}")
    if not application.notes:
        print("  notes:     —")
        return
    print("  notes:")
    for note in application.notes:
        print(f"    {_date(note.created_at)}  {note.body}")


def _summary(tracked: TrackedJob) -> str:
    return f"{_short_id(tracked.job.id)}  {tracked.job.title} @ {tracked.job.company}"


def _short_id(job_id: str) -> str:
    return job_id[:_SHORT_ID_LENGTH]


def _date(value: datetime | None) -> str:
    # Times are stored in UTC; show the date in my own timezone, so applying
    # at 9 pm Eastern isn't recorded as the next day.
    return value.astimezone().date().isoformat() if value is not None else "—"
