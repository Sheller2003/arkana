from __future__ import annotations

from enum import Enum


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


__all__ = ["CellType"]
