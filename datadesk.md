
# data projector

projects data from multible tables and databases to the target
contains:
- DB_list = [db_ids]
- tables = tables
- user_group:str 
- admin_group:str 
- owner:str
- data_cache: Enum:Data_chache(server, real_time_db )
- allowed_tables (with regex) default all
- store_commands:dict[store_key:command]
- final_store:bool if yes don't allow to change the store after initial load
- check_table_is_allowed(table:str, db_id:int)
- load()
  - loads db_objects()
- get_table_object(db_id, table_id)
  - db_id is optional if == null search in all DBs
- get_db_object(db_id)
- get_primary_keys()
- store_set(key:str, command:str)
  - stores the data of the command
- store_reload(key:str, command:str(optional))
  - reloads the data of the regarding key
  - if no command given reuse the old one
- 


# data_model
__init__(Data_Projector, model_frame)
load()
- loads reqired fields by projector
- 

# data_desk

gets created by a data_projector. Is a dynamic model witch stores data
fields:list[{field_key:str, field_value:str, field_}]
__init__(Data_Projector)

add_field(field_key:str, field_definition)
delete_field(field_key)
update_field(field_key:str, field_definition)
save_as_model(frame)
save_as_model_frame()
save()-> returns desk_id and store the desk in tmp 
to_json()-> returns all fields and values as json

sql_select_handler
__init__(sql_select_command:str)
- get_datatables()->datatables
- set_datatable_main(table:str)
- get_database()->str
- set_database(db_key:str)

# frame
## frame factoring
- load_frame_by_id(id:int)->frame_object
- create_frame(projector)->frame_creation_object
- save_frame(frame:frame_creation_object)


frame_object
- check_fields_are_allowed(model_object)
- create_initial_model()->model_object
- get_refs()
- get_super_frame()
- get_projector()
- get_field(field_key)->dict
- get_select_commands()->list[str]
- get_update_commands()->list[str]
- get_deletion_commands()
- set_frame_status(status:str)
- get_frame_status()
- check_auth(user_id:str)
-

frame_creation_object
- add_field(field_key:str, field_definition, )
