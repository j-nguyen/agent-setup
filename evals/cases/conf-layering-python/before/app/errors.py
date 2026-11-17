class AppError(Exception):
    status = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status = 404


class ValidationError(AppError):
    status = 400
