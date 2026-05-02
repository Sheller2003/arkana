from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
import secrets
from typing import Any, Iterator
from urllib.parse import urlparse

import keyring
from keyring.errors import NoKeyringError
import mysql.connector
from mysql.connector import MySQLConnection

from .config import ArkanaMainDBConfig
from .constants import DEFAULT_MYSQL_PORT, DEFAULT_POSTGRES_PORT


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    user_name: str
    user_role: str
    user_storage_db_id: int | None
    supabase_user_id: str | None = None
    supabase_email: str | None = None


@dataclass(frozen=True)
class DBConnectionRecord:
    db_con_id: int
    user_group: int
    owner: str
    url: str | None
    ip: str | None
    server_description: str | None
    default_user: str | None
    admin_user: str | None
    db_type: str
    data_source_id: int | None = None
    server_id: int | None = None
    server_connection_id: int | None = None
    data_source_type: str | None = None
    data_source_subtype: str | None = None
    server_key: str | None = None
    server_type: str | None = None
    connection_kind: str | None = None


@dataclass(frozen=True)
class DBSchemaRecord:
    db_id: int
    db_con_id: int
    user_group: int
    owner: str
    url: str | None
    ip: str | None
    db_name: str
    db_description: str | None
    data_source_id: int | None = None


@dataclass(frozen=True)
class ArkanaServerRecord:
    server_id: int
    user_group: int
    owner: str
    server_key: str
    server_type: str
    server_label: str | None
    server_description: str | None


@dataclass(frozen=True)
class ArkanaServerConnectionRecord:
    server_connection_id: int
    user_group: int
    owner: str
    server_id: int
    connection_kind: str
    url: str | None
    ip: str | None
    auth_mode: str | None
    metadata_json: dict[str, Any] | None


@dataclass(frozen=True)
class ArkanaDataSourceRecord:
    data_source_id: int
    user_group: int
    owner: str
    data_source_type: str
    data_source_subtype: str | None
    data_source_key: str | None
    data_source_label: str | None
    server_id: int
    server_connection_id: int
    metadata_json: dict[str, Any] | None


@dataclass(frozen=True)
class PersonalUserRecord:
    db_id: int
    db_name: str
    arkana_user_id: str
    arkana_user_name: str
    db_user_name: str


@dataclass(frozen=True)
class DBWithConnection:
    schema: DBSchemaRecord
    connection: DBConnectionRecord


