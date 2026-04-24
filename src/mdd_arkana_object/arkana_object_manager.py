from src.mdd_arkana_object.ark_obj_interface import Arkana_Object_Interface
from src.mdd_arkana_object.ark_notes import ArkanaNotes
from src.mdd_arkana_object.ark_report import ArkanaReport
from src.mdd_arkana_object.db_connection import ArkanaObjectDBConnection

from src.arkana_mdd_db.config import get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB
from src.arkana_auth.user_object import Arkana_User

class ArkanaObjectManager():

    def __init__(self, user:Arkana_User):
        self.user:Arkana_User = user

    def get_object(self, arkana_id:int)->Arkana_Object_Interface:
        d_object = self.__select_object(arkana_id)
        if not d_object:
            raise ValueError(f"Arkana object not found for id={arkana_id}")

        ark_type = str(d_object.get("arkana_type", "")).lower()
        cls_map = {
            "board": ArkanaReport,
            "report": ArkanaReport,
            "ark_notes": ArkanaNotes,
            "notes": ArkanaNotes,
        }
        obj_cls = cls_map.get(ark_type, Arkana_Object_Interface)
        # Pass fields as kwargs; interface will pick relevant ones
        if not self.user.check_user_group_allowed(d_object.get("auth_group", 0)):
            raise OSError("Arkana object not allowed")
        db_connection = self.__resolve_object_db_connection(d_object)
        d_object["db_connection"] = db_connection
        d_object["user_object"] = self.user
        if d_object.get("modeling_db", d_object.get("moddeling_db", 0)) not in (None, 0):
            runtime_connection, runtime_cursor = db_connection.open_cursor()
            d_object["db_runtime_connection"] = runtime_connection
            d_object["db_cursor"] = runtime_cursor
        return obj_cls(**d_object)
        
        

    
    def get_classes(self) -> dict[str, str]:
        """
        Return all possible Arkana object types as a mapping {type_key: description}.

        Reads from the `arkana_type` table. If the table is missing or an error
        occurs, returns an empty dict.
        """
        config = get_main_db_config()
        db = ArkanaMainDB(config)

        try:
            with db.connect() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "SELECT type_key, type_description FROM arkana_type ORDER BY type_key"
                    )
                    rows = cursor.fetchall() or []
                finally:
                    cursor.close()
        except Exception:
            # Graceful fallback if table doesn't exist yet
            return {}

        result: dict[str, str] = {}
        for row in rows:
            key = str(row[0]) if row and row[0] is not None else None
            if not key:
                continue
            desc = str(row[1]) if len(row) > 1 and row[1] is not None else ""
            result[key] = desc
        return result

    def __select_object(self, arkana_id:int)->dict:
        # Connect to main Arkana DB using .env configuration and fetch object row
        config = get_main_db_config()
        db = ArkanaMainDB(config)

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
                row = db._fetchone(query, (arkana_id,))
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

    def __resolve_object_db_connection(self, d_object: dict) -> ArkanaObjectDBConnection:
        modeling_db = d_object.get("modeling_db", d_object.get("moddeling_db", 0)) or 0
        try:
            modeling_db = int(modeling_db)
        except (TypeError, ValueError):
            modeling_db = 0

        config = get_main_db_config()
        db = ArkanaMainDB(config)

        if modeling_db == 0:
            return ArkanaObjectDBConnection(
                main_db=db,
                database=config.database,
                is_default=True,
            )

        runtime_access = self.user.resolve_db_runtime_access(modeling_db)
        db_record = runtime_access["db_record"]
        return ArkanaObjectDBConnection(
            main_db=db,
            database=db_record.schema.db_name,
            connection_record=db_record.connection,
            credential_db_id=db_record.schema.db_id,
            user_name=runtime_access["user_name"],
            password=runtime_access.get("password"),
            arkana_user_id=runtime_access["arkana_user_id"],
            is_default=False,
        )
        
    
