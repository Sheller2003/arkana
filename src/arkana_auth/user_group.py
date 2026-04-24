from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UserGroup:
    group_id: int
    owner: str | None = None
    group_name: str | None = None
    obj_group: bool = False
    parent_group: int | None = None
    object_key: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "UserGroup":
        return cls(
            group_id=int(payload.get("group_id") or 0),
            owner=str(payload.get("owner")) if payload.get("owner") is not None else None,
            group_name=str(payload.get("group_name")) if payload.get("group_name") is not None else None,
            obj_group=bool(payload.get("obj_group") or False),
            parent_group=int(payload["parent_group"]) if payload.get("parent_group") is not None else None,
            object_key=str(payload.get("object_key")) if payload.get("object_key") is not None else None,
            created_at=str(payload.get("created_at")) if payload.get("created_at") is not None else None,
            updated_at=str(payload.get("updated_at")) if payload.get("updated_at") is not None else None,
        )


__all__ = ["UserGroup"]
