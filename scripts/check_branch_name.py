"""Reject commits on branches that don't follow `type/short-description`."""

import re
import subprocess
import sys

ALLOWED_TYPES = ("feature", "fix", "chore", "docs", "refactor", "test", "ci", "build")
PATTERN = re.compile(rf"^({'|'.join(ALLOWED_TYPES)})/[a-z0-9]+(-[a-z0-9]+)*$")
# main/develop are guarded by no-commit-to-branch; HEAD = detached (mid-rebase)
EXEMPT = {"main", "develop", "HEAD"}


def current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607 - git on PATH is expected
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    branch = current_branch()
    if branch in EXEMPT or PATTERN.match(branch):
        return 0
    print(
        f"Branch '{branch}' doesn't match type/short-description.\n"
        f"  Allowed types: {', '.join(ALLOWED_TYPES)}\n"
        f"  Example: feature/greenhouse-source\n"
        f"  Rename with: git branch -m <new-name>"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