class ArkanaMainDB:
    def __init__(self, config: ArkanaMainDBConfig) -> None:
        self.config = config

    @contextmanager
    def connect(self) -> Iterator[MySQLConnection]:
        connection = mysql.connector.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
        )
        try:
            yield connection
        finally:
            connection.close()

    def authenticate_api_user(self, username: str, password: str) -> AuthUser | None:
        user = self.get_user_by_login_identifier(username)
        if user is None:
            return None

        password_candidates: list[str] = []
        for candidate in (username, user.user_name, user.supabase_email):
            normalized = str(candidate).strip() if candidate is not None else ""
            if normalized and normalized not in password_candidates:
                password_candidates.append(normalized)

        password_matches = False
        for candidate in password_candidates:
            stored_password = self._get_api_password(candidate)
            if stored_password is not None and secrets.compare_digest(stored_password, password):
                password_matches = True
                break
        if not password_matches:
            return None

        return user

    @staticmethod
    def _username_env_key(username: str) -> str:
        normalized = []
        for char in str(username):
            normalized.append(char.upper() if char.isalnum() else "_")
        return "ARKANA_API_PASSWORD_" + "".join(normalized)

    def _get_api_password(self, username: str) -> str | None:
        try:
            stored_password = keyring.get_password(self.config.api_keyring_service, username)
        except NoKeyringError:
            stored_password = None
        if stored_password:
            return stored_password

        specific_env = os.getenv(self._username_env_key(username))
        if specific_env:
            return specific_env

        shared_env = os.getenv("ARKANA_API_PASSWORD")
        if shared_env:
            return shared_env

        return None

    def get_user_by_name(self, username: str) -> AuthUser | None:
        query = """
            SELECT user_id, user_name, user_role, user_storage_db_id, supabase_user_id, supabase_email
            FROM arkana_user
            WHERE user_name = %s
            LIMIT 1
        """
        row = self._fetchone(query, (username,))
        return self._row_to_auth_user(row)

    def get_user_by_login_identifier(self, identifier: str) -> AuthUser | None:
        query = """
            SELECT user_id, user_name, user_role, user_storage_db_id, supabase_user_id, supabase_email
            FROM arkana_user
            WHERE user_name = %s OR supabase_email = %s
            LIMIT 1
        """
        row = self._fetchone(query, (identifier, identifier))
        return self._row_to_auth_user(row)

    def get_db_schema(self, db_id: int) -> DBSchemaRecord | None:
        row = None
        queries = [
            """
            SELECT db_id, db_con_id, user_group, owner, url, ip, db_name, db_description, data_source_id
            FROM db_schema
            WHERE db_id = %s
            LIMIT 1
            """,
            """
            SELECT db_id, db_con_id, user_group, owner, url, ip, db_name, db_description
            FROM db_schema
            WHERE db_id = %s
            LIMIT 1
            """,
        ]
        for query in queries:
            try:
                row = self._fetchone(query, (db_id,))
                break
            except Exception:
                continue
        return self._row_to_schema(row)

    def get_db_connection(self, db_con_id: int) -> DBConnectionRecord | None:
        row = None
        queries = [
            """
            SELECT
                c.db_con_id,
                c.user_group,
                c.owner,
                c.url,
                c.ip,
                c.server_description,
                c.default_user,
                c.admin_user,
                c.db_type,
                c.data_source_id,
                c.server_id,
                c.server_connection_id,
                ds.data_source_type,
                ds.data_source_subtype,
                s.server_key,
                s.server_type,
                sc.connection_kind
            FROM db_connection AS c
            LEFT JOIN arkana_data_source AS ds ON ds.data_source_id = c.data_source_id
            LEFT JOIN arkana_server AS s ON s.server_id = c.server_id
            LEFT JOIN arkana_server_connection AS sc ON sc.server_connection_id = c.server_connection_id
            WHERE c.db_con_id = %s
            LIMIT 1
            """,
            """
            SELECT db_con_id, user_group, owner, url, ip, server_description, default_user, admin_user, db_type
            FROM db_connection
            WHERE db_con_id = %s
            LIMIT 1
            """,
        ]
        for query in queries:
            try:
                row = self._fetchone(query, (db_con_id,))
                break
            except Exception:
                continue
        return self._row_to_connection(row)

    def get_db_with_connection(self, db_id: int) -> DBWithConnection | None:
        schema = self.get_db_schema(db_id)
        if schema is None:
            return None
        connection = self.get_db_connection(schema.db_con_id)
        if connection is None:
            return None
        return DBWithConnection(schema=schema, connection=connection)

    def list_tables(self, db_id: int) -> list[dict[str, Any]]:
        db_record = self.get_db_with_connection(db_id)
        if db_record is None:
            raise ValueError(f"Unknown db_id: {db_id}")
        if db_record.connection.db_type != "MySQL":
            raise NotImplementedError("Only MySQL metadata inspection is implemented")

        with self.connect_target(
            db_record.connection,
            db_record.schema.db_name,
            credential_db_id=db_record.schema.db_id,
        ) as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT table_schema, table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    ORDER BY table_name
                    """,
                    (db_record.schema.db_name,),
                )
                return list(cursor.fetchall())
            finally:
                cursor.close()

    def get_table_info(self, db_id: int, table_name: str) -> dict[str, Any]:
        db_record = self.get_db_with_connection(db_id)
        if db_record is None:
            raise ValueError(f"Unknown db_id: {db_id}")
        if db_record.connection.db_type != "MySQL":
            raise NotImplementedError("Only MySQL metadata inspection is implemented")

        with self.connect_target(
            db_record.connection,
            db_record.schema.db_name,
            credential_db_id=db_record.schema.db_id,
        ) as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT column_name, data_type, is_nullable, column_key
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (db_record.schema.db_name, table_name),
                )
                columns = list(cursor.fetchall())
            finally:
                cursor.close()
        return {"table_name": table_name, "columns": columns}

    def build_key_models(
        self,
        db_id: int,
        start_tables: list[str] | None = None,
        max_distance: int | None = None,
        include_all: bool = False,
    ) -> dict[str, Any]:
        db_record = self.get_db_with_connection(db_id)
        if db_record is None:
            raise ValueError(f"Unknown db_id: {db_id}")
        if db_record.connection.db_type != "MySQL":
            raise NotImplementedError("Only MySQL key model discovery is implemented")

        with self.connect_target(
            db_record.connection,
            db_record.schema.db_name,
            credential_db_id=db_record.schema.db_id,
        ) as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT
                        table_name,
                        referenced_table_name
                    FROM information_schema.key_column_usage
                    WHERE table_schema = %s
                      AND referenced_table_name IS NOT NULL
                    """,
                    (db_record.schema.db_name,),
                )
                edges = list(cursor.fetchall())
            finally:
                cursor.close()

        graph: dict[str, set[str]] = {}
        all_tables = {edge["table_name"] for edge in edges} | {edge["referenced_table_name"] for edge in edges}
        for edge in edges:
            source = str(edge["table_name"])
            target = str(edge["referenced_table_name"])
            graph.setdefault(source, set()).add(target)
            graph.setdefault(target, set()).add(source)

        if include_all:
            with self.connect_target(
                db_record.connection,
                db_record.schema.db_name,
                credential_db_id=db_record.schema.db_id,
            ) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                        """,
                        (db_record.schema.db_name,),
                    )
                    for (table_name,) in cursor.fetchall():
                        all_tables.add(str(table_name))
                finally:
                    cursor.close()
            for table_name in all_tables:
                graph.setdefault(table_name, set())

        seeds = start_tables or sorted(graph)
        groups: list[list[str]] = []
        visited: set[str] = set()
        for seed in seeds:
            if seed in visited:
                continue
            stack: list[tuple[str, int]] = [(seed, 0)]
            component: list[str] = []
            while stack:
                current, distance = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                if max_distance is not None and distance >= max_distance:
                    continue
                for neighbor in sorted(graph.get(current, set()), reverse=True):
                    if neighbor not in visited:
                        stack.append((neighbor, distance + 1))
            if component:
                groups.append(sorted(component))

        return {
            "db_id": db_id,
            "groups": groups,
            "include_all": include_all,
            "start_tables": start_tables or [],
            "max_distance": max_distance,
        }

    def create_db_schema(self, payload: dict[str, Any]) -> DBSchemaRecord:
        resolved_data_source_id = payload.get("data_source_id")
        if resolved_data_source_id is None:
            connection_record = self.get_db_connection(int(payload["db_con_id"]))
            if connection_record is not None:
                resolved_data_source_id = connection_record.data_source_id
        try:
            new_id = self._insert(
                """
                INSERT INTO db_schema (db_con_id, user_group, owner, url, ip, db_name, db_description, data_source_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload["db_con_id"],
                    payload["user_group"],
                    payload["owner"],
                    payload.get("url"),
                    payload.get("ip"),
                    payload["db_name"],
                    payload.get("db_description"),
                    resolved_data_source_id,
                ),
            )
        except Exception:
            new_id = self._insert(
                """
                INSERT INTO db_schema (db_con_id, user_group, owner, url, ip, db_name, db_description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload["db_con_id"],
                    payload["user_group"],
                    payload["owner"],
                    payload.get("url"),
                    payload.get("ip"),
                    payload["db_name"],
                    payload.get("db_description"),
                ),
            )
        record = self.get_db_schema(new_id)
        if record is None:
            raise RuntimeError("Inserted db_schema record could not be reloaded")
        return record

    def create_db_connection(self, payload: dict[str, Any]) -> DBConnectionRecord:
        normalized = self._normalize_db_connection_payload(payload)
        try:
            if normalized.get("server_id") is None:
                normalized["server_id"] = self.create_arkana_server(normalized).server_id
            if normalized.get("server_connection_id") is None:
                normalized["server_connection_id"] = self.create_arkana_server_connection(normalized).server_connection_id
            if normalized.get("data_source_id") is None:
                normalized["data_source_id"] = self.create_data_source(normalized).data_source_id
        except Exception:
            normalized = dict(payload)

        try:
            new_id = self._insert(
                """
                INSERT INTO db_connection (
                    user_group, owner, url, ip, server_description, default_user, admin_user, db_type,
                    data_source_id, server_id, server_connection_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    normalized["user_group"],
                    normalized["owner"],
                    normalized.get("url"),
                    normalized.get("ip"),
                    normalized.get("server_description"),
                    normalized.get("default_user"),
                    normalized.get("admin_user"),
                    normalized["db_type"],
                    normalized.get("data_source_id"),
                    normalized.get("server_id"),
                    normalized.get("server_connection_id"),
                ),
            )
        except Exception:
            new_id = self._insert(
                """
                INSERT INTO db_connection (
                    user_group, owner, url, ip, server_description, default_user, admin_user, db_type
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    normalized["user_group"],
                    normalized["owner"],
                    normalized.get("url"),
                    normalized.get("ip"),
                    normalized.get("server_description"),
                    normalized.get("default_user"),
                    normalized.get("admin_user"),
                    normalized["db_type"],
                ),
            )
        record = self.get_db_connection(new_id)
        if record is None:
            raise RuntimeError("Inserted db_connection record could not be reloaded")
        return record

    def create_arkana_server(self, payload: dict[str, Any]) -> ArkanaServerRecord:
        normalized = self._normalize_db_connection_payload(payload)
        new_id = self._insert(
            """
            INSERT INTO arkana_server (
                user_group, owner, server_key, server_type, server_label, server_description
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                normalized["user_group"],
                normalized["owner"],
                normalized["server_key"],
                normalized["server_type"],
                normalized.get("server_label"),
                normalized.get("server_description"),
            ),
        )
        return ArkanaServerRecord(
            server_id=new_id,
            user_group=int(normalized["user_group"]),
            owner=str(normalized["owner"]),
            server_key=str(normalized["server_key"]),
            server_type=str(normalized["server_type"]),
            server_label=str(normalized.get("server_label")) if normalized.get("server_label") is not None else None,
            server_description=(
                str(normalized.get("server_description")) if normalized.get("server_description") is not None else None
            ),
        )

    def create_arkana_server_connection(self, payload: dict[str, Any]) -> ArkanaServerConnectionRecord:
        normalized = self._normalize_db_connection_payload(payload)
        if normalized.get("server_id") is None:
            normalized["server_id"] = self.create_arkana_server(normalized).server_id
        metadata_json = normalized.get("metadata_json")
        metadata_text = json.dumps(metadata_json) if metadata_json is not None else None
        new_id = self._insert(
            """
            INSERT INTO arkana_server_connection (
                user_group, owner, server_id, connection_kind, url, ip, auth_mode, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                normalized["user_group"],
                normalized["owner"],
                normalized["server_id"],
                normalized["connection_kind"],
                normalized.get("url"),
                normalized.get("ip"),
                normalized.get("auth_mode"),
                metadata_text,
            ),
        )
        return ArkanaServerConnectionRecord(
            server_connection_id=new_id,
            user_group=int(normalized["user_group"]),
            owner=str(normalized["owner"]),
            server_id=int(normalized["server_id"]),
            connection_kind=str(normalized["connection_kind"]),
            url=str(normalized.get("url")) if normalized.get("url") is not None else None,
            ip=str(normalized.get("ip")) if normalized.get("ip") is not None else None,
            auth_mode=str(normalized.get("auth_mode")) if normalized.get("auth_mode") is not None else None,
            metadata_json=metadata_json if isinstance(metadata_json, dict) else None,
        )

    def create_data_source(self, payload: dict[str, Any]) -> ArkanaDataSourceRecord:
        normalized = self._normalize_db_connection_payload(payload)
        if normalized.get("server_id") is None:
            normalized["server_id"] = self.create_arkana_server(normalized).server_id
        if normalized.get("server_connection_id") is None:
            normalized["server_connection_id"] = self.create_arkana_server_connection(normalized).server_connection_id
        metadata_json = normalized.get("metadata_json")
        metadata_text = json.dumps(metadata_json) if metadata_json is not None else None
        new_id = self._insert(
            """
            INSERT INTO arkana_data_source (
                user_group, owner, data_source_type, data_source_subtype, data_source_key,
                data_source_label, server_id, server_connection_id, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                normalized["user_group"],
                normalized["owner"],
                normalized["data_source_type"],
                normalized.get("data_source_subtype"),
                normalized.get("data_source_key"),
                normalized.get("data_source_label"),
                normalized["server_id"],
                normalized["server_connection_id"],
                metadata_text,
            ),
        )
        return ArkanaDataSourceRecord(
            data_source_id=new_id,
            user_group=int(normalized["user_group"]),
            owner=str(normalized["owner"]),
            data_source_type=str(normalized["data_source_type"]),
            data_source_subtype=(
                str(normalized.get("data_source_subtype")) if normalized.get("data_source_subtype") is not None else None
            ),
            data_source_key=(
                str(normalized.get("data_source_key")) if normalized.get("data_source_key") is not None else None
            ),
            data_source_label=(
                str(normalized.get("data_source_label")) if normalized.get("data_source_label") is not None else None
            ),
            server_id=int(normalized["server_id"]),
            server_connection_id=int(normalized["server_connection_id"]),
            metadata_json=metadata_json if isinstance(metadata_json, dict) else None,
        )

    def get_personal_user(self, db_id: int) -> PersonalUserRecord | None:
        query = """
            SELECT d.db_id, d.db_name, u.user_id, u.user_name, p.db_user_name
            FROM ark_db_personal_user AS p
            JOIN arkana_user AS u ON u.user_id = p.arkana_user_id
            JOIN db_schema AS d ON d.db_id = p.db_id
            WHERE p.db_id = %s
            ORDER BY u.user_name
            LIMIT 1
        """
        row = self._fetchone(query, (db_id,))
        return self._row_to_personal_user(row)

    def get_personal_user_for_arkana_user(self, db_id: int, arkana_user_id: str) -> PersonalUserRecord | None:
        query = """
            SELECT d.db_id, d.db_name, u.user_id, u.user_name, p.db_user_name
            FROM ark_db_personal_user AS p
            JOIN arkana_user AS u ON u.user_id = p.arkana_user_id
            JOIN db_schema AS d ON d.db_id = p.db_id
            WHERE p.db_id = %s
              AND p.arkana_user_id = %s
            LIMIT 1
        """
        row = self._fetchone(query, (db_id, arkana_user_id))
        return self._row_to_personal_user(row)

    def find_personal_user(
        self,
        db_identifier: str,
        arkana_username: str,
        db_username: str,
    ) -> PersonalUserRecord | None:
        query = """
            SELECT d.db_id, d.db_name, u.user_id, u.user_name, p.db_user_name
            FROM ark_db_personal_user AS p
            JOIN arkana_user AS u
              ON u.user_id = p.arkana_user_id
            JOIN db_schema AS d
              ON d.db_id = p.db_id
            WHERE (CAST(d.db_id AS CHAR) = %s OR d.db_name = %s)
              AND u.user_name = %s
              AND p.db_user_name = %s
            LIMIT 1
        """
        row = self._fetchone(query, (db_identifier, db_identifier, arkana_username, db_username))
        return self._row_to_personal_user(row)

    def create_personal_user(self, payload: dict[str, Any]) -> PersonalUserRecord:
        query = """
            INSERT INTO ark_db_personal_user (db_id, arkana_user_id, db_user_name)
            VALUES (%s, %s, %s)
        """
        self._insert(
            query,
            (payload["db_id"], payload["arkana_user_id"], payload["db_user_name"]),
        )
        query_reload = """
            SELECT d.db_id, d.db_name, u.user_id, u.user_name, p.db_user_name
            FROM ark_db_personal_user AS p
            JOIN arkana_user AS u ON u.user_id = p.arkana_user_id
            JOIN db_schema AS d ON d.db_id = p.db_id
            WHERE p.db_id = %s AND p.arkana_user_id = %s
            LIMIT 1
        """
        row = self._fetchone(query_reload, (payload["db_id"], payload["arkana_user_id"]))
        result = self._row_to_personal_user(row)
        if result is None:
            raise RuntimeError("Inserted personal user record could not be reloaded")
        return result

    def set_db_user_password(
        self,
        *,
        db_id: int,
        db_user_name: str,
        password: str,
        arkana_user_id: str | None = None,
    ) -> None:
        key = self.build_db_password_key(db_id, db_user_name, arkana_user_id)
        keyring.set_password(self.config.keyring_service, key, password)

    def user_can_access_group(self, user: AuthUser, group_id: int) -> bool:
        if user.user_role in {"root", "admin"}:
            return True
        if group_id == 0:
            return True
        return False

    def user_can_access_db(self, user: AuthUser, db_id: int) -> bool:
        db_record = self.get_db_schema(db_id)
        if db_record is None:
            return False
        return self.user_can_access_group(user, db_record.user_group)

    @contextmanager
    def connect_target(
        self,
        connection_record: DBConnectionRecord,
        database: str | None = None,
        *,
        credential_db_id: int | None = None,
        user_name: str | None = None,
        password: str | None = None,
        arkana_user_id: str | None = None,
    ) -> Iterator[MySQLConnection]:
        host, port = self._resolve_host_and_port(connection_record)
        effective_user = user_name or connection_record.default_user
        if effective_user is None:
            raise ValueError("No target database user configured")
        effective_password = password
        if effective_password is None:
            effective_password = self.get_db_user_password(
                db_id=credential_db_id,
                db_user_name=effective_user,
                arkana_user_id=arkana_user_id,
            )
        connection = mysql.connector.connect(
            host=host,
            port=port,
            database=database,
            user=effective_user,
            password=effective_password or "",
        )
        try:
            yield connection
        finally:
            connection.close()

    def get_db_user_password(
        self,
        *,
        db_id: int | None,
        db_user_name: str,
        arkana_user_id: str | None = None,
    ) -> str | None:
        if db_id is None:
            return None
        key = self.build_db_password_key(db_id, db_user_name, arkana_user_id)
        return keyring.get_password(self.config.keyring_service, key)

    def _resolve_host_and_port(self, connection_record: DBConnectionRecord) -> tuple[str, int]:
        target = connection_record.url or connection_record.ip
        if not target:
            raise ValueError("db_connection requires either url or ip")

        if "://" in target:
            parsed = urlparse(target)
            host = parsed.hostname or "127.0.0.1"
            if parsed.port is not None:
                return host, parsed.port
        if ":" in target and "://" not in target:
            host, _, maybe_port = target.partition(":")
            if maybe_port.isdigit():
                return host, int(maybe_port)
        default_port = DEFAULT_MYSQL_PORT if connection_record.db_type == "MySQL" else DEFAULT_POSTGRES_PORT
        return target, default_port

    def _fetchone(self, query: str, params: tuple[Any, ...]) -> tuple[Any, ...] | None:
        with self.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(query, params)
                return cursor.fetchone()
            finally:
                cursor.close()

    def _fetchall(self, query: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        with self.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(query, params)
                return list(cursor.fetchall() or [])
            finally:
                cursor.close()

    def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        with self.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(query, params)
                connection.commit()
            finally:
                cursor.close()

    def _insert(self, query: str, params: tuple[Any, ...]) -> int:
        with self.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(query, params)
                connection.commit()
                return int(cursor.lastrowid)
            finally:
                cursor.close()

    @staticmethod
    def build_db_password_key(db_id: int, db_user_name: str, arkana_user_id: str | None = None) -> str:
        if arkana_user_id:
            return f"db:{db_id}|arkana:{arkana_user_id}|dbuser:{db_user_name}"
        return f"db:{db_id}|shared:{db_user_name}"

    @staticmethod
    def _normalize_db_connection_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        db_type = str(normalized.get("db_type") or "MySQL")
        data_source_type = str(normalized.get("data_source_type") or "db")
        data_source_subtype = normalized.get("data_source_subtype")
        if data_source_type == "db" and not data_source_subtype and db_type.lower() == "supabase":
            data_source_subtype = "supabase_db"
        normalized["data_source_type"] = data_source_type
        normalized["data_source_subtype"] = (
            str(data_source_subtype).strip() if data_source_subtype not in (None, "") else None
        )
        server_key = normalized.get("server_key")
        if server_key in (None, ""):
            if normalized["data_source_subtype"] == "supabase_db":
                server_key = "supabase"
            elif normalized.get("url"):
                parsed = urlparse(str(normalized["url"]))
                server_key = parsed.hostname or db_type.lower()
            elif normalized.get("ip"):
                server_key = str(normalized["ip"])
            else:
                server_key = db_type.lower()
        normalized["server_key"] = str(server_key)
        if normalized.get("server_type") in (None, ""):
            normalized["server_type"] = "api"
        if normalized.get("connection_kind") in (None, ""):
            normalized["connection_kind"] = "url" if normalized.get("url") else ("ip" if normalized.get("ip") else "embedded")
        return normalized

    @staticmethod
    def _row_to_schema(row: tuple[Any, ...] | None) -> DBSchemaRecord | None:
        if row is None:
            return None
        return DBSchemaRecord(
            db_id=int(row[0]),
            db_con_id=int(row[1]),
            user_group=int(row[2]),
            owner=str(row[3]),
            url=str(row[4]) if row[4] is not None else None,
            ip=str(row[5]) if row[5] is not None else None,
            db_name=str(row[6]),
            db_description=str(row[7]) if row[7] is not None else None,
            data_source_id=int(row[8]) if len(row) > 8 and row[8] is not None else None,
        )

    @staticmethod
    def _row_to_connection(row: tuple[Any, ...] | None) -> DBConnectionRecord | None:
        if row is None:
            return None
        return DBConnectionRecord(
            db_con_id=int(row[0]),
            user_group=int(row[1]),
            owner=str(row[2]),
            url=str(row[3]) if row[3] is not None else None,
            ip=str(row[4]) if row[4] is not None else None,
            server_description=str(row[5]) if row[5] is not None else None,
            default_user=str(row[6]) if row[6] is not None else None,
            admin_user=str(row[7]) if row[7] is not None else None,
            db_type=str(row[8]),
            data_source_id=int(row[9]) if len(row) > 9 and row[9] is not None else None,
            server_id=int(row[10]) if len(row) > 10 and row[10] is not None else None,
            server_connection_id=int(row[11]) if len(row) > 11 and row[11] is not None else None,
            data_source_type=str(row[12]) if len(row) > 12 and row[12] is not None else None,
            data_source_subtype=str(row[13]) if len(row) > 13 and row[13] is not None else None,
            server_key=str(row[14]) if len(row) > 14 and row[14] is not None else None,
            server_type=str(row[15]) if len(row) > 15 and row[15] is not None else None,
            connection_kind=str(row[16]) if len(row) > 16 and row[16] is not None else None,
        )

    @staticmethod
    def _row_to_personal_user(row: tuple[Any, ...] | None) -> PersonalUserRecord | None:
        if row is None:
            return None
        return PersonalUserRecord(
            db_id=int(row[0]),
            db_name=str(row[1]),
            arkana_user_id=str(row[2]),
            arkana_user_name=str(row[3]),
            db_user_name=str(row[4]),
        )

    @staticmethod
    def _row_to_auth_user(row: tuple[Any, ...] | None) -> AuthUser | None:
        if row is None:
            return None
        return AuthUser(
            user_id=str(row[0]),
            user_name=str(row[1]),
            user_role=str(row[2]),
            user_storage_db_id=int(row[3]) if row[3] is not None else None,
            supabase_user_id=str(row[4]) if len(row) > 4 and row[4] is not None else None,
            supabase_email=str(row[5]) if len(row) > 5 and row[5] is not None else None,
        )
