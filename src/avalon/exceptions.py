"""Custom exception types for Avalon game configuration and flow."""


class ConfigurationError(ValueError):
    """Raised when game configuration data violates official rules."""


class InvalidActionError(RuntimeError):
    """Raised when a game action violates the current rules or phase."""
