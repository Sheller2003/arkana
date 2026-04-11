

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


PlanId = Literal[0, 1]


def _plan_info(plan_id: PlanId) -> dict:
    if plan_id == 1:
        return {
            "plan_id": 1,
            "name": "enterprise",
            "max_tokens": None,  # unlimited
            "max_runtime_seconds": None,  # unlimited
            "unlimited": True,
        }
    # default plan (test user)
    return {
        "plan_id": 0,
        "name": "default",
        "max_tokens": 0,
        "max_runtime_seconds": 30 * 60,  # 30 minutes per day
        "unlimited": False,
    }


@dataclass
class _DailyUsage:
    tokens_used: int = 0
    runtime_seconds_used: int = 0
    day: date = date.today()


class ArkanaUsageAccounting:
    def __init__(self, user_id: str, service: str = "arkana", plan_id: PlanId = 0, main_db=None):
        self.user_id = user_id
        self.service = service
        self._plan_id: PlanId = plan_id
        self._usage: _DailyUsage = _DailyUsage()
        self.main_db = main_db

    def _ensure_today(self) -> None:
        # rotate usage on day change
        if self._usage.day != date.today():
            self._usage = _DailyUsage()

    def load_by_db(self) -> "ArkanaUsageAccounting":
        self._ensure_today()
        if self.main_db is None:
            return self

        service3 = (self.service or "ark").lower()[:3]
        sql = (
            """
            SELECT used_time, used_tokens, pay_model
            FROM user_runtime_usage_accounting
            WHERE user_id = %s
              AND `date` = %s
              AND service = %s
            ORDER BY pay_model DESC
            LIMIT 1
            """
        )

        with self.main_db.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, (self.user_id, self._usage.day, service3))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return self

        self._usage.runtime_seconds_used = int(row[0]) if row[0] is not None else 0
        self._usage.tokens_used = int(row[1]) if row[1] is not None else 0
        self._plan_id = int(row[2]) if row[2] is not None else self._plan_id
        return self

    def logg_token(self, nr_of_tokens: int) -> int:
        # add tokens to token usage sum
        if nr_of_tokens <= 0:
            return self._usage.tokens_used
        self._ensure_today()
        if not self.check_for_tokens_available(nr_of_tokens):
            # Still record nothing if not available
            return self._usage.tokens_used
        self._usage.tokens_used += nr_of_tokens
        return self._usage.tokens_used

    def logg_runtime(self, runtime: int) -> int:
        # add seconds to runtime usage sum
        if runtime <= 0:
            return self._usage.runtime_seconds_used
        self._ensure_today()
        if not self.check_for_runtime_available(runtime):
            # Still record nothing if not available
            return self._usage.runtime_seconds_used
        self._usage.runtime_seconds_used += runtime
        return self._usage.runtime_seconds_used

    def check_for_tokens_available(self, nr_of_tokens: int) -> bool:
        self._ensure_today()
        info = _plan_info(self._plan_id)
        max_tokens = info["max_tokens"]
        if max_tokens is None:  # unlimited
            return True
        # ensure we don't exceed today's quota
        return (self._usage.tokens_used + max(nr_of_tokens, 0)) <= max_tokens

    def check_for_runtime_available(self, runtime: int) -> bool:
        self._ensure_today()
        info = _plan_info(self._plan_id)
        max_runtime = info["max_runtime_seconds"]
        if max_runtime is None:  # unlimited
            return True
        return (self._usage.runtime_seconds_used + max(runtime, 0)) <= max_runtime

    def get_user_accounting_plan(self) -> dict:
        # implement in json mapping as per docstring
        # 0 -> default (testuser) max 0 tokens and 30min runtime
        # 1 -> enterprise user infinity tokens and runtime
        return _plan_info(self._plan_id)

    def save(self, main_db: "ArkanaMainDB") -> None:
        """Persist (upsert) today's accounting record and plan to the DB.

        Writes into table `user_runtime_usage_accounting` using the compound
        primary key (user_id, date, service, pay_model). If a record already
        exists for today, the plan is updated and the usage counters are
        updated to the max of existing and in-memory values.

        Parameters:
            main_db: ArkanaMainDB instance used to execute the SQL.
        """
        # Local import to avoid hard dependency at module import time
        try:
            from src.arkana_mdd_db.main_db import ArkanaMainDB  # type: ignore
        except Exception:  # pragma: no cover - import only for typing at runtime
            ArkanaMainDB = object  # type: ignore

        if not isinstance(main_db, ArkanaMainDB):  # type: ignore[arg-type]
            raise TypeError("main_db must be an instance of ArkanaMainDB")

        self._ensure_today()
        # service in DB is CHAR(3); normalize to 3 chars to be safe
        service3 = (self.service or "ark").lower()[:3]

        sql = (
            """
            INSERT INTO user_runtime_usage_accounting
                (user_id, `date`, service, used_time, used_tokens, pay_model)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pay_model = VALUES(pay_model),
                used_time = GREATEST(used_time, VALUES(used_time)),
                used_tokens = GREATEST(used_tokens, VALUES(used_tokens))
            """
        )
        params = (
            self.user_id,
            self._usage.day,
            service3,
            int(self._usage.runtime_seconds_used),
            int(self._usage.tokens_used),
            int(self._plan_id),
        )

        with main_db.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                connection.commit()
            finally:
                cursor.close()


