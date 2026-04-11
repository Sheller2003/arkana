from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from mysql.connector import MySQLConnection

from src.arkana_mdd_db.main_db import ArkanaMainDB, DBConnectionRecord


@dataclass(frozen=True)
class ArkanaObjectDBConnection:
    main_db: ArkanaMainDB
    database: str | None
    connection_record: DBConnectionRecord | None = None
    credential_db_id: int | None = None
    user_name: str | None = None
    arkana_user_id: str | None = None
    is_default: bool = False

    @contextmanager
    def connect(self) -> Iterator[MySQLConnection]:
        if self.is_default:
            with self.main_db.connect() as connection:
                yield connection
            return

        if self.connection_record is None:
            raise ValueError("Missing connection_record for non-default object db connection")

        with self.main_db.connect_target(
            self.connection_record,
            self.database,
            credential_db_id=self.credential_db_id,
            user_name=self.user_name,
            arkana_user_id=self.arkana_user_id,
        ) as connection:
            yield connection

    def open_cursor(self):
        if self.is_default:
            connection = self.main_db.connect().__enter__()
        else:
            if self.connection_record is None:
                raise ValueError("Missing connection_record for non-default object db connection")
            connection = self.main_db.connect_target(
                self.connection_record,
                self.database,
                credential_db_id=self.credential_db_id,
                user_name=self.user_name,
                arkana_user_id=self.arkana_user_id,
            ).__enter__()
        return connection, connection.cursor()
