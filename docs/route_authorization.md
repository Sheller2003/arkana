# Route Authorization Objects

This document describes the concrete API authorization objects currently enforced by the route layer.

Implementation source:
- `src/arkana_api_service/route_auth.py`

Enforcement model:
- every main route group has its own `auth_class`
- every endpoint has its own `auth_key`
- a request is allowed only if the user has both:
  - the required `auth_class`
  - the required `auth_key` with at least the required value

Runtime check:
- `require_route_auth(current_user, route_name)`

## Auth Classes

| Main route | Auth class | Purpose |
| --- | --- | --- |
| `health` | `api.health` | access to health/status endpoints |
| `user` | `api.user` | access to user/account endpoints |
| `db` | `api.db` | access to database metadata and credential endpoints |
| `frames` | `api.frames` | access to frame execution endpoints |
| `notes` | `api.notes` | access to notes and temporary notes endpoints |
| `groups` | `api.groups` | access to Supabase group management endpoints |
| `report` | `api.report` | access to report read/write/run endpoints |

## Endpoint Auth Objects

### Health

| Route name | Endpoint | Auth class | Auth object |
| --- | --- | --- | --- |
| `health` | `GET /health` | `api.health` | `api.health.read` |

### User

| Route name | Endpoint | Auth class | Auth object |
| --- | --- | --- | --- |
| `get_user_login_check` | `GET /user/login_check` | `api.user` | `api.user.login_check.read` |
| `get_user_usage` | `GET /user/usage` | `api.user` | `api.user.usage.read` |
| `get_user_max_usage` | `GET /user/max_usage` | `api.user` | `api.user.max_usage.read` |
| `get_specific_user_usage` | `GET /user/{user_id}/usage` | `api.user` | `api.user.usage.user.read` |
| `reload_specific_user` | `POST /user/{user_id}/reload` | `api.user` | `api.user.reload.user.write` |
| `reload_current_user` | `POST /user/reload` | `api.user` | `api.user.reload.self.write` |

### DB

| Route name | Endpoint | Auth class | Auth object |
| --- | --- | --- | --- |
| `get_db` | `GET /db/{db_id}/` | `api.db` | `api.db.read` |
| `get_db_tables` | `GET /db/{db_id}/tables` | `api.db` | `api.db.tables.read` |
| `get_database_table` | `GET /database/{db_id}/table/{table_key}` | `api.db` | `api.db.table.read` |
| `get_key_models` | `POST /db/{db_id}/key_models` | `api.db` | `api.db.key_models.read` |
| `create_db` | `POST /db/` | `api.db` | `api.db.create` |
| `create_db_connection` | `POST /db_connection/` | `api.db` | `api.db.connection.create` |
| `get_personal_user` | `GET /db_connection/personal_user/` | `api.db` | `api.db.personal_user.read` |
| `create_personal_user` | `POST /db_connection/personal_user/` | `api.db` | `api.db.personal_user.create` |
| `set_db_user_password` | `POST /db_connection/user/{user_name}/password` | `api.db` | `api.db.user_password.write` |

### Frames

| Route name | Endpoint | Auth class | Auth object |
| --- | --- | --- | --- |
| `execute_frame` | `POST /frames/execute` | `api.frames` | `api.frames.execute` |

### Notes

| Route name | Endpoint | Auth class | Auth object |
| --- | --- | --- | --- |
| `create_notes` | `POST /notes` | `api.notes` | `api.notes.create` |
| `get_notes` | `GET /notes/{object_id}/` | `api.notes` | `api.notes.read` |
| `get_tmp_notes` | `GET /notes/tmp_{buffer_id}/` | `api.notes` | `api.notes.tmp.read` |
| `save_notes` | `POST /notes/{note_id}/save` | `api.notes` | `api.notes.save` |
| `create_notes_chapter` | `POST /notes/{node_id}/chapter` | `api.notes` | `api.notes.chapter.create` |
| `get_note_chapter` | `GET /notes/{node_id}/chapter/{chapter_identifier}` | `api.notes` | `api.notes.chapter.read` |
| `get_note_chapter_files` | `GET /notes/{node_id}/chapter/{chapter_identifier}/files` | `api.notes` | `api.notes.chapter.files.read` |
| `upload_note_chapter_file` | `POST /notes/{node_id}/chapter/{chapter_identifier}/file` | `api.notes` | `api.notes.chapter.file.upload` |

