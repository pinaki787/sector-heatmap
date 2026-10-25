"""Boundary errors: only the owned adapter can prove no submit call began."""
class PreflightRejected(ValueError):
    """Raised before the first broker-mutating request; never used after it."""
