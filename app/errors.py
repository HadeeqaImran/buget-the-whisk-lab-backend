from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def _field_name(location: Sequence[Any]) -> str:
    parts = [str(part) for part in location if part not in {"body", "query", "path"}]
    return ".".join(parts) if parts else "request"


def _friendly_validation_message(field: str, error: dict[str, Any]) -> str:
    error_type = str(error.get("type", ""))
    context = error.get("ctx") or {}

    if field == "email" and ("pattern" in error_type or "string_pattern_mismatch" in error_type):
        return "Enter a valid email address"
    if field == "password" and "string_too_short" in error_type:
        return f"Password must be at least {context.get('min_length', 8)} characters"
    if field == "name" and "string_too_short" in error_type:
        return "Name is required"
    if "decimal" in error_type or "greater_than_equal" in error_type:
        return "Enter a valid amount"
    if "missing" in error_type:
        return "This field is required"

    return str(error.get("msg", "Invalid value"))


def _validation_fields(exc: RequestValidationError) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for error in exc.errors():
        field = _field_name(error.get("loc", []))
        message = _friendly_validation_message(field, error)
        fields.setdefault(field, []).append(message)
    return fields


def error_response(status_code: int, message: str, code: str, fields: dict[str, list[str]] | None = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if fields:
        payload["error"]["fields"] = fields
    return JSONResponse(status_code=status_code, content=payload)


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    response = error_response(exc.status_code, detail, "http_error")
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = _validation_fields(exc)
    readable_fields = ", ".join(fields.keys())
    message = f"Please check: {readable_fields}" if readable_fields else "Please check your input"
    return error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, message, "validation_error", fields)


async def integrity_exception_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    message = "This record conflicts with existing data"
    original = str(getattr(exc, "orig", ""))
    if "users_email" in original or "users.email" in original or "unique" in original.lower():
        message = "Email already registered"
    return error_response(status.HTTP_409_CONFLICT, message, "conflict")


async def database_exception_handler(_: Request, __: SQLAlchemyError) -> JSONResponse:
    return error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Database is unavailable. Please try again shortly.",
        "database_unavailable",
    )


async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Something went wrong. Please try again.",
        "server_error",
    )
