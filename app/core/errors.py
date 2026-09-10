"""Domain errors. User-facing messages are human-readable; details stay in logs."""


class RepurposeError(Exception):
    code = "internal_error"
    status = 500
    hint = ""

    def __init__(self, message: str, *, details: str = ""):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(RepurposeError):
    code = "not_found"
    status = 404


class ValidationError(RepurposeError):
    code = "invalid_input"
    status = 422


class MediaError(RepurposeError):
    code = "media_error"
    status = 422
    hint = "Check: source codec, file integrity, available disk space, FFmpeg installation."


class ProviderError(RepurposeError):
    code = "provider_error"
    status = 502
    hint = "Check provider URL/key, model name, and network connectivity."


class AuthError(RepurposeError):
    code = "unauthorized"
    status = 401
