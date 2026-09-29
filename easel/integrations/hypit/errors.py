"""Errors raised by the Easel-Hypit integration."""


class HypitIntegrationError(ValueError):
    """A handoff, workspace, lifecycle, or Hypit CLI operation is invalid."""


class HypitCLIError(HypitIntegrationError):
    """A CLI invocation failed, optionally retaining a validated machine payload."""

    def __init__(self, message: str, *, payload=None, returncode: int | None = None):
        super().__init__(message)
        self.payload = payload
        self.returncode = returncode
