"""Fail release builds when the tag, package metadata, and import version differ."""

import re
import sys
from importlib.metadata import version

from harness import __version__


def check_release(tag: str) -> None:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise SystemExit("Release tag must have the form vMAJOR.MINOR.PATCH")
    if tag[1:] != __version__ or __version__ != version("lightweight-ai-harness"):
        raise SystemExit("Release tag, harness.__version__, and package metadata must match")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/check_release.py v0.1.0")
    check_release(sys.argv[1])
    print("Release version check passed")
