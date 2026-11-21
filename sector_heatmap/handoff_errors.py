"""Boundary errors: only the owned adapter can prove no submit call began."""
class PreflightRejected(ValueError):
    """Raised before the first broker-mutating request; never used after it."""

class IncompleteAnalysis(ValueError):
    """Execution remains blocked, while read-only findings survive for reporting."""
    def __init__(self,message,report):
        super().__init__(message)
        self.report=report

class BrokerAuthenticationRequired(ValueError):
    """Latest saved credentials were rejected; never retry a trading operation."""
