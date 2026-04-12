from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def build_help(
    *,
    endpoint: str,
    method: str,
    description: str,
    query_parameters: dict[str, str] | None = None,
    path_parameters: dict[str, str] | None = None,
    body: str | None = None,
    returns: str | None = None,
) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "method": method.upper(),
        "description": description,
        "path_parameters": path_parameters or {},
        "query_parameters": query_parameters or {},
        "body": body,
        "returns": returns,
    }


def with_help(response: Any, *, help_enabled: bool, help_payload: dict[str, Any]) -> Any:
    if not help_enabled:
        return response
    if isinstance(response, BaseModel):
        data: dict[str, Any] = response.model_dump()
    elif isinstance(response, dict):
        data = dict(response)
    else:
        data = {"result": response}
    data["_help"] = help_payload
    return data
