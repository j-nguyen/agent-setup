class PaymentError(Exception):
    """The provider rejected the request (e.g. card declined). Don't retry."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code = status, code


class TransientError(Exception):
    """The request may have failed for a temporary reason."""
