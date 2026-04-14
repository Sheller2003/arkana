from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse


class CellType(str, Enum):
    PY_CODE = "py_code"
    PY_RESULT = "py_result"
    R_CODE = "r_code"
    R_RESULT = "r_result"
    MD = "md"
    HTML = "html"
    TEXT = "text"
    CSV = "csv"
    FILE = "file"
    FILE_CSV = "file_csv"
    FILE_JSON = "file_json"
    FILE_JPG = "file_jpg"
    RDATA = "rdata"

    @classmethod
    def infer_file_type(cls, content: str | None, default: str | None = None) -> str:
        normalized = str(content or "").strip()
        if not normalized:
            return default or cls.FILE.value
        parsed = urlparse(normalized)
        file_name = parsed.path if parsed.scheme else normalized
        suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if suffix == "csv":
            return cls.FILE_CSV.value
        if suffix == "json":
            return cls.FILE_JSON.value
        if suffix in {"jpg", "jpeg"}:
            return cls.FILE_JPG.value
        return default or cls.FILE.value

    @classmethod
    def is_file_type(cls, value: str | None) -> bool:
        normalized = str(value or "").strip().lower()
        return normalized in {
            cls.FILE.value,
            cls.FILE_CSV.value,
            cls.FILE_JSON.value,
            cls.FILE_JPG.value,
        }

    @classmethod
    def is_workspace_file_reference_type(cls, value: str | None) -> bool:
        normalized = str(value or "").strip().lower()
        return cls.is_file_type(normalized) or normalized == cls.RDATA.value


__all__ = ["CellType"]
