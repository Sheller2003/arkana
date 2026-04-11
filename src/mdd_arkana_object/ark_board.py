from src.mdd_arkana_object.ark_obj_interface import Arkana_Object_Interface
from src.arkana_mdd_db.config import get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB


class ArkBoard(Arkana_Object_Interface):
    """
    ArkBoard represents a dashboard/board object in Arkana.

    Loads its specific fields from the `arkana_dashboard_header` table.
    """

    arkana_type: str = "board"
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

    def load(self):
        """
        Load ArkBoard specific values from DB by `arkana_id` using a single SELECT.
        - Loads `arkana_group` from `arkana_dashboard_header` and all dashboard cells
          from `arkana_dashboard_cells` via LEFT JOIN in one query.
        """
        if self.arkana_id is None:
            return self

        # Use shared cursor from interface
        _, cursor = self._ensure_model_cursor()

        # Ensure required tables exist
        if not self._has_table("arkana_dashboard_header"):
            raise RuntimeError("Required table 'arkana_dashboard_header' not found")
        if not self._has_table("arkana_dashboard_cells"):
            raise RuntimeError("Required table 'arkana_dashboard_cells' not found")

        # Detect legacy/new column variants on the cells table.
        uses_prev = self._has_column("arkana_dashboard_cells", "prev_id")
        has_content = self._has_column("arkana_dashboard_cells", "content")
        content_column = "content" if has_content else ("cell_value" if self._has_column("arkana_dashboard_cells", "cell_value") else None)
        order_column = "order_id" if self._has_column("arkana_dashboard_cells", "order_id") else ("run_order" if self._has_column("arkana_dashboard_cells", "run_order") else None)

        has_depend_by = self._has_column("arkana_dashboard_cells", "depend_by")

        if uses_prev and order_column is None:
            # Load header and all cells with prev_id (no ORDER BY; we'll reconstruct by traversal)
            if content_column is not None:
                query = (
                    f"SELECT h.arkana_group, c.cell_id, c.prev_id, c.cell_key, c.cell_type, c.taggs, c.{content_column}"
                    + (", c.depend_by " if has_depend_by else " ")
                    + "FROM arkana_dashboard_header h "
                    + "LEFT JOIN arkana_dashboard_cells c ON c.arkana_object_id = h.arkana_id "
                    + "WHERE h.arkana_id = %s"
                )
                cursor.execute(
                    query,
                    (int(self.arkana_id),),
                )
            else:
                query = (
                    "SELECT h.arkana_group, c.cell_id, c.prev_id, c.cell_key, c.cell_type, c.taggs"
                    + (", c.depend_by " if has_depend_by else " ")
                    + "FROM arkana_dashboard_header h "
                    + "LEFT JOIN arkana_dashboard_cells c ON c.arkana_object_id = h.arkana_id "
                    + "WHERE h.arkana_id = %s"
                )
                cursor.execute(
                    query,
                    (int(self.arkana_id),),
                )
            rows = cursor.fetchall() or []
            self.cells = []
            header_group_set = False
            # Build lookup maps
            cells_by_id: dict[int, dict] = {}
            prev_of: dict[int, int | None] = {}
            id_set: set[int] = set()
            import json
            for r in rows:
                if not header_group_set:
                    self.arkana_group = int(r[0]) if r and r[0] is not None else None
                    header_group_set = True
                if ((6 if content_column is None else 7) <= len(r)) and r[1] is not None:
                    cid = int(r[1])
                    # Treat 0 as head marker as well as NULL
                    pid = int(r[2]) if r[2] is not None else None
                    if pid == 0:
                        pid = None
                    content_value = None
                    if content_column is not None and len(r) > 6:
                        raw = r[6]
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
                    cell = {
                        "cell_id": cid,
                        # order_id will be assigned after traversal
                        "order_id": None,
                        "prev_id": pid,
                        "prev": pid,
                        "cell_key": str(r[3]) if r[3] is not None else None,
                        "cell_type": str(r[4]) if r[4] is not None else None,
                        "taggs": self._taggs_to_storage(r[5]),
                        "content": content_value,
                    }
                    if has_depend_by:
                        depend_by_idx = 7 if content_column is not None else 6
                        cell["depend_by"] = int(r[depend_by_idx]) if len(r) > depend_by_idx and r[depend_by_idx] is not None else None
                    cells_by_id[cid] = cell
                    prev_of[cid] = pid
                    id_set.add(cid)

            # Find heads: prev_id is NULL/0 or not present among ids
            heads: list[int] = []
            for cid, pid in prev_of.items():
                if pid is None or pid not in id_set:
                    heads.append(cid)

            visited: set[int] = set()
            order_counter = 1

            # Traverse from each head, in stable order
            for head in sorted(heads):
                current = head
                while current is not None and current not in visited and current in cells_by_id:
                    cell = cells_by_id[current]
                    cell["order_id"] = order_counter
                    self.cells.append(cell)
                    visited.add(current)
                    order_counter += 1
                    # Find "next" as the one that has prev_id == current
                    nxt = None
                    for cid, pid in prev_of.items():
                        if cid not in visited and pid == current:
                            nxt = cid
                            break
                    current = nxt

            # Append any remaining (cycle/orphan) cells in deterministic order
            for cid in sorted(id_set):
                if cid not in visited:
                    cell = cells_by_id[cid]
                    cell["order_id"] = order_counter
                    self.cells.append(cell)
                    order_counter += 1

            # If there were no rows at all, still try to fetch header
            if not rows:
                cursor.execute(
                    "SELECT arkana_group FROM arkana_dashboard_header WHERE arkana_id = %s LIMIT 1",
                    (int(self.arkana_id),),
                )
                row = cursor.fetchone()
                if row is not None:
                    self.arkana_group = int(row[0]) if row[0] is not None else None
                self.cells = []
        else:
            # Legacy order_id-based loading
            if content_column is not None:
                query = (
                    f"SELECT h.arkana_group, c.cell_id, c.{order_column}, "
                    + ("c.prev_id, " if uses_prev else "")
                    + "c.cell_key, c.cell_type, c.taggs, "
                    + f"c.{content_column}"
                    + (", c.depend_by " if has_depend_by else " ")
                    + "FROM arkana_dashboard_header h "
                    + "LEFT JOIN arkana_dashboard_cells c ON c.arkana_object_id = h.arkana_id "
                    + "WHERE h.arkana_id = %s "
                    + f"ORDER BY c.{order_column}"
                )
                cursor.execute(
                    query,
                    (int(self.arkana_id),),
                )
            else:
                query = (
                    f"SELECT h.arkana_group, c.cell_id, c.{order_column}, "
                    + ("c.prev_id, " if uses_prev else "")
                    + "c.cell_key, c.cell_type, c.taggs"
                    + (", c.depend_by " if has_depend_by else " ")
                    + "FROM arkana_dashboard_header h "
                    + "LEFT JOIN arkana_dashboard_cells c ON c.arkana_object_id = h.arkana_id "
                    + "WHERE h.arkana_id = %s "
                    + f"ORDER BY c.{order_column}"
                )
                cursor.execute(
                    query,
                    (int(self.arkana_id),),
                )
            rows = cursor.fetchall() or []
            self.cells = []
            header_group_set = False
            import json
            for r in rows:
                if not header_group_set:
                    self.arkana_group = int(r[0]) if r and r[0] is not None else None
                    header_group_set = True
                # When there are no fields yet, columns 1..5 can be None
                min_len = 6 + (1 if uses_prev else 0) + (1 if content_column is not None else 0)
                if min_len <= len(r) and r[1] is not None:
                    offset = 1 if uses_prev else 0
                    content_value = None
                    content_idx = 6 + offset
                    if content_column is not None and len(r) > content_idx:
                        raw = r[content_idx]
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
                    self.cells.append(
                        {
                            "cell_id": int(r[1]) if r[1] is not None else None,
                            "order_id": int(r[2]) if r[2] is not None else None,
                            "prev_id": int(r[3]) if uses_prev and r[3] is not None else None,
                            "prev": int(r[3]) if uses_prev and r[3] is not None else None,
                            "cell_key": str(r[3 + offset]) if r[3 + offset] is not None else None,
                            "cell_type": str(r[4 + offset]) if r[4 + offset] is not None else None,
                            "taggs": self._taggs_to_storage(r[5 + offset]),
                            "content": content_value,
                            "depend_by": int(r[content_idx + 1]) if has_depend_by and len(r) > content_idx + 1 and r[content_idx + 1] is not None else None,
                        }
                    )

            # If no rows returned at all (no fields yet), still fetch header once
            if not rows:
                cursor.execute(
                    "SELECT arkana_group FROM arkana_dashboard_header WHERE arkana_id = %s LIMIT 1",
                    (int(self.arkana_id),),
                )
                row = cursor.fetchone()
                if row is not None:
                    self.arkana_group = int(row[0]) if row[0] is not None else None
                self.cells = []

        return self

    def to_json(self) -> dict:
        # Start with base fields from interface
        data = super().to_json()
        # Ensure known board-specific fields are present
        data["arkana_group"] = self.arkana_group
        if self.cells is not None:
            data["cells"] = [self._serialize_cell(cell) for cell in self.cells]
        # Include any other public instance attributes not already captured
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            if key == "db_connection":
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

        # Use shared cursor/connection
        _, cursor = self._ensure_model_cursor()

        # Ensure required tables exist
        if not self._has_table("arkana_dashboard_header"):
            raise RuntimeError("Required table 'arkana_dashboard_header' not found")
        if not self._has_table("arkana_dashboard_cells"):
            raise RuntimeError("Required table 'arkana_dashboard_cells' not found")

        # Check if a dashboard header row already exists
        cursor.execute(
            "SELECT 1 FROM arkana_dashboard_header WHERE arkana_id = %s LIMIT 1",
            (int(self.arkana_id),),
        )
        exists = cursor.fetchone()

        group_val = int(self.arkana_group) if self.arkana_group is not None else None

        if exists is None:
            # Insert new header row
            cursor.execute(
                "INSERT INTO arkana_dashboard_header (arkana_id, arkana_group) VALUES (%s, %s)",
                (int(self.arkana_id), group_val),
            )
            self._commit_model()
        else:
            # Update existing header row
            cursor.execute(
                "UPDATE arkana_dashboard_header SET arkana_group = %s WHERE arkana_id = %s",
                (group_val, int(self.arkana_id)),
            )
            self._commit_model()

        # Persist cells: replace all rows for this object id
        # Normalize in-memory cells list
        if self.cells is None:
            self.cells = []

        # Delete existing rows
        cursor.execute(
            "DELETE FROM arkana_dashboard_cells WHERE arkana_object_id = %s",
            (int(self.arkana_id),),
        )

        uses_prev = self._has_column("arkana_dashboard_cells", "prev_id")
        has_content = self._has_column("arkana_dashboard_cells", "content")
        content_column = "content" if has_content else ("cell_value" if self._has_column("arkana_dashboard_cells", "cell_value") else None)
        order_column = "order_id" if self._has_column("arkana_dashboard_cells", "order_id") else ("run_order" if self._has_column("arkana_dashboard_cells", "run_order") else None)
        has_depend_by = self._has_column("arkana_dashboard_cells", "depend_by")

        # Insert all cells in order
        # Requirement: cell_id must be assigned per dashboard separately (no AUTO_INCREMENT expected).
        # We assign cell_id deterministically from 1..n for this arkana_object_id and align order_id accordingly.
        order_counter = 1
        prev_cell_id: int | None = None
        import json
        for cell in self.cells:
            cell_key = cell.get("cell_key") or f"cell_{order_counter}"
            cell_type = cell.get("cell_type") or "text"
            tag_str = self._taggs_to_storage(cell.get("taggs"))
            cell_id_for_board = int(cell.get("cell_id") or order_counter)
            prev_id_value = cell.get("prev_id", cell.get("prev"))
            if prev_id_value in (None, ""):
                prev_id_value = prev_cell_id if prev_cell_id is not None else 0
            depend_by_value = cell.get("depend_by")
            content_value = cell.get("content")
            # Serialize content to JSON if column exists
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
                values.append(int(order_counter))
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
                f"INSERT INTO arkana_dashboard_cells ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values),
            )

            # Update in-memory ids to reflect persisted values
            cell["cell_id"] = cell_id_for_board
            cell["order_id"] = order_counter
            cell["prev_id"] = int(prev_id_value)
            cell["prev"] = int(prev_id_value)
            prev_cell_id = cell_id_for_board
            order_counter += 1

        self._commit_model()

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
        order_id = len(self.cells) + 1
        self.cells.append(
            {
                "cell_id": None,
                "order_id": order_id,
                "prev_id": self.cells[-1].get("cell_id") if self.cells else 0,
                "prev": self.cells[-1].get("cell_id") if self.cells else 0,
                "depend_by": None,
                "cell_key": f"cell_{order_id}",
                "cell_type": str(cell_type),
                "taggs": tag_str,
                "content": payload,
            }
        )
        return None
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
        max_order = len(self.cells)

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
        cell_key = str(payload.get("cell_key") or f"cell_{target}")
        cell_type = str(payload.get("cell_type") or "text")

        # Build new cell dict
        new_cell: dict = {
            "cell_id": None,
            "order_id": target,
            "cell_key": cell_key,
            "cell_type": cell_type,
            "taggs": payload.get("taggs"),
        }

        # Attach any additional, non-persisted attributes (kept in-memory)
        for k, v in payload.items():
            if k in {"cell_key", "cell_type", "taggs"}:
                continue
            new_cell[k] = v

        # Insert in-memory and re-number orders
        self.cells.insert(target - 1, new_cell)
        for i, c in enumerate(self.cells, start=1):
            c["order_id"] = i
        return self

    # --------- Cell tag management (no content persistence) ---------
    def update_cell(self, id: int, new_value: dict | None = None, **kwargs):
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

        # Resolve target cell by cell_id, else by index (1-based)
        target_cell = None
        try:
            id_int = int(id)
        except Exception:
            id_int = -1
        for c in self.cells:
            if c.get("cell_id") == id_int:
                target_cell = c
                break
        if target_cell is None and 1 <= id_int <= len(self.cells):
            target_cell = self.cells[id_int - 1]
        if target_cell is None:
            return self

        # Normalize taggs
        if "taggs" in payload:
            payload["taggs"] = self._taggs_to_storage(payload.get("taggs"))

        # Apply updates (persisted keys + any extras)
        for k, v in payload.items():
            target_cell[k] = v

        return self

    def get_cell(self, identifier: int | str) -> dict | None:
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        target = self._resolve_cell(identifier)
        if target is None:
            return None
        return self._serialize_cell(target)

    def delete_cell(self, identifier: int | str):
        if self.cells is None:
            self.load()
        if self.cells is None:
            self.cells = []

        target = self._resolve_cell(identifier)
        if target is None:
            return self

        self.cells.remove(target)
        for index, cell in enumerate(self.cells, start=1):
            cell["order_id"] = index
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

    def _resolve_cell(self, identifier: int | str) -> dict | None:
        if self.cells is None:
            self.cells = []

        try:
            int_identifier = int(identifier)
        except Exception:
            int_identifier = None

        if int_identifier is not None:
            for cell in self.cells:
                if cell.get("cell_id") == int_identifier:
                    return cell
            if 1 <= int_identifier <= len(self.cells):
                return self.cells[int_identifier - 1]

        str_identifier = str(identifier)
        for cell in self.cells:
            if str(cell.get("cell_key")) == str_identifier:
                return cell
        return None

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

    def _serialize_cell(self, cell: dict) -> dict:
        serialized = dict(cell)
        serialized["taggs"] = self._taggs_to_list(serialized.get("taggs"))
        return serialized

    def get_next_running_id(self) -> int:
        #todo get next running id 
        running_id = 0
        return 0
