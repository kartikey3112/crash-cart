"""Assertion helpers whose failure messages show the request and response, so a red test
on the dashboard explains itself without re-running anything."""

import httpx
from pydantic import BaseModel

from tests.api.schemas import ErrorBody


def describe(response: httpx.Response) -> str:
    request = response.request
    return f"{request.method} {request.url} -> {response.status_code}: {response.text[:400]}"


def expect_status(response: httpx.Response, expected: int) -> None:
    assert response.status_code == expected, f"expected HTTP {expected}; got {describe(response)}"


def expect_json[M: BaseModel](response: httpx.Response, expected: int, model: type[M]) -> M:
    """Check the status code, then validate the body against a response contract."""
    expect_status(response, expected)
    return model.model_validate(response.json())


def expect_error(response: httpx.Response, status: int, code: str) -> None:
    """Business errors must have the documented shape and a stable error code."""
    body = expect_json(response, status, ErrorBody)
    assert body.detail.code == code, f"expected error code {code!r}; got {describe(response)}"
