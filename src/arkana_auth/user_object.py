from __future__ import annotations

from dataclasses import dataclass

from src.arkana_auth.arkana_usage_accounting import ArkanaUsageAccounting
from src.arkana_mdd_db.main_db import ArkanaMainDB, AuthUser, DBWithConnection, PersonalUserRecord


@dataclass(frozen=True)
class ArkanaUser:
    main_db: ArkanaMainDB
    auth: AuthUser

    def _has_supabase_user(self) -> bool:
        return bool(self.auth.supabase_user_id)

    @property
    def user_id(self) -> str:
        return self.auth.user_id

    @property
    def user_name(self) -> str:
        return self.auth.user_name

    @property
    def user_role(self) -> str:
        return self.auth.user_role

    @property
    def user_storage_db_id(self) -> int | None:
        return self.auth.user_storage_db_id

    def is_admin(self) -> bool:
        if not self._has_supabase_user():
            return True
        return self.user_role in {"root", "admin"}

    def check_user_group_allowed(self, group_id: int) -> bool:
        if not self._has_supabase_user():
            return True
        return self.main_db.user_can_access_group(self.auth, group_id)

    def check_user_permissions(self, user_role: str) -> bool:
        if not self._has_supabase_user():
            return True
        if self.user_role == "root":
            return True
        role_order = {"viewer": 0, "editor": 1, "admin": 2, "root": 3}
        return role_order.get(self.user_role, -1) >= role_order.get(user_role, -1)

    def check_user_has_private_connection(self, db_id: int) -> bool:
        return self.get_users_private_connection(db_id) is not None

    def get_users_private_connection(self, db_id: int) -> PersonalUserRecord | None:
        return self.main_db.get_personal_user_for_arkana_user(db_id, self.user_id)

    @staticmethod
    def build_db_credential_service_name(db_id: int) -> str:
        return f"arkana-db:{db_id}"

    def can_access_db(self, db_id: int) -> bool:
        if not self._has_supabase_user():
            return True
        return self.main_db.user_can_access_db(self.auth, db_id)

    def get_private_db_user(self, db_id: int) -> PersonalUserRecord | None:
        if not self.can_access_db(db_id):
            return None
        return self.get_users_private_connection(db_id)

    def create_private_db_user(self, db_id: int, arkana_user_id: str, db_user_name: str) -> PersonalUserRecord:
        if not self.can_access_db(db_id):
            raise PermissionError("Access denied")
        if not self.is_admin() and arkana_user_id != self.user_id:
            raise PermissionError("Only admins may assign private db users to other users")
        return self.main_db.create_personal_user(
            {"db_id": db_id, "arkana_user_id": arkana_user_id, "db_user_name": db_user_name}
        )

    def resolve_private_db_user_for_password(self, db_id: int, db_user_name: str) -> PersonalUserRecord | None:
        if not self.can_access_db(db_id):
            raise PermissionError("Access denied")
        personal_user = self.main_db.find_personal_user(str(db_id), self.user_name, db_user_name)
        if self.is_admin():
            return personal_user
        if personal_user is None or personal_user.arkana_user_id != self.user_id:
            raise PermissionError("Only own db user password may be changed")
        return personal_user

    def set_private_db_password(self, db_id: int, db_user_name: str, password: str) -> None:
        personal_user = self.resolve_private_db_user_for_password(db_id, db_user_name)
        self.main_db.set_db_user_password(
            db_id=db_id,
            db_user_name=db_user_name,
            password=password,
            arkana_user_id=personal_user.arkana_user_id if personal_user else None,
        )

    def get_runtime_db_password(
        self,
        *,
        db_id: int,
        db_user_name: str,
        personal_user: PersonalUserRecord | None,
        group_id: int,
    ) -> str | None:
        return self.main_db.get_db_user_password(
            db_id=db_id,
            db_user_name=db_user_name,
            arkana_user_id=personal_user.arkana_user_id if personal_user else None,
        )

    def resolve_db_runtime_access(self, db_id: int) -> dict[str, object]:
        if not self.can_access_db(db_id):
            raise PermissionError("Access denied")

        db_record = self.main_db.get_db_with_connection(db_id)
        if db_record is None:
            raise ValueError(f"Unknown db_id: {db_id}")

        personal_user = self.get_users_private_connection(db_id)
        if personal_user is not None:
            return {
                "db_record": db_record,
                "user_name": personal_user.db_user_name,
                "arkana_user_id": personal_user.arkana_user_id,
                "password": self.get_runtime_db_password(
                    db_id=db_id,
                    db_user_name=personal_user.db_user_name,
                    personal_user=personal_user,
                    group_id=db_record.schema.user_group,
                ),
                "is_private": True,
            }

        return {
            "db_record": db_record,
            "user_name": db_record.connection.default_user,
            "arkana_user_id": None,
            "password": self.get_runtime_db_password(
                db_id=db_id,
                db_user_name=str(db_record.connection.default_user or ""),
                personal_user=None,
                group_id=db_record.schema.user_group,
            ),
            "is_private": False,
        }

    def get_accounting_obj(self):
        return ArkanaUsageAccounting(self.user_id, main_db=self.main_db)


Arkana_User = ArkanaUser

__all__ = ["ArkanaUser", "Arkana_User"]
