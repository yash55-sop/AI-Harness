"""Structured metadata logging without prompts, tool contents or credentials."""

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        values: dict[str, Any] = {"level": record.levelname, "event": record.getMessage()}
        for key in ("step", "tool", "duration", "error_type"):
            if hasattr(record, key):
                values[key] = getattr(record, key)
        return json.dumps(values)


def agent_logger(verbose: bool, level: str) -> logging.Logger:
    if not verbose:
        return logging.getLogger("harness.agent")
    logger = logging.Logger("harness.agent", level=logging.INFO if level == "WARNING" else level)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger
