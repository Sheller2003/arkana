from src.arkana_mdd_db.config import get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB
import mysql.connector
from mysql.connector import Error as MySQLError
from src.mdd_arkana_object.db_connection import ArkanaObjectDBConnection
from src.mdd_arkana_object.run_action.action_handler_interface import build_action_handler


class Arkana_Object_Interface:
    """
    Base interface for Arkana objects.

    - Constructor stores all common arkana_object fields passed in kwargs.
    - "load" and "check_with_key" are intended to be overridden by subclasses
      to implement object-specific behavior.
    """

    # Default/declared attributes (runtime values are set in __init__)
    arkana_id: int | None = None
    arkana_type: str = "interface"
    auth_group: int | None = None
    object_key: str | None = None
    description: str | None = None
    modeling_db: int = 0
    db_connection: ArkanaObjectDBConnection | None = None
    _runtime_connection = None  # type: ignore[var-annotated]
    _runtime_cursor = None  # type: ignore[var-annotated]

    # Shared main-DB connection/cursor across all interface instances
    _shared_db: ArkanaMainDB | None = None
    _shared_connection = None  # type: ignore[var-annotated]
    _shared_cursor = None  # type: ignore[var-annotated]

    def __init__(self, **kwargs):
        # Persist known fields safely with basic normalization
        arkana_id = kwargs.get("arkana_id")
        self.arkana_id = int(arkana_id) if arkana_id is not None else None

        self.arkana_type = str(kwargs.get("arkana_type", self.arkana_type))

        auth_group = kwargs.get("auth_group")
        self.auth_group = int(auth_group) if auth_group is not None else None

        object_key = kwargs.get("object_key")
        self.object_key = str(object_key) if object_key is not None else None

        description = kwargs.get("description")
        self.description = str(description) if description is not None else None

        modeling_db = kwargs.get("modeling_db", kwargs.get("moddeling_db", 0))
        try:
            self.modeling_db = int(modeling_db) if modeling_db is not None else 0
        except (TypeError, ValueError):
            self.modeling_db = 0

        db_connection = kwargs.get("db_connection")
        self.db_connection = db_connection if isinstance(db_connection, ArkanaObjectDBConnection) else None
        self._runtime_connection = kwargs.get("db_runtime_connection")
        self._runtime_cursor = kwargs.get("db_cursor")

    # ------------- Shared cursor/connection management -------------
    @classmethod
    def _ensure_cursor(cls):
        """
        Ensure a single shared cursor (and its underlying connection) exists for
        all Arkana_Object_Interface instances. Recreates if disconnected.
        """
        try:
            if cls._shared_connection is not None:
                # Check and revive if needed
                try:
                    if hasattr(cls._shared_connection, "is_connected") and cls._shared_connection.is_connected():
                        if cls._shared_cursor is not None:
                            return cls._shared_connection, cls._shared_cursor
                except Exception:
                    pass

            # (Re)create
            config = get_main_db_config()
            cls._shared_db = ArkanaMainDB(config)
            cls._shared_connection = mysql.connector.connect(
                host=config.host,
                port=config.port,
                database=config.database,
                user=config.user,
                password=config.password,
            )
            cls._shared_cursor = cls._shared_connection.cursor()
            return cls._shared_connection, cls._shared_cursor
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize shared DB cursor: {exc}") from exc

    @classmethod
    def _commit(cls) -> None:
        if cls._shared_connection is not None:
            try:
                cls._shared_connection.commit()
            except Exception:
                # Try to revive connection once
                cls._shared_connection = None
                cls._shared_cursor = None
                connection, _ = cls._ensure_cursor()
                connection.commit()

    @classmethod
    def _close_shared(cls) -> None:
        cur = cls._shared_cursor
        con = cls._shared_connection
        cls._shared_cursor = None
        cls._shared_connection = None
        try:
            if cur is not None:
                cur.close()
        finally:
            if con is not None:
                try:
                    con.close()
                except Exception:
                    pass

    def _ensure_model_cursor(self):
        try:
            if self._runtime_connection is not None:
                try:
                    if hasattr(self._runtime_connection, "is_connected") and self._runtime_connection.is_connected():
                        if self._runtime_cursor is not None:
                            return self._runtime_connection, self._runtime_cursor
                except Exception:
                    pass

            if self.db_connection is not None:
                # Try object-specific connection first; on failure, gracefully fall back
                try:
                    self._runtime_connection, self._runtime_cursor = self.db_connection.open_cursor()
                    return self._runtime_connection, self._runtime_cursor
                except Exception:
                    # Fall back to shared/main DB cursor as a resilient default
                    pass

            return self._ensure_cursor()
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize model DB cursor: {exc}") from exc

    def _commit_model(self) -> None:
        if self._runtime_connection is not None:
            self._runtime_connection.commit()
            return
        self._commit()

    def check_with_key(self, key) -> bool:
        """
        Default implementation compares provided key to the stored object_key.
        Subclasses may override to implement custom logic.
        """
        if key is None or self.object_key is None:
            return False
        return str(key) == self.object_key

    def load(self):
        """
        Default no-op loader. Subclasses should override to load
        object-specific values (e.g., from DB) and may return self.
        """
        return self

    def to_json(self) -> dict:
        return {
            "arkana_id": self.arkana_id,
            "arkana_type": self.arkana_type,
            "auth_group": self.auth_group,
            "object_key": self.object_key,
            "description": self.description,
            "modeling_db": self.modeling_db,
        }

    def save(self):
        """
        Default save implementation.

        - Designed to be overridden by subclasses to persist object-specific
          data to their own tables.
        - Ensures the base `arkana_object` entry exists; if `arkana_id` is
          missing or 0, it will insert the base row first to obtain a new id.
        - Always persists current base fields to `arkana_object` (insert/update).
        """
        # If not yet persisted (arkana_id None or 0), insert into arkana_object first
        if self.arkana_id in (None, 0):
            self.save_arkana_object(self)
        else:
            # Even when id exists, keep base fields in sync
            self.save_arkana_object(self)
        return self

    def save_arkana_object(self, arkana_object):
        """
        Persist the base arkana_object entry.

        Accepts either:
        - a dict with keys (arkana_id, arkana_type, auth_group, object_key, description), or
        - an Arkana_Object_Interface (or subclass) instance.

        Returns the `arkana_id` after persistence (possibly newly created).
        """
        # Normalize payload
        if isinstance(arkana_object, dict):
            data = arkana_object
        elif isinstance(arkana_object, Arkana_Object_Interface):
            data = arkana_object.to_json()
        else:
            data = self.to_json()

        arkana_id = data.get("arkana_id", self.arkana_id)
        arkana_type = (data.get("arkana_type") or self.arkana_type or "").strip()
        auth_group = data.get("auth_group", self.auth_group)
        object_key = data.get("object_key", self.object_key)
        description = data.get("description", self.description)
        modeling_db = data.get("modeling_db", self.modeling_db)

        # Use shared main DB cursor
        connection, cursor = self._ensure_cursor()

        # Helper: detect whether arkana_object has column `modeling_db`
        def _has_modeling_db_column() -> bool:
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                     WHERE TABLE_SCHEMA = DATABASE()
                       AND TABLE_NAME = 'arkana_object'
                       AND COLUMN_NAME = 'modeling_db'
                    """
                )
                row = cursor.fetchone()
                return bool(row and int(row[0]) > 0)
            except Exception:
                return False

        has_modeling_col = _has_modeling_db_column()

        # Insert new base object if no valid id
        if arkana_id in (None, 0):
            if has_modeling_col:
                cursor.execute(
                    (
                        "INSERT INTO arkana_object (arkana_type, auth_group, object_key, description, modeling_db) "
                        "VALUES (%s, %s, %s, %s, %s)"
                    ),
                    (
                        str(arkana_type),
                        int(auth_group) if auth_group is not None else None,
                        str(object_key) if object_key is not None else None,
                        str(description) if description is not None else None,
                        int(modeling_db) if modeling_db is not None else 0,
                    ),
                )
            else:
                # Legacy schema without modeling_db column
                cursor.execute(
                    (
                        "INSERT INTO arkana_object (arkana_type, auth_group, object_key, description) "
                        "VALUES (%s, %s, %s, %s)"
                    ),
                    (
                        str(arkana_type),
                        int(auth_group) if auth_group is not None else None,
                        str(object_key) if object_key is not None else None,
                        str(description) if description is not None else None,
                    ),
                )
            new_id = int(cursor.lastrowid)
            self._commit()
            # Update self with the new id
            self.arkana_id = new_id
            return new_id

        # Otherwise, update existing base row
        try:
            if has_modeling_col:
                cursor.execute(
                    (
                        "UPDATE arkana_object "
                        "SET arkana_type = %s, auth_group = %s, object_key = %s, description = %s, modeling_db = %s "
                        "WHERE arkana_id = %s"
                    ),
                    (
                        str(arkana_type),
                        int(auth_group) if auth_group is not None else None,
                        str(object_key) if object_key is not None else None,
                        str(description) if description is not None else None,
                        int(modeling_db) if modeling_db is not None else 0,
                        int(arkana_id),
                    ),
                )
            else:
                cursor.execute(
                    (
                        "UPDATE arkana_object "
                        "SET arkana_type = %s, auth_group = %s, object_key = %s, description = %s "
                        "WHERE arkana_id = %s"
                    ),
                    (
                        str(arkana_type),
                        int(auth_group) if auth_group is not None else None,
                        str(object_key) if object_key is not None else None,
                        str(description) if description is not None else None,
                        int(arkana_id),
                    ),
                )
            self._commit()
        except MySQLError:
            raise
        # Keep self in sync
        self.arkana_id = int(arkana_id)
        self.arkana_type = arkana_type or self.arkana_type
        self.auth_group = int(auth_group) if auth_group is not None else None
        self.object_key = str(object_key) if object_key is not None else None
        self.description = str(description) if description is not None else None
        self.modeling_db = int(modeling_db) if modeling_db is not None else 0
        return self.arkana_id
    
    def get_field(self, arkana_id: int) -> dict:
        # Use main DB from .env to fetch a single arkana_object by id
        _, cursor = self._ensure_cursor()

        row = None
        queries = [
            (
                "SELECT arkana_id, arkana_type, auth_group, object_key, description, modeling_db "
                "FROM arkana_object WHERE arkana_id = %s LIMIT 1"
            ),
            (
                "SELECT arkana_id, arkana_type, auth_group, object_key, description "
                "FROM arkana_object WHERE arkana_id = %s LIMIT 1"
            ),
        ]
        for query in queries:
            try:
                cursor.execute(query, (arkana_id,))
                row = cursor.fetchone()
                break
            except Exception:
                continue
        if row is None:
            return {}
        return {
            "arkana_id": int(row[0]) if row[0] is not None else None,
            "arkana_type": str(row[1]) if row[1] is not None else None,
            "auth_group": int(row[2]) if row[2] is not None else None,
            "object_key": str(row[3]) if row[3] is not None else None,
            "description": str(row[4]) if row[4] is not None else None,
            "modeling_db": int(row[5]) if len(row) > 5 and row[5] is not None else 0,
        }
    
    def get_field_by_key(self, arkana_key: str) -> dict:
        # Use main DB from .env to fetch a single arkana_object by object_key
        _, cursor = self._ensure_cursor()

        row = None
        queries = [
            (
                "SELECT arkana_id, arkana_type, auth_group, object_key, description, modeling_db "
                "FROM arkana_object WHERE object_key = %s LIMIT 1"
            ),
            (
                "SELECT arkana_id, arkana_type, auth_group, object_key, description "
                "FROM arkana_object WHERE object_key = %s LIMIT 1"
            ),
        ]
        for query in queries:
            try:
                cursor.execute(query, (arkana_key,))
                row = cursor.fetchone()
                break
            except Exception:
                continue
        if row is None:
            return {}
        return {
            "arkana_id": int(row[0]) if row[0] is not None else None,
            "arkana_type": str(row[1]) if row[1] is not None else None,
            "auth_group": int(row[2]) if row[2] is not None else None,
            "object_key": str(row[3]) if row[3] is not None else None,
            "description": str(row[4]) if row[4] is not None else None,
            "modeling_db": int(row[5]) if len(row) > 5 and row[5] is not None else 0,
        }

    def run_cell_action(self, user_object, runned_field_id: int | str) -> list[dict]:
        if not hasattr(self, "cells"):
            raise RuntimeError("Object has no cells")
        if getattr(self, "cells", None) is None and hasattr(self, "load"):
            self.load()

        cells = getattr(self, "cells", None)
        if not isinstance(cells, list):
            raise RuntimeError("Object has no cells")

        parent_index = self._find_cell_index(runned_field_id)
        if parent_index is None:
            raise ValueError(f"Cell not found: {runned_field_id}")

        parent_cell = cells[parent_index]
        handler = build_action_handler(
            assigned_to_arkana_id=self.arkana_id,
            field_id=parent_cell.get("cell_id", runned_field_id),
            field_value=str(parent_cell.get("content") or ""),
            running_id=parent_cell.get("cell_id", runned_field_id),
            user_object=user_object,
            cell_type=str(parent_cell.get("cell_type") or ""),
        )
        result_cells = handler.get_result_cells()
        return self._append_result_cells_below_field(parent_index, parent_cell, result_cells)

    def _find_cell_index(self, identifier: int | str) -> int | None:
        cells = getattr(self, "cells", None)
        if not isinstance(cells, list):
            return None

        try:
            int_identifier = int(identifier)
        except Exception:
            int_identifier = None

        if int_identifier is not None:
            for index, cell in enumerate(cells):
                if cell.get("cell_id") == int_identifier:
                    return index
            if 1 <= int_identifier <= len(cells):
                return int_identifier - 1

        str_identifier = str(identifier)
        for index, cell in enumerate(cells):
            if str(cell.get("cell_key")) == str_identifier:
                return index
        return None

    def _append_result_cells_below_field(self, parent_index: int, parent_cell: dict, result_cells: list[dict]) -> list[dict]:
        cells = getattr(self, "cells", None)
        if not isinstance(cells, list):
            raise RuntimeError("Object has no cells")

        parent_cell_id = int(parent_cell.get("cell_id") or -1)
        parent_key = parent_cell.get("cell_key")
        parent_prev = parent_cell.get("prev_id", parent_cell.get("prev", 0))

        inserted: list[dict] = []
        insert_at = parent_index + 1
        for result_cell in result_cells:
            new_cell = dict(result_cell)
            new_cell["cell_id"] = -1
            new_cell["cell_key"] = parent_key
            new_cell["prev"] = parent_prev
            new_cell["prev_id"] = parent_prev
            new_cell["depend_by"] = parent_cell_id
            cells.insert(insert_at, new_cell)
            inserted.append(new_cell)
            insert_at += 1

        for order_id, cell in enumerate(cells, start=1):
            cell["order_id"] = order_id
        return inserted
