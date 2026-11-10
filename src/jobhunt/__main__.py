"""Entry point for `python -m jobhunt`."""

from __future__ import annotations

import sys

from jobhunt.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
