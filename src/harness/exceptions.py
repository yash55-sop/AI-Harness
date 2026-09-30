"""Public errors raised by the harness."""


class HarnessError(Exception):
    """Base class for harness failures."""


class ConfigurationError(HarnessError):
    """The supplied configuration is invalid."""


class ProviderError(HarnessError):
    """A model request failed or returned an invalid response."""


class AuthenticationError(ProviderError):
    """Provider credentials are missing or rejected."""


class ToolError(HarnessError):
    """A tool could not complete its operation."""


class ToolNotFoundError(ToolError):
    """A requested tool is not registered."""


class ToolValidationError(ToolError):
    """Tool arguments do not match the declared input schema."""


class DuplicateToolError(ConfigurationError):
    """Two tools have the same name."""


class MaxStepsExceeded(HarnessError):
    """The model did not finish within the configured step limit."""


class ContextLimitError(HarnessError):
    """The current conversation turn cannot fit in the context budget."""
