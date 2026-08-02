class DaikinServiceException(RuntimeError):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class DaikinAuthException(DaikinServiceException):
    """Raised when the client cannot obtain or maintain a usable access token."""

    def __init__(self, message: str, status: int = 401):
        super().__init__(message, status)