### Groups

| Route name | Endpoint | Auth class | Auth object |
| --- | --- | --- | --- |
| `create_group` | `POST /groups/create_group` | `api.groups` | `api.groups.create` |
| `get_group_members` | `GET /groups/{group_id}/members` | `api.groups` | `api.groups.members.read` |
| `delete_group` | `DELETE /groups/{group_id}` | `api.groups` | `api.groups.delete` |
| `assign_group` | `POST /groups/{group_id}/assign` | `api.groups` | `api.groups.assign` |

### Report

| Route name | Endpoint | Auth class | Auth object |
| --- | --- | --- | --- |
| `get_report` | `GET /report/{arkana_id}` | `api.report` | `api.report.read` |
| `create_report` | `POST /report` | `api.report` | `api.report.create` |
| `get_report_cell` | `GET /report/{arkana_id}/cell/{cell_identifier}` | `api.report` | `api.report.cell.read` |
| `get_report_cell_by_id` | `GET /report/{arkana_id}/cell` and `GET /report/{arkana_id}/cell/` | `api.report` | `api.report.cell_by_id.read` |
| `get_report_cell_content_by_id` | `GET /report/{arkana_id}/cell/get` | `api.report` | `api.report.cell_content_by_id.read` |
| `get_report_cell_content` | `GET /report/{arkana_id}/cell/{cell_identifier}/get` | `api.report` | `api.report.cell_content.read` |
| `get_report_files` | `GET /report/{arkana_id}/files` | `api.report` | `api.report.files.read` |
| `get_report_file` | `GET /report/{arkana_id}/files/{file_name}` | `api.report` | `api.report.file.read` |
| `get_report_sessions` | `GET /report/{arkana_id}/sessions` | `api.report` | `api.report.sessions.read` |
| `restart_report_sessions` | `POST /report/{arkana_id}/sessions` | `api.report` | `api.report.sessions.restart` |
| `update_report_cell` | `PUT /report/{arkana_id}/cell/{cell_identifier}` | `api.report` | `api.report.cell.update` |
| `delete_report_cell` | `DELETE /report/{arkana_id}/cell/{cell_identifier}` | `api.report` | `api.report.cell.delete` |
| `upload_report_cell_file` | `POST /report/{arkana_id}/cell/{cell_identifier}/upload` | `api.report` | `api.report.cell.upload` |
| `upload_report_file` | `POST /report/{arkana_id}/upload` | `api.report` | `api.report.file.upload` |
| `delete_report` | `DELETE /report/{arkana_id}` | `api.report` | `api.report.delete` |
| `create_report_cell` | `POST /report/{arkana_id}/cell/` | `api.report` | `api.report.cell.create` |
| `run_report_cells` | `POST /report/{arkana_id}/run` | `api.report` | `api.report.run` |
| `get_run_report_cell` | `GET /report/{arkana_id}/cell/{cell_identifier}/run` | `api.report` | `api.report.cell.run.read` |
| `post_run_report_cell` | `POST /report/{arkana_id}/cell/{cell_identifier}/run` | `api.report` | `api.report.cell.run` |

## Naming Convention

Current naming pattern:
- auth classes: `api.<main-route>`
- endpoint auth objects: `api.<main-route>.<action>`

Examples:
- `api.user`
- `api.user.usage.read`
- `api.db.connection.create`
- `api.report.cell.run`

## Notes

- Route-level authorization is additive to existing business checks such as:
  - group membership
  - object ownership
  - admin/root role checks
  - report/object visibility checks
- Local non-Supabase users currently allow `has_effective_auth(...)` and `has_auth_class_assignment(...)` by default in `user_object.py`.
- Supabase-backed users resolve these checks through the effective authorization payload loaded from Supabase.
