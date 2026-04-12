from src.mdd_arkana_object.ark_obj_interface import Arkana_Object_Interface
from src.mdd_arkana_object.cell_types import CellType
from src.mdd_arkana_object.run_action.action_handler_interface import build_action_handler
from src.arkana_mdd_db.config import get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB


class ArkanaReport(Arkana_Object_Interface):
    """
    ArkanaReport represents a report object in Arkana.

    Loads its specific fields from the `arkana_dashboard_header` table.
    """

    arkana_type: str = "report"
    arkana_group: int | None = None
    # Deprecated: JSON content is no longer persisted in DB. Kept for in-memory use only.
    content_json: dict | list | None = None
    # In-memory representation of dashboard cells; persisted in save()
    # Each item: {"cell_id"?: int, "order_id": int, "cell_key": str, "cell_type": str, "taggs": str | None, "content": Any}
    cells: list[dict] | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Optional field if already provided by caller
        if "arkana_group" in kwargs and kwargs.get("arkana_group") is not None:
            try:
                self.arkana_group = int(kwargs.get("arkana_group"))
            except (TypeError, ValueError):
                self.arkana_group = None
        # Allow passing preloaded JSON content (in-memory only; not persisted)
        if "content_json" in kwargs and kwargs.get("content_json") is not None:
            self.content_json = kwargs.get("content_json")

    def _resolve_existing_table(self, *table_names: str) -> str | None:
        for table_name in table_names:
            if self._has_table(table_name):
                return table_name
        return None

    def _header_table_name(self) -> str:
        table_name = self._resolve_existing_table("arkana_report_header")
        if table_name is None:
            raise RuntimeError("Required table 'arkana_report_header' not found")
        return table_name

    def _cells_table_name(self) -> str:
        table_name = self._resolve_existing_table("arkana_report_cells")
        if table_name is None:
            raise RuntimeError("Required table 'arkana_report_cells' not found")
        return table_name

    def load(self):
        """
        Load ArkBoard specific values from DB by `arkana_id` using a single SELECT.
        - Loads `arkana_group` from `arkana_dashboard_header` and all dashboard cells
          from `arkana_dashboard_cells` via LEFT JOIN in one query.
        """
        if self.arkana_id is None:
            return self

        try:
            _, cursor = self._ensure_model_cursor()
            header_table = self._header_table_name()
            cells_table = self._cells_table_name()

            uses_prev = self._has_column(cells_table, "prev_id")
            has_content = self._has_column(cells_table, "content")
            content_column = (
                "content"
                if has_content
                else ("cell_value" if self._has_column(cells_table, "cell_value") else None)
            )
            order_column = (
                "order_id"
                if self._has_column(cells_table, "order_id")
                else ("run_order" if self._has_column(cells_table, "run_order") else None)
            )
            has_depend_by = self._has_column(cells_table, "depend_by")
            import json

            select_parts = ["h.arkana_group", "c.cell_id"]
            if order_column is not None:
                select_parts.append(f"c.{order_column}")
            if uses_prev:
                select_parts.append("c.prev_id")
            select_parts.extend(["c.cell_key", "c.cell_type", "c.taggs"])
            if content_column is not None:
                select_parts.append(f"c.{content_column}")
            if has_depend_by:
                select_parts.append("c.depend_by")

            query = (
                f"SELECT {', '.join(select_parts)} "
                f"FROM {header_table} h "
                f"LEFT JOIN {cells_table} c ON c.arkana_object_id = h.arkana_id "
                "WHERE h.arkana_id = %s "
            )
            if order_column is not None:
                if has_depend_by:
                    query += (
                        f"ORDER BY c.{order_column}, "
                        "CASE WHEN c.depend_by IS NULL THEN 0 ELSE 1 END, "
                        "c.depend_by, c.cell_id"
                    )
                else:
                    query += f"ORDER BY c.{order_column}, c.cell_id"

            cursor.execute(query, (int(self.arkana_id),))
            rows = cursor.fetchall() or []
            self.cells = []
            header_group_set = False
            for r in rows:
                if not header_group_set:
                    self.arkana_group = int(r[0]) if r and r[0] is not None else None
                    header_group_set = True
            if not rows:
                cursor.execute(
                    f"SELECT arkana_group FROM {header_table} WHERE arkana_id = %s LIMIT 1",
                    (int(self.arkana_id),),
                )
                row = cursor.fetchone()
                if row is not None:
                    self.arkana_group = int(row[0]) if row[0] is not None else None
                self.cells = []
            else:
                for r in rows:
                    if r[1] is None:
                        continue
                    index = 2
                    order_id = None
                    if order_column is not None:
                        order_id = int(r[index]) if r[index] is not None else None
                        index += 1
                    prev_id = None
                    if uses_prev:
                        prev_id = int(r[index]) if r[index] is not None else None
                        index += 1
                    cell_key = str(r[index]) if r[index] is not None else None
                    index += 1
                    cell_type = str(r[index]) if r[index] is not None else None
                    index += 1
                    taggs = self._taggs_to_storage(r[index])
                    index += 1
                    content_value = None
                    if content_column is not None:
                        raw = r[index]
                        index += 1
                        try:
                            if raw is None:
                                content_value = None
                            elif content_column == "content" and isinstance(raw, (bytes, bytearray)):
                                content_value = json.loads(raw.decode("utf-8"))
                            elif content_column == "content" and isinstance(raw, str):
                                content_value = json.loads(raw)
                            else:
                                content_value = raw
                        except Exception:
                            content_value = raw
                    depend_by = None
                    if has_depend_by and len(r) > index and r[index] is not None:
                        depend_by = int(r[index])

                    self.cells.append(
                        {
                            "cell_id": int(r[1]) if r[1] is not None else None,
                            "order_id": order_id,
                            "prev_id": prev_id,
                            "prev": prev_id,
                            "cell_key": cell_key,
                            "cell_type": cell_type,
                            "taggs": taggs,
                            "content": content_value,
                            "depend_by": depend_by,
                        }
                    )

            return self
        finally:
            self._close_model()

    def to_json(self) -> dict:
        # Start with base fields from interface
        data = super().to_json()
        # Ensure known board-specific fields are present
        data["arkana_group"] = self.arkana_group
        if self.cells is not None:
            data["cells"] = self._serialize_cells_for_api(self.cells, include_index=True)
        # Include any other public instance attributes not already captured
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            if key == "db_connection":
                continue
            if key == "user_object":
                continue
            if key == "content_json":
                continue
            if key == "cells":
                continue
            if key in data:
                continue
            if callable(value):
                continue
            data[key] = value
        return data

    def save(self):
        """
        Persist ArkBoard to the database.

        Behavior:
        - Calls super().save() to ensure base `arkana_object` row exists and is up-to-date.
        - Upserts record in `arkana_dashboard_header` with fields:
            - arkana_id (PK, FK to arkana_object)
            - arkana_group (nullable)
        - Replaces dashboard cells in `arkana_dashboard_cells` for this object id using the
          in-memory `self.cells` list.
        - Returns self for chaining.
        """
        # Ensure base object exists and fields are synced
        super().save()

        if self.arkana_id in (None, 0):
            # Could not obtain a valid arkana_id; nothing more to do safely
            return self

        try:
            # Use shared cursor/connection
            _, cursor = self._ensure_model_cursor()
            header_table = self._header_table_name()
            cells_table = self._cells_table_name()

            # Check if a report header row already exists
            cursor.execute(
                f"SELECT 1 FROM {header_table} WHERE arkana_id = %s LIMIT 1",
                (int(self.arkana_id),),
            )
            exists = cursor.fetchone()

            group_val = int(self.arkana_group) if self.arkana_group is not None else None

            if exists is None:
                cursor.execute(
                    f"INSERT INTO {header_table} (arkana_id, arkana_group) VALUES (%s, %s)",
                    (int(self.arkana_id), group_val),
                )
            else:
                cursor.execute(
                    f"UPDATE {header_table} SET arkana_group = %s WHERE arkana_id = %s",
                    (group_val, int(self.arkana_id)),
                )

            if self.cells is None:
                self.cells = []

            cursor.execute(
                f"DELETE FROM {cells_table} WHERE arkana_object_id = %s",
                (int(self.arkana_id),),
            )

            uses_prev = self._has_column(cells_table, "prev_id")
            has_content = self._has_column(cells_table, "content")
            content_column = "content" if has_content else ("cell_value" if self._has_column(cells_table, "cell_value") else None)
            order_column = "order_id" if self._has_column(cells_table, "order_id") else ("run_order" if self._has_column(cells_table, "run_order") else None)
            has_depend_by = self._has_column(cells_table, "depend_by")

            order_counter = 1
            prev_cell_id: int | None = None
            import json
            used_cell_keys: set[str] = set()
            for cell in self.cells:
                cell_type = cell.get("cell_type") or "text"
                tag_str = self._taggs_to_storage(cell.get("taggs"))
                raw_cell_id = cell.get("cell_id")
                try:
                    normalized_cell_id = int(raw_cell_id) if raw_cell_id is not None else 0
                except (TypeError, ValueError):
                    normalized_cell_id = 0
                cell_id_for_board = normalized_cell_id if normalized_cell_id > 0 else order_counter
                cell_key = self._ensure_unique_cell_key(cell.get("cell_key"), cell_id_for_board, used_cell_keys)
                prev_id_value = cell.get("prev_id", cell.get("prev"))
                if prev_id_value in (None, ""):
                    prev_id_value = prev_cell_id if prev_cell_id is not None else 0
                depend_by_value = cell.get("depend_by")
                content_value = cell.get("content")
                content_serialized = None
                if content_column is not None:
                    try:
                        if content_column == "content":
                            content_serialized = json.dumps(content_value) if content_value is not None else None
                        else:
                            content_serialized = str(content_value) if content_value is not None else None
                    except Exception:
                        content_serialized = str(content_value) if content_value is not None else None

                columns = ["cell_id", "arkana_object_id"]
                values = [int(cell_id_for_board), int(self.arkana_id)]
                if order_column is not None:
                    columns.append(order_column)
                    values.append(int(cell.get("order_id") or order_counter))
                if uses_prev:
                    columns.append("prev_id")
                    values.append(int(prev_id_value))
                columns.extend(["cell_key", "cell_type", "taggs"])
                values.extend([str(cell_key), str(cell_type), tag_str])
                if content_column is not None:
                    columns.append(content_column)
                    values.append(content_serialized)
                if has_depend_by:
                    columns.append("depend_by")
                    values.append(int(depend_by_value) if depend_by_value not in (None, "") else None)

                placeholders = ", ".join(["%s"] * len(columns))
                cursor.execute(
                    f"INSERT INTO {cells_table} ({', '.join(columns)}) VALUES ({placeholders})",
                    tuple(values),
                )

                cell["cell_id"] = cell_id_for_board
                cell["order_id"] = order_counter
                cell["cell_key"] = cell_key
                cell["prev_id"] = int(prev_id_value)
                cell["prev"] = int(prev_id_value)
                prev_cell_id = cell_id_for_board
                order_counter += 1

            self._commit_model()
        except Exception:
            self._rollback_model()
            raise
        finally:
            self._close_model()

        return self

    # --------- Dashboard cells management ---------
    def reset_cells(self):
        """
        Clear in-memory dashboard cells for this board.
        Persistence will occur on the next `save()` call.
        Returns self for chaining.
        """
        if self.cells is None:
            self.cells = []
        else:
            self.cells.clear()
        return self

    def append_cell(self, cell_type: str, payload, taggs: list[str] | None = None) -> int | None:
        """
        Append a new cell as the last item for this board (in-memory only).
        Persistence will occur on the next `save()` call. Returns None (no DB insert here).
        """
        # Normalize taggs into space-separated string
        tag_str = self._taggs_to_storage(taggs)

        if self.cells is None:
            self.cells = []
        order_id = self._next_top_level_order_id()
        next_cell_id = self._next_free_cell_id()
        self.cells.append(
            {
                "cell_id": next_cell_id,
                "order_id": order_id,
                "prev_id": self.cells[-1].get("cell_id") if self.cells else 0,
                "prev": self.cells[-1].get("cell_id") if self.cells else 0,
                "depend_by": None,
                "cell_key": f"cell_{next_cell_id}",
                "cell_type": str(cell_type),
                "taggs": tag_str,
                "content": payload,
            }
        )
        return None

    def run_cell(self, cell_id, save_result: bool) -> list[dict]:
        if self.user_object is None:
            raise RuntimeError("run_cell requires an attached user_object")
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        parent_index = self._find_runnable_cell_index(cell_id)
        if parent_index is None:
            raise ValueError(f"Cell not found: {cell_id}")

        parent_cell = self.cells[parent_index]
        parent_identifier = parent_cell.get("cell_id") if parent_cell.get("cell_id") not in (None, 0) else parent_cell.get("cell_key")
        handler = build_action_handler(
            assigned_to_arkana_id=self.arkana_id,
            field_id=parent_identifier,
            field_value=str(parent_cell.get("content") or ""),
            running_id=parent_identifier,
            user_object=self.user_object,
            cell_type=str(parent_cell.get("cell_type") or ""),
        )
        result_cells = handler.get_result_cells()
        if not save_result:
            transient_cells = self._build_transient_result_cells(parent_cell, result_cells)
            return [self._serialize_cell(cell) for cell in transient_cells]

        updated_cells = self._replace_result_cells(parent_index, parent_cell, result_cells)
        self.save()
        return [self._serialize_cell(cell) for cell in updated_cells]

    def run_all_cells(self, save_result: bool) -> list[dict]:
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        runnable_identifiers: list[int | str] = []
        runnable_types = {CellType.PY_CODE.value, CellType.R_CODE.value}
        for cell in self.cells:
            if str(cell.get("cell_type") or "") not in runnable_types:
                continue
            runnable_identifiers.append(cell.get("cell_id") if cell.get("cell_id") not in (None, 0) else cell.get("cell_key"))

        results: list[dict] = []
        for identifier in runnable_identifiers:
            results.append({"cell": identifier, "results": self.run_cell(identifier, save_result)})
        return results
    def _has_table(self, table_name: str) -> bool:
        try:
            _, cursor = self._ensure_model_cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                """,
                (table_name,),
            )
            row = cursor.fetchone()
            return (row is not None) and int(row[0]) > 0
        except Exception:
            return False

    def _has_column(self, table_name: str, column_name: str) -> bool:
        try:
            _, cursor = self._ensure_model_cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                """,
                (table_name, column_name),
            )
            row = cursor.fetchone()
            return (row is not None) and int(row[0]) > 0
        except Exception:
            return False

    def add_cell(self, index: int, cell: dict | None = None, **kwargs):
        """
        Add a dashboard cell at the given position (1-based order).

        Requirements from issue:
        - Caller may provide all necessary fields EXCEPT `order_id` and `cell_id` (these are controlled by the system).
        - The parameter `index` must remain and defines the insertion position (1-based).

        Accepted/normalized fields (from `cell` dict and/or `**kwargs`):
        - cell_key: str (default: "cell_{index}")
        - cell_type: str (default: "text")
        - taggs: list[str] | str | None (stored as space-separated string)
        - any other keys will be stored in-memory on the cell dict but are not persisted to DB by `save()`.

        Persistence occurs on the next `save()` call.
        Returns self for chaining.
        """
        # In-memory ordering only; persist on save()
        if self.cells is None:
            self.cells = []
        top_level_cells = [existing for existing in self.cells if existing.get("depend_by") in (None, 0, "")]
        max_order = len(top_level_cells)

        # Normalize target index (1-based)
        try:
            target = int(index)
        except Exception:
            target = max_order + 1
        if target <= 0:
            target = 1
        if target > max_order + 1:
            target = max_order + 1  # append

        # Merge user payload from dict and kwargs
        payload: dict = {}
        if isinstance(cell, dict):
            payload.update(cell)
        if kwargs:
            payload.update(kwargs)

        # Remove forbidden keys
        payload.pop("order_id", None)
        payload.pop("cell_id", None)
        payload.pop("field_id", None)  # backward compatibility with wording

        # Normalize taggs to space-separated string
        if "taggs" in payload:
            payload["taggs"] = self._taggs_to_storage(payload.get("taggs"))

        # Defaults
        next_cell_id = self._next_free_cell_id()
        cell_key = str(payload.get("cell_key") or f"cell_{next_cell_id}")
        cell_type = str(payload.get("cell_type") or "text")

        # Build new cell dict
        new_cell: dict = {
            "cell_id": next_cell_id,
            "order_id": target,
            "prev_id": 0,
            "prev": 0,
            "depend_by": None,
            "cell_key": cell_key,
            "cell_type": cell_type,
            "taggs": payload.get("taggs"),
        }

        # Attach any additional, non-persisted attributes (kept in-memory)
        for k, v in payload.items():
            if k in {"cell_key", "cell_type", "taggs"}:
                continue
            new_cell[k] = v

        insert_position = self._top_level_insert_position(target)
        self.cells.insert(insert_position, new_cell)
        self._reindex_cells()
        return self

    # --------- Cell tag management (no content persistence) ---------
    def update_cell(self, id: int | str, new_value: dict | None = None, **kwargs):
        """
        Update an existing cell's properties in-memory. Writes occur on `save()`.

        - `id` can be the `cell_id` (preferred) or the 1-based index position when
          `cell_id` is not yet assigned.
        - Caller may pass all fields except `order_id` and `cell_id`.
        - Recognized persisted fields: `cell_key`, `cell_type`, `taggs`.
          Other keys are stored in-memory on the cell dict and ignored by DB `save()`.
        """
        # Prepare payload
        payload: dict = {}
        if isinstance(new_value, dict):
            payload.update(new_value)
        if kwargs:
            payload.update(kwargs)

        # Remove forbidden keys
        payload.pop("order_id", None)
        payload.pop("cell_id", None)
        payload.pop("field_id", None)

        # Ensure cells are loaded
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        target_cell = self._resolve_cell_by_identifier(id)
        if target_cell is None:
            return self

        # Normalize taggs
        if "taggs" in payload:
            payload["taggs"] = self._taggs_to_storage(payload.get("taggs"))

        # Apply updates (persisted keys + any extras)
        for k, v in payload.items():
            target_cell[k] = v

        self._normalize_cell_keys()

        return self

    def get_cell(self, identifier: int | str) -> dict | None:
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        target = self._resolve_cell_by_identifier(identifier)
        if target is None:
            return None
        return self._serialize_cell(target, include_children=True)

    def get_cell_by_id(self, cell_id: int) -> dict | None:
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        for cell in self.cells:
            if cell.get("cell_id") == int(cell_id):
                return self._serialize_cell(cell, include_children=True)
        return None

    def delete_cell(self, identifier: int | str):
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        target = self._resolve_cell_by_identifier(identifier)
        if target is None:
            return self

        self.cells.remove(target)
        self._reindex_cells()
        return self

    def add_cell_tag(self, id: int, tag: str):
        """
        Add a tag to the cell's `taggs` list (space-separated storage in SQL; in-memory list semantics).

        - Managed in-memory; persisted on next save().

        Returns self for chaining.
        """
        if tag is None:
            return self
        tag = str(tag).strip()
        if not tag:
            return self

        # In-memory tag management; persist on save()
        if self.cells is None:
            self.cells = []
        # find by cell_id or by 1-based index fallback
        target = None
        for cell in self.cells:
            if cell.get("cell_id") == int(id):
                target = cell
                break
        if target is None and 1 <= int(id) <= len(self.cells):
            target = self.cells[int(id) - 1]
        if target is None:
            return self
        existing = str(target.get("taggs") or "")
        tokens = [t for t in existing.split(" ") if t]
        if tag not in tokens:
            tokens.append(tag)
        target["taggs"] = " ".join(tokens) if tokens else None
        return self

    def delete_cell_tag(self, id: int, cell_tag: str):
        """
        Remove a tag from the cell's tags. `cell_tag` matches exact token.
        """
        if cell_tag is None:
            return self
        cell_tag = str(cell_tag).strip()
        if not cell_tag:
            return self

        # In-memory tag removal; persist on save()
        if self.cells is None:
            self.cells = []
        target = None
        for cell in self.cells:
            if cell.get("cell_id") == int(id):
                target = cell
                break
        if target is None and 1 <= int(id) <= len(self.cells):
            target = self.cells[int(id) - 1]
        if target is None:
            return self
        existing = str(target.get("taggs") or "")
        tokens = [t for t in existing.split(" ") if t and t != cell_tag]
        target["taggs"] = " ".join(tokens) if tokens else None
        return self

    def get_cell_taggs(self) -> dict[int, list[str]]:
        """
        Return a mapping of cell_id -> list of tags for all cells on this board.
        """
        result: dict[int, list[str]] = {}
        if self.arkana_id in (None, 0):
            return result

        # Use in-memory cells if present; otherwise load() first
        if self.cells is None:
            self.load()
        for cell in self.cells or []:
            fid = int(cell.get("cell_id") or cell.get("order_id") or 0)
            tg = str(cell.get("taggs") or "")
            tokens = [t for t in tg.split(" ") if t]
            result[fid] = tokens
        return result

    def _resolve_cell_by_identifier(self, identifier: int | str) -> dict | None:
        if self.cells is None:
            self.cells = []

        try:
            int_identifier = int(identifier)
        except Exception:
            int_identifier = None

        if int_identifier is not None:
            root_cells = [cell for cell in self.cells if cell.get("depend_by") in (None, 0, "")]
            if 1 <= int_identifier <= len(root_cells):
                return root_cells[int_identifier - 1]

        str_identifier = str(identifier)
        for cell in self.cells:
            if str(cell.get("cell_key")) == str_identifier:
                return cell
        return None

    def _find_runnable_cell_index(self, identifier: int | str) -> int | None:
        if self.cells is None:
            self.cells = []

        try:
            int_identifier = int(identifier)
        except Exception:
            int_identifier = None

        if int_identifier is not None:
            root_indices = [
                index for index, cell in enumerate(self.cells)
                if cell.get("depend_by") in (None, 0, "")
            ]
            if 1 <= int_identifier <= len(root_indices):
                return root_indices[int_identifier - 1]

        str_identifier = str(identifier)
        for index, cell in enumerate(self.cells):
            if cell.get("depend_by") not in (None, 0, ""):
                continue
            if str(cell.get("cell_key")) == str_identifier:
                return index
        return None

    def _prepare_result_cell(self, parent_cell: dict, result_cell: dict) -> dict:
        prepared = dict(result_cell)
        parent_cell_id = int(parent_cell.get("cell_id") or 0)
        parent_prev = parent_cell.get("prev_id", parent_cell.get("prev", 0))
        parent_order_id = int(parent_cell.get("order_id") or 0)
        prepared["cell_id"] = None
        prepared["cell_key"] = parent_cell.get("cell_key")
        prepared["order_id"] = parent_order_id
        prepared["prev_id"] = parent_prev
        prepared["prev"] = parent_prev
        prepared["depend_by"] = parent_cell_id
        return prepared

    def _build_transient_result_cells(self, parent_cell: dict, result_cells: list[dict]) -> list[dict]:
        next_cell_id = self._next_free_cell_id()
        prepared_cells: list[dict] = []
        for offset, result_cell in enumerate(result_cells):
            prepared = self._prepare_result_cell(parent_cell, result_cell)
            prepared["cell_id"] = next_cell_id + offset
            prepared_cells.append(prepared)
        return prepared_cells

    def _replace_result_cells(self, parent_index: int, parent_cell: dict, result_cells: list[dict]) -> list[dict]:
        if self.cells is None:
            self.cells = []

        parent_cell_id = int(parent_cell.get("cell_id") or 0)
        existing_file_cells: list[dict] = []
        remaining_cells: list[dict] = []
        for index, cell in enumerate(self.cells):
            if index == parent_index:
                remaining_cells.append(cell)
                continue
            if cell.get("depend_by") != parent_cell_id:
                remaining_cells.append(cell)
                continue
            cell_type = str(cell.get("cell_type") or "")
            if cell_type.endswith("_result") or cell_type == CellType.FILE.value:
                if cell_type == CellType.FILE.value:
                    existing_file_cells.append(cell)
                continue

        new_result_cells = self._build_transient_result_cells(parent_cell, result_cells)
        existing_file_contents = {str(cell.get("content")) for cell in existing_file_cells}
        merged_result_cells: list[dict] = []
        for cell in new_result_cells:
            if str(cell.get("cell_type") or "") == CellType.FILE.value and str(cell.get("content")) in existing_file_contents:
                continue
            merged_result_cells.append(cell)

        insert_at = parent_index + 1
        for offset, cell in enumerate(merged_result_cells + existing_file_cells):
            remaining_cells.insert(insert_at + offset, cell)

        self.cells = remaining_cells
        self._reindex_cells()
        self._normalize_cell_keys()
        return [cell for cell in self.cells if cell.get("depend_by") == parent_cell_id]

    def _next_free_cell_id(self) -> int:
        if self.cells is None:
            return 1
        current_max = 0
        for cell in self.cells:
            try:
                current_max = max(current_max, int(cell.get("cell_id") or 0))
            except (TypeError, ValueError):
                continue
        return current_max + 1

    def _next_top_level_order_id(self) -> int:
        if self.cells is None:
            return 1
        root_cells = [cell for cell in self.cells if cell.get("depend_by") in (None, 0, "")]
        return len(root_cells) + 1

    def _top_level_insert_position(self, target_index: int) -> int:
        if self.cells is None:
            return 0
        root_count = 0
        for index, cell in enumerate(self.cells):
            if cell.get("depend_by") not in (None, 0, ""):
                continue
            root_count += 1
            if root_count == target_index:
                return index
        return len(self.cells)

    def _reindex_cells(self) -> None:
        if self.cells is None:
            return
        current_index = 0
        current_parent_id = None
        order_by_parent: dict[int, int] = {}
        for cell in self.cells:
            depend_by = cell.get("depend_by")
            if depend_by in (None, 0, ""):
                current_index += 1
                cell["order_id"] = current_index
                current_parent_id = cell.get("cell_id")
                if current_parent_id not in (None, 0, ""):
                    order_by_parent[int(current_parent_id)] = current_index
            else:
                parent_id = int(depend_by)
                cell["order_id"] = order_by_parent.get(parent_id, current_index)

    def _normalize_cell_keys(self) -> None:
        if self.cells is None:
            return
        used_cell_keys: set[str] = set()
        for cell in self.cells:
            raw_cell_id = cell.get("cell_id")
            try:
                cell_id = int(raw_cell_id) if raw_cell_id is not None else 0
            except (TypeError, ValueError):
                cell_id = 0
            if cell_id <= 0:
                cell_id = self._next_free_cell_id()
                cell["cell_id"] = cell_id
            cell["cell_key"] = self._ensure_unique_cell_key(cell.get("cell_key"), cell_id, used_cell_keys)

    def _ensure_unique_cell_key(self, proposed_key, cell_id: int, used_cell_keys: set[str]) -> str:
        base_key = str(proposed_key).strip() if proposed_key is not None else ""
        if not base_key:
            base_key = f"cell_{cell_id}"
        unique_key = base_key
        suffix = 1
        while unique_key in used_cell_keys:
            unique_key = f"{base_key}_{suffix}"
            suffix += 1
        used_cell_keys.add(unique_key)
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

    def _serialize_cells_for_api(self, cells: list[dict], include_index: bool) -> list[dict]:
        serialized_by_id: dict[int, dict] = {}
        root_cells: list[dict] = []

        ordered_cells = sorted(
            cells,
            key=lambda cell: (
                int(cell.get("order_id") or 0),
                1 if cell.get("depend_by") not in (None, 0, "") else 0,
                int(cell.get("cell_id") or 0),
            ),
        )

        for cell in ordered_cells:
            is_child = cell.get("depend_by") not in (None, 0, "")
            serialized = self._serialize_cell(
                cell,
                include_children=False,
                include_index=(include_index and not is_child),
            )
            cell_id = int(cell.get("cell_id") or 0)
            if cell_id > 0:
                serialized_by_id[cell_id] = serialized

            depend_by = cell.get("depend_by")
            if depend_by in (None, 0, ""):
                root_cells.append(serialized)
                continue

            parent = serialized_by_id.get(int(depend_by))
            if parent is None:
                root_cells.append(serialized)
                continue
            parent.setdefault("cells", []).append(serialized)

        return root_cells

    def _serialize_cell(self, cell: dict, include_children: bool = False, include_index: bool = True) -> dict:
        serialized = dict(cell)
        if include_index:
            serialized["index"] = int(serialized.get("order_id") or 0)
        serialized["taggs"] = self._taggs_to_list(serialized.get("taggs"))
        serialized.pop("order_id", None)
        serialized.pop("prev", None)
        serialized.pop("prev_id", None)
        serialized.pop("depend_by", None)
        if include_children and self.cells is not None and cell.get("cell_id") not in (None, 0):
            parent_id = int(cell.get("cell_id"))
            child_cells = [
                child for child in self.cells
                if child.get("depend_by") == parent_id
            ]
            serialized["cells"] = self._serialize_cells_for_api(child_cells, include_index=False)
        else:
            serialized["cells"] = []
        if not include_index:
            serialized.pop("index", None)
        return serialized
