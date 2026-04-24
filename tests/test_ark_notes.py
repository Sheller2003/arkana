from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mdd_arkana_object.ark_notes import ArkanaNotes
from src.mdd_arkana_object.arkana_object_manager import ArkanaObjectManager


class _DummyUser:
    user_id = "user-1"

    def check_user_group_allowed(self, group_id: int) -> bool:
        return True

    def resolve_db_runtime_access(self, db_id: int) -> dict[str, object]:
        raise AssertionError("resolve_db_runtime_access should not be called for default DB objects")


class ArkanaNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        ArkanaNotes._buffer.clear()
        self.addCleanup(ArkanaNotes._buffer.clear)

    def test_append_update_delete_chapter_roundtrip(self) -> None:
        notes = ArkanaNotes(arkana_id=7, object_key="notes-1", description="Example notes")

        chapter_id = notes.append_chapter(
            key="Introduction",
            content="# Hello",
            taggs=["intro", "docs"],
            files=["a.md", "b.png"],
        )
        self.assertEqual(chapter_id, 1)

        updated = notes.update_chapter(
            "Introduction",
            {
                "content": "## Updated",
                "taggs": ["intro", "updated"],
                "files": ["c.pdf"],
            },
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["content"], "## Updated")
        self.assertEqual(updated["taggs"], ["intro", "updated"])
        self.assertEqual(updated["files"], ["c.pdf"])

        payload = notes.to_json()
        self.assertEqual(payload["arkana_type"], "ark_notes")
        self.assertEqual(len(payload["chapters"]), 1)
        self.assertEqual(payload["chapters"][0]["key"], "Introduction")
        self.assertEqual(payload["chapters"][0]["index"], 1)

        notes.delete_chapter("Introduction")
        self.assertEqual(notes.to_json()["chapters"], [])

    def test_duplicate_chapter_keys_are_normalized(self) -> None:
        notes = ArkanaNotes()
        notes.append_chapter(key="Chapter", content="one")
        notes.append_chapter(key="Chapter", content="two")

        chapters = notes.to_json()["chapters"]
        self.assertEqual(chapters[0]["key"], "Chapter")
        self.assertEqual(chapters[1]["key"], "Chapter_1")

    def test_object_manager_resolves_ark_notes(self) -> None:
        manager = ArkanaObjectManager(_DummyUser())
        manager._ArkanaObjectManager__select_object = MagicMock(return_value={
            "arkana_id": 9,
            "arkana_type": "ark_notes",
            "auth_group": 0,
            "object_key": "notes-key",
            "description": "Notes",
            "modeling_db": 0,
        })
        manager._ArkanaObjectManager__resolve_object_db_connection = MagicMock(return_value=MagicMock())

        obj = manager.get_object(9)

        self.assertIsInstance(obj, ArkanaNotes)
        self.assertEqual(obj.arkana_id, 9)
        self.assertEqual(obj.object_key, "notes-key")

    def test_zero_id_notes_are_saved_only_in_buffer(self) -> None:
        notes = ArkanaNotes(arkana_id=0, object_key="tmp")
        notes.append_chapter(key="Temp", content="buffered")

        notes.save()

        self.assertEqual(notes.arkana_id, 0)
        self.assertIsNotNone(notes.buffer_id)
        reloaded = ArkanaNotes.load_from_buffer(notes.buffer_id or "")
        self.assertEqual(reloaded.to_json()["chapters"][0]["key"], "Temp")

    def test_notes_buffer_ttl_is_24_hours(self) -> None:
        self.assertEqual(ArkanaNotes.BUFFER_TTL_SECONDS, 24 * 60 * 60)

    def test_buffer_directory_is_created_for_temp_notes(self) -> None:
        notes = ArkanaNotes(arkana_id=0)
        notes.append_chapter(key="Temp", content="buffered")
        notes.save()

        path = ArkanaNotes.get_buffer_directory(notes.buffer_id or "")

        self.assertTrue(path.exists())
        self.assertIn(Path(tempfile.gettempdir()), path.parents)

    def test_expired_buffer_is_pruned(self) -> None:
        notes = ArkanaNotes(arkana_id=0)
        notes.append_chapter(key="Temp", content="buffered")
        notes.save()
        buffer_id = notes.buffer_id or ""

        with ArkanaNotes._buffer_lock:
            ArkanaNotes._buffer[buffer_id]["expires_at"] = -1

        with self.assertRaises(KeyError):
            ArkanaNotes.load_from_buffer(buffer_id)

    def test_save_to_db_persists_buffered_notes_and_clears_buffer_id(self) -> None:
        notes = ArkanaNotes(arkana_id=0, object_key="tmp-note", description="draft")
        notes.append_chapter(key="Temp", content="buffered")
        notes.save()
        original_buffer_id = notes.buffer_id

        with patch.object(ArkanaNotes, "_save_persisted", autospec=True) as save_persisted:
            def _assign_id(instance):
                instance.arkana_id = 42
                return instance

            save_persisted.side_effect = _assign_id
            notes.save_to_db()

        self.assertEqual(notes.arkana_id, 42)
        self.assertIsNone(notes.buffer_id)
        self.assertFalse(original_buffer_id in ArkanaNotes._buffer)


if __name__ == "__main__":
    unittest.main()
