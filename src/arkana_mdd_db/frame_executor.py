from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .main_db import ArkanaMainDB

INTERPOLATION_RE = re.compile(r"\^\-\^\{([^}]+)\}\^\-\^")


class FrameExecutionError(RuntimeError):
    pass


@dataclass
class ExecutionContext:
    input_parameters: dict[str, Any]
    tables: dict[str, list[dict[str, Any]]]
    model_results: dict[str, Any]
    output_fields: dict[str, Any]


class FrameExecutor:
    def __init__(self, main_db: ArkanaMainDB) -> None:
        self.main_db = main_db

    def execute(
        self,
        frame: dict[str, Any],
        input_parameters: dict[str, Any] | None = None,
        referenced_frames: dict[str, dict[str, Any]] | None = None,
        call_stack: set[int] | None = None,
    ) -> dict[str, Any]:
        params = input_parameters or {}
        refs = referenced_frames or {}
        stack = call_stack or set()
        frame_id = frame.get("frame_id")
        if frame_id is not None:
            if int(frame_id) in stack:
                raise FrameExecutionError(f"Circular model reference detected for frame_id={frame_id}")
            stack = set(stack)
            stack.add(int(frame_id))

        self._validate_input_parameters(frame, params)
        db_map = {entry["db_key"]: entry for entry in frame.get("dbs", [])}
        tables = self._load_tables(frame, db_map, params)

        context = ExecutionContext(
            input_parameters=params,
            tables=tables,
            model_results={},
            output_fields={},
        )
        context.model_results = self._resolve_model_refs(frame, refs, context, stack)

        result: dict[str, Any] = {}
        for field_name, definition in frame.get("model_fields", {}).items():
            value = self._resolve_path(definition.get("path", ""), definition, frame, context)
            result[field_name] = self._cast_value(value, definition.get("type", "str"))
            context.output_fields[field_name] = result[field_name]

        return result

    def _validate_input_parameters(self, frame: dict[str, Any], params: dict[str, Any]) -> None:
        expected = frame.get("input_parameters", {})
        for param_key in expected:
            if param_key not in params:
                raise FrameExecutionError(f"Missing required input parameter: {param_key}")

    def _load_tables(
        self,
        frame: dict[str, Any],
        db_map: dict[str, dict[str, Any]],
        input_parameters: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        tables = sorted(frame.get("tables", []), key=lambda item: item.get("select_order", 0))
        for table in tables:
            table_key = table["table_key"]
            db_key = table["db"]
            db_definition = db_map.get(db_key)
            if db_definition is None:
                raise FrameExecutionError(f"Unknown db_key in frame: {db_key}")
            connection_id = int(db_definition["connection_id"])
            connection_record = self.main_db.get_db_connection(connection_id)
            if connection_record is None:
                raise FrameExecutionError(f"Unknown connection_id: {connection_id}")
            values = tuple(self._resolve_query_value(value, input_parameters, result) for value in table.get("values", []))
            rows = self._run_select(
                connection_record,
                table["select_statement"],
                values,
                credential_db_id=int(db_definition["db_id"]) if db_definition.get("db_id") is not None else None,
                database=db_definition.get("db_name"),
            )
            if table.get("distinct"):
                rows = self._distinct_rows(rows)
            result[table_key] = rows
        return result

    def _run_select(
        self,
        connection_record: Any,
        query: str,
        values: tuple[Any, ...],
        *,
        credential_db_id: int | None,
        database: str | None,
    ) -> list[dict[str, Any]]:
        if connection_record.db_type != "MySQL":
            raise FrameExecutionError("Only MySQL frame execution is implemented")
        with self.main_db.connect_target(
            connection_record,
            database,
            credential_db_id=credential_db_id,
        ) as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, values)
                return list(cursor.fetchall())
            finally:
                cursor.close()

    def _distinct_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[tuple[str, Any], ...]] = set()
        unique_rows: list[dict[str, Any]] = []
        for row in rows:
            marker = tuple(sorted(row.items()))
            if marker in seen:
                continue
            seen.add(marker)
            unique_rows.append(row)
        return unique_rows

    def _resolve_query_value(
        self,
        value: Any,
        input_parameters: dict[str, Any],
        tables: dict[str, list[dict[str, Any]]],
    ) -> Any:
        if not isinstance(value, str):
            return value
        if value.startswith("parameter:"):
            return input_parameters[value.split(":", 1)[1]]
        if value.startswith("table:"):
            table_key, field_name, row_index = self._parse_table_field_path(value)
            return tables[table_key][row_index][field_name]
        return value

    def _resolve_model_refs(
        self,
        frame: dict[str, Any],
        referenced_frames: dict[str, dict[str, Any]],
        context: ExecutionContext,
        call_stack: set[int],
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for model_ref in frame.get("model_ref", []):
            frame_id = int(model_ref["frame_id"])
            target_frame = referenced_frames.get(str(frame_id))
            if target_frame is None:
                raise FrameExecutionError(f"Missing referenced frame for frame_id={frame_id}")
            mapped_params: dict[str, Any] = {}
            for target_param, source in model_ref.get("parameter", {}).items():
                mapped_params[target_param] = self._resolve_source_reference(source, context)
            results[model_ref["model_key"]] = self.execute(
                target_frame,
                input_parameters=mapped_params,
                referenced_frames=referenced_frames,
                call_stack=call_stack,
            )
        return results

    def _resolve_path(
        self,
        path: str,
        definition: dict[str, Any],
        frame: dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        if path == "const":
            return definition.get("value")
        if path.startswith("parameter:"):
            key = path.split(":", 1)[1]
            return context.input_parameters[key]
        if path.startswith("table:") and "-" in path:
            table_key, field_name, row_index = self._parse_table_field_path(path)
            return context.tables[table_key][row_index][field_name]
        if path.startswith("table:"):
            table_key = path.split(":", 1)[1]
            return context.tables[table_key]
        if path.startswith("model:"):
            model_key = path.split(":", 1)[1]
            return context.model_results[model_key]
        if isinstance(path, str) and "^-^{" in path:
            return self._interpolate_string(path, context)
        raise FrameExecutionError(f"Unsupported path: {path}")

    def _resolve_source_reference(self, source: Any, context: ExecutionContext) -> Any:
        if not isinstance(source, str):
            return source
        if source in context.output_fields:
            return context.output_fields[source]
        if source in context.input_parameters:
            return context.input_parameters[source]
        if source.startswith(("parameter:", "table:", "model:")):
            return self._resolve_path(source, {}, {}, context)
        return source

    def _interpolate_string(self, template: str, context: ExecutionContext) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in context.output_fields:
                return str(context.output_fields[key])
            if key in context.input_parameters:
                return str(context.input_parameters[key])
            raise FrameExecutionError(f"Interpolation placeholder could not be resolved: {key}")

        return INTERPOLATION_RE.sub(replace, template)

    def _cast_value(self, value: Any, target_type: str) -> Any:
        if target_type in {"str", "string"}:
            return "" if value is None else str(value)
        if target_type == "int":
            return int(value)
        if target_type == "float":
            return float(value)
        if target_type == "bool":
            return bool(value)
        if target_type in {"dict", "list", "json", "raw"}:
            return value
        raise FrameExecutionError(f"Unsupported target type: {target_type}")

    def _parse_table_field_path(self, path: str) -> tuple[str, str, int]:
        body = path.split(":", 1)[1]
        table_key, remainder = body.split("-", 1)
        field_name, row_text = remainder.rsplit("-", 1)
        return table_key, field_name, int(row_text)
