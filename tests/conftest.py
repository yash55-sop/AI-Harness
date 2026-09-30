"""Keep unit tests independent of the developer's environment."""

import pytest


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("integration"):
        return
    for name in ("OPENAI_API_KEY", "HARNESS_MAX_STEPS", "HARNESS_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
