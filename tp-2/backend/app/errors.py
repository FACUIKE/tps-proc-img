"""
Translation of exceptions to HTTP responses. Given.

Every error leaves the API with the same format:

    {"detail": {"code": "DOCUMENT_NOT_FOUND", "message": "..."}}

Endpoints do not need try/except: they let the exceptions go up and these
handlers answer.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from docscan import DocumentNotFound, InvalidImage, ScanError


class ApiError(Exception):
    """An error of the API itself (not of the core), with its status and code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ScanNotFound(ApiError):
    """There is no scan with that id. TODO (team): raise it from your storage."""

    def __init__(self, scan_id: str) -> None:
        super().__init__(404, "SCAN_NOT_FOUND", f"No existe un escaneo con id {scan_id!r}.")


# Core exceptions → (HTTP status, code). Subclasses inherit the entry of their parent.
CORE_ERRORS: dict[type[ScanError], tuple[int, str]] = {
    InvalidImage: (400, "INVALID_FILE"),
    DocumentNotFound: (422, "DOCUMENT_NOT_FOUND"),
    ScanError: (400, "SCAN_ERROR"),
}


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(ScanError)
    async def handle_core_error(request: Request, exc: ScanError) -> JSONResponse:
        for exc_type in type(exc).__mro__:
            if exc_type in CORE_ERRORS:
                status, code = CORE_ERRORS[exc_type]
                return error_response(status, code, str(exc))
        return error_response(400, "SCAN_ERROR", str(exc))  # pragma: no cover
