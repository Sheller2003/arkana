USE arkana;

DROP TRIGGER IF EXISTS trg_db_schema_validate_group_insert;
DROP TRIGGER IF EXISTS trg_db_schema_validate_group_update;

ALTER TABLE arkana_report_header DROP FOREIGN KEY fk_arkana_report_header_group;
ALTER TABLE arkana_dashboard_header DROP FOREIGN KEY fk_arkana_dashboard_header_group;
ALTER TABLE arkana_object DROP FOREIGN KEY fk_arkana_object_auth_group;
ALTER TABLE db_schema DROP FOREIGN KEY fk_db_schema_user_group;
ALTER TABLE db_connection DROP FOREIGN KEY fk_db_connection_user_group;

DROP TABLE IF EXISTS user_group_user;
DROP TABLE IF EXISTS user_group;
