from __future__ import annotations

import json
import secrets
import shutil
import tempfile
import threading
import time
from copy import deepcopy
from pathlib import Path

from src.mdd_arkana_object.ark_obj_interface import Arkana_Object_Interface


class ArkanaNotes(Arkana_Object_Interface):
    arkana_type: str = "ark_notes"
    chapters: list[dict] | None = None
    buffer_id: str | None = None

    BUFFER_TTL_SECONDS = 24 * 60 * 60
    _buffer_lock = threading.Lock()
    _buffer: dict[str, dict[str, object]] = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        buffer_id = kwargs.get("buffer_id")
        self.buffer_id = str(buffer_id) if buffer_id not in (None, "") else None
        chapters = kwargs.get("chapters")
        if isinstance(chapters, list):
            self.chapters = [dict(chapter) for chapter in chapters if isinstance(chapter, dict)]

    def _header_table_name(self) -> str:
        if not self._has_table("arkana_notes_header"):
            raise RuntimeError("Required table 'arkana_notes_header' not found")
        return "arkana_notes_header"

    def _chapters_table_name(self) -> str:
        if not self._has_table("arkana_notes_chapter"):
            raise RuntimeError("Required table 'arkana_notes_chapter' not found")
        return "arkana_notes_chapter"

    def load(self):
        if self.arkana_id is None:
            return self

        try:
            _, cursor = self._ensure_model_cursor()
            header_table = self._header_table_name()
            chapters_table = self._chapters_table_name()

            cursor.execute(
                f"SELECT 1 FROM {header_table} WHERE arkana_id = %s LIMIT 1",
                (int(self.arkana_id),),
            )
            if cursor.fetchone() is None:
                self.chapters = []
                return self

            cursor.execute(
                (
                    f"SELECT chapter_id, order_id, chapter_key, taggs, content, files "
                    f"FROM {chapters_table} "
                    "WHERE arkana_object_id = %s "
                    "ORDER BY order_id, chapter_id"
                ),
                (int(self.arkana_id),),
            )
            rows = cursor.fetchall() or []
            self.chapters = []
            for row in rows:
                raw_files = row[5] if len(row) > 5 else None
                files = self._files_to_list(raw_files)
                self.chapters.append(
                    {
                        "chapter_id": int(row[0]) if row[0] is not None else None,
                        "order_id": int(row[1]) if row[1] is not None else None,
                        "key": str(row[2]) if row[2] is not None else None,
                        "taggs": self._taggs_to_storage(row[3]),
                        "content": str(row[4]) if row[4] is not None else "",
                        "files": files,
                    }
                )
            return self
        finally:
            self._close_model()

    def to_json(self) -> dict:
        data = super().to_json()
        self._normalize_chapters()
        data["chapters"] = self._serialize_chapters_for_api(self.chapters or [])
        if self.buffer_id:
            data["buffer_id"] = self.buffer_id
            data["object_id"] = f"tmp_{self.buffer_id}"
        return data

    def save(self):
        if self.arkana_id in (None, 0):
            self._save_to_buffer()
            return self
        return self._save_persisted()

    def save_to_db(self):
        previous_buffer_id = self.buffer_id
        if self.arkana_id in (None, 0):
            self.arkana_id = None
        self.buffer_id = None
        self._save_persisted()
        if previous_buffer_id:
            self._move_buffer_files_to_object_storage(previous_buffer_id)
            self.delete_buffer(previous_buffer_id)
        return self

    def _save_persisted(self):
        super().save()
        if self.arkana_id in (None, 0):
            return self

        try:
            _, cursor = self._ensure_model_cursor()
            header_table = self._header_table_name()
            chapters_table = self._chapters_table_name()

            cursor.execute(
                f"SELECT 1 FROM {header_table} WHERE arkana_id = %s LIMIT 1",
                (int(self.arkana_id),),
            )
            exists = cursor.fetchone()
            if exists is None:
                cursor.execute(
                    f"INSERT INTO {header_table} (arkana_id) VALUES (%s)",
                    (int(self.arkana_id),),
                )

            if self.chapters is None:
                self.chapters = []

            self._normalize_chapters()

            cursor.execute(
                f"DELETE FROM {chapters_table} WHERE arkana_object_id = %s",
                (int(self.arkana_id),),
            )

            for chapter in self.chapters:
                cursor.execute(
                    (
                        f"INSERT INTO {chapters_table} "
                        "(arkana_object_id, chapter_id, order_id, chapter_key, taggs, content, files) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
                    ),
                    (
                        int(self.arkana_id),
                        int(chapter["chapter_id"]),
                        int(chapter["order_id"]),
                        str(chapter.get("key") or f"chapter_{chapter['chapter_id']}"),
                        self._taggs_to_storage(chapter.get("taggs")),
                        str(chapter.get("content") or ""),
                        json.dumps(self._files_to_list(chapter.get("files"))),
                    ),
                )

            self._commit_model()
        except Exception:
            self._rollback_model()
            raise
        finally:
            self._close_model()

        return self

    @classmethod
    def load_from_buffer(cls, buffer_id: str) -> "ArkanaNotes":
        normalized = str(buffer_id).strip()
        cls._prune_expired_buffers()
        with cls._buffer_lock:
            entry = cls._buffer.get(normalized)
            if entry is None:
                raise KeyError(normalized)
            snapshot = deepcopy(entry.get("snapshot") or {})
        snapshot["arkana_id"] = 0
        snapshot["buffer_id"] = normalized
        return cls(**snapshot)

    @classmethod
    def delete_buffer(cls, buffer_id: str) -> bool:
        normalized = str(buffer_id).strip()
        with cls._buffer_lock:
            entry = cls._buffer.pop(normalized, None)
        if entry is None:
            return False
        cls._delete_buffer_directory(normalized)
        return True

    @classmethod
    def get_buffer_directory(cls, buffer_id: str) -> Path:
        cls._prune_expired_buffers()
        path = cls._buffer_root() / str(buffer_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def reset_chapters(self):
        if self.chapters is None:
            self.chapters = []
        else:
            self.chapters.clear()
        return self

    def append_chapter(
        self,
        *,
        key: str,
        content: str = "",
        taggs: list[str] | str | None = None,
        files: list[str] | str | None = None,
    ) -> int:
        if self.chapters is None:
            self.chapters = []
        chapter_id = self._next_free_chapter_id()
        self.chapters.append(
            {
                "chapter_id": chapter_id,
                "order_id": len(self.chapters) + 1,
                "key": str(key).strip() or f"chapter_{chapter_id}",
                "taggs": self._taggs_to_storage(taggs),
                "content": str(content or ""),
                "files": self._files_to_list(files),
            }
        )
        return chapter_id

    def get_chapter(self, identifier: int | str) -> dict | None:
        if self.chapters is None:
            return None
        resolved = self._find_chapter(identifier)
        if resolved is None:
            return None
        return self._serialize_chapter_for_api(resolved)

    def update_chapter(self, identifier: int | str, payload: dict) -> dict | None:
        if self.chapters is None:
            self.chapters = []
        chapter = self._find_chapter(identifier)
        if chapter is None:
            return None
        if "key" in payload:
            chapter["key"] = str(payload.get("key") or "").strip() or chapter["key"]
        if "content" in payload:
            chapter["content"] = str(payload.get("content") or "")
        if "taggs" in payload:
            chapter["taggs"] = self._taggs_to_storage(payload.get("taggs"))
        if "files" in payload:
            chapter["files"] = self._files_to_list(payload.get("files"))
        return self._serialize_chapter_for_api(chapter)

    def delete_chapter(self, identifier: int | str):
        if self.chapters is None:
            self.chapters = []
            return self
        for index, chapter in enumerate(self.chapters):
            if self._matches_chapter_identifier(chapter, identifier):
                self.chapters.pop(index)
                self._normalize_chapters()
                break
        return self

    def _find_chapter(self, identifier: int | str) -> dict | None:
        if self.chapters is None:
            return None
        for chapter in self.chapters:
            if self._matches_chapter_identifier(chapter, identifier):
                return chapter
        return None

    @staticmethod
    def _matches_chapter_identifier(chapter: dict, identifier: int | str) -> bool:
        try:
            int_identifier = int(identifier)
        except (TypeError, ValueError):
            int_identifier = None
        if int_identifier is not None and chapter.get("chapter_id") == int_identifier:
            return True
        return str(chapter.get("key") or "") == str(identifier)

    def _next_free_chapter_id(self) -> int:
        if self.chapters is None:
            return 1
        current_max = 0
        for chapter in self.chapters:
            try:
                current_max = max(current_max, int(chapter.get("chapter_id") or 0))
            except (TypeError, ValueError):
                continue
        return current_max + 1

    def _save_to_buffer(self) -> None:
        self._normalize_chapters()
        if not self.buffer_id:
            self.buffer_id = self._new_buffer_id()
        snapshot = self.to_json()
        snapshot["arkana_id"] = 0
        snapshot["buffer_id"] = self.buffer_id
        snapshot["object_id"] = f"tmp_{self.buffer_id}"
        with self._buffer_lock:
            self._prune_expired_buffers(locked=True)
            self._buffer[self.buffer_id] = {
                "expires_at": time.monotonic() + self.BUFFER_TTL_SECONDS,
                "snapshot": deepcopy(snapshot),
            }

    @classmethod
    def _prune_expired_buffers(cls, *, locked: bool = False) -> None:
        def _do_prune() -> None:
            now = time.monotonic()
            expired = [buffer_id for buffer_id, entry in cls._buffer.items() if float(entry.get("expires_at") or 0) <= now]
            for buffer_id in expired:
                cls._buffer.pop(buffer_id, None)
                cls._delete_buffer_directory(buffer_id)

        if locked:
            _do_prune()
            return
        with cls._buffer_lock:
            _do_prune()

    @staticmethod
    def _new_buffer_id() -> str:
        return secrets.token_hex(8)

    @staticmethod
    def _buffer_root() -> Path:
        return Path(tempfile.gettempdir()) / "arkana_notes_buffer"

    @classmethod
    def _object_storage_root(cls) -> Path:
        return cls._buffer_root() / "objects"

    @classmethod
    def _delete_buffer_directory(cls, buffer_id: str) -> None:
        try:
            shutil.rmtree(cls._buffer_root() / str(buffer_id), ignore_errors=True)
        except Exception:
            return

    def _move_buffer_files_to_object_storage(self, buffer_id: str) -> None:
        source_dir = self._buffer_root() / str(buffer_id) / "files"
        if not source_dir.exists():
            return
        target_dir = self._object_storage_root() / str(self.arkana_id) / "files"
        target_dir.mkdir(parents=True, exist_ok=True)
        for source_path in source_dir.iterdir():
            if not source_path.is_file():
                continue
            target_path = target_dir / source_path.name
            if target_path.exists():
                stem = target_path.stem
                suffix = target_path.suffix
                counter = 1
                while target_path.exists():
                    target_path = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(source_path), str(target_path))

    def _normalize_chapters(self) -> None:
        if self.chapters is None:
            return
        used_keys: set[str] = set()
        for order_id, chapter in enumerate(self.chapters, start=1):
            chapter_id = chapter.get("chapter_id")
            try:
                normalized_chapter_id = int(chapter_id) if chapter_id is not None else 0
            except (TypeError, ValueError):
                normalized_chapter_id = 0
            if normalized_chapter_id <= 0:
                normalized_chapter_id = self._next_free_chapter_id()
            chapter["chapter_id"] = normalized_chapter_id
            chapter["order_id"] = order_id
            chapter["key"] = self._ensure_unique_chapter_key(chapter.get("key"), normalized_chapter_id, used_keys)
            chapter["taggs"] = self._taggs_to_storage(chapter.get("taggs"))
            chapter["content"] = str(chapter.get("content") or "")
            chapter["files"] = self._files_to_list(chapter.get("files"))

    @staticmethod
    def _ensure_unique_chapter_key(proposed_key, chapter_id: int, used_keys: set[str]) -> str:
        base_key = str(proposed_key).strip() if proposed_key is not None else ""
        if not base_key:
            base_key = f"chapter_{chapter_id}"
        unique_key = base_key
        suffix = 1
        while unique_key in used_keys:
            unique_key = f"{base_key}_{suffix}"
            suffix += 1
        used_keys.add(unique_key)
        return unique_key

    @staticmethod
    def _taggs_to_storage(taggs) -> str | None:
        if taggs is None or taggs == "":
            return None
        if isinstance(taggs, str):
            tokens = [s for s in taggs.split() if s]
            return " ".join(tokens) if tokens else None
        uniq: list[str] = []
        for tag in taggs:
            normalized = str(tag).strip()
            if normalized and normalized not in uniq:
                uniq.append(normalized)
        return " ".join(uniq) if uniq else None

    @staticmethod
    def _taggs_to_list(taggs) -> list[str]:
        if taggs is None or taggs == "":
            return []
        if isinstance(taggs, str):
            return [s for s in taggs.split() if s]
        return [str(tag).strip() for tag in taggs if str(tag).strip()]

    @staticmethod
    def _files_to_list(files) -> list[str]:
        if files is None or files == "":
            return []
        if isinstance(files, str):
            stripped = files.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return [stripped]
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
            if parsed is None:
                return []
            return [str(parsed).strip()] if str(parsed).strip() else []
        return [str(item).strip() for item in files if str(item).strip()]

    def _serialize_chapters_for_api(self, chapters: list[dict]) -> list[dict]:
        return [self._serialize_chapter_for_api(chapter) for chapter in chapters]

    def _serialize_chapter_for_api(self, chapter: dict) -> dict:
        serialized = dict(chapter)
        serialized["taggs"] = self._taggs_to_list(serialized.get("taggs"))
        serialized["files"] = self._files_to_list(serialized.get("files"))
        serialized["index"] = int(serialized.get("order_id") or 0)
        serialized.pop("order_id", None)
        return serialized


__all__ = ["ArkanaNotes"]
