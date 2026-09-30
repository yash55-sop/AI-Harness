"""Release checks prevent accidentally publishing a mismatched version."""

import pytest

from harness import __version__
from scripts.check_release import check_release


def test_release_version_is_valid() -> None:
    check_release(f"v{__version__}")


@pytest.mark.parametrize("tag", ["main", "0.1.0", "v99.0.0", "v0.1.0rc1"])
def test_invalid_release_tag(tag: str) -> None:
    with pytest.raises(SystemExit):
        check_release(tag)
