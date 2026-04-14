# Arkana API

Base URL:
- `http://<host>:8000`

## Auth

Bevorzugt:
- `Authorization: Bearer <supabase_access_token>`

Fallback:
- HTTP Basic Auth

Beispiel Bearer:
```http
Authorization: Bearer eyJ...
```

Beispiel Basic Auth:
```http
Authorization: Basic base64(username:password)
```

Hinweise:
- Supabase-Token funktionieren auf allen Endpoints.
- Die meisten Endpoints akzeptieren `?help=true`.

## Standard-Objekte

### Report

Felder:
- `arkana_id: int`
- `arkana_type: "report"`
- `auth_group: int | null`
- `object_key: string | null`
- `description: string | null`
- `modeling_db: int`
- `arkana_group: int | null`
- `cells: ReportCell[]`

Beispiel:
```json
{
  "arkana_id": 8,
  "arkana_type": "report",
  "auth_group": 0,
  "object_key": "demo-report",
  "description": "Example report",
  "modeling_db": 0,
  "arkana_group": 0,
  "cells": []
}
```

### ReportCell

Felder:
- `cell_id: int`
- `cell_key: string | null`
- `cell_type: string`
- `taggs: string[] | string | null`
- `content: string | object | null`
- `cells: ReportCell[]` optional in verschachtelter Ausgabe

Wichtige `cell_type` Werte:
- `text`
- `md`
- `html`
- `py_code`
- `py_result`
- `r_code`
- `r_result`
- `file`
- `file_csv`
- `file_json`
- `file_jpg`
- `rdata`

Beispiel:
```json
{
  "cell_id": 3,
  "cell_key": "py_code",
  "cell_type": "py_code",
  "taggs": ["demo", "python"],
  "content": "print('hello')",
  "cells": []
}
```

### ReportCreateRequest

Felder:
- `public: bool`
- `auth_group: int`
- `object_key: string | null`
- `description: string | null`
- `arkana_group: int | null`
- `cells: ReportCellRequest[]`

Beispiel:
```json
{
  "public": true,
  "auth_group": 0,
  "object_key": "sales-q2",
  "description": "Quarterly report",
  "arkana_group": 0,
  "cells": []
}
```

### ReportCellRequest

Felder:
- `cell_key: string | null`
- `cell_type: string | null`
- `taggs: string[] | string | null`
- `content: string | null`

Beispiel:
```json
{
  "cell_key": "r_code",
  "cell_type": "r_code",
  "taggs": ["stats"],
  "content": "summary(cars)"
}
```

## Health

### `GET /health`

Beschreibung:
- Liefert den API-Status.

Response:
```json
{
  "status": "ok"
}
```

## User

### `GET /user/login_check`

Beschreibung:
- Prüft Authentifizierung und liefert die aufgelöste User-Identität.

Response-Felder:
- `can_login: bool`
- `user_id: string`
- `user_name: string`
- `user_role: string`

Beispiel:
```json
{
  "can_login": true,
  "user_id": "d30ab318-15da-4bf7-8331-aa4e24098f1b",
  "user_name": "niklasf1234@yahoo.com",
  "user_role": "viewer"
}
```

### `GET /user/usage`

Response-Felder:
- `user_id: string`
- `service: string`
- weitere Usage-Felder aus dem Accounting

### `GET /user/max_usage`

Response-Felder:
- `user_id: string`
- `service: string`
- `runtime_seconds_max: int`
- `tokens_max: int`

### `GET /user/usage/{user_id}`

Beschreibung:
- Root-only.

## Groups

### `POST /groups/create_group`

Request:
```json
{
  "group_name": "analytics-team"
}
```

Response:
```json
{
  "group_id": 123
}
```

### `GET /groups/{group_id}/members`

Response:
```json
{
  "group_id": 123,
  "members": [
    "user-uuid-1",
    "user-uuid-2"
  ]
}
```

### `DELETE /groups/{group_id}`

Response:
```json
{
  "status": "ok",
  "group_id": 123
}
```

### `POST /groups/{group_id}/assign`

Request:
```json
{
  "user_id": "d30ab318-15da-4bf7-8331-aa4e24098f1b"
}
```

Response:
```json
{
  "status": "ok",
  "group_id": 123,
  "user_id": "d30ab318-15da-4bf7-8331-aa4e24098f1b"
}
```

## Reports

### `GET /report/{arkana_id}`

Beschreibung:
- Lädt den kompletten Report mit Top-Level-Zellen und Sub-Zellen.

Beispiel:
```json
{
  "arkana_id": 8,
  "arkana_type": "report",
  "auth_group": 0,
  "object_key": "demo-report",
  "description": "Example report",
  "arkana_group": 0,
  "cells": [
    {
      "cell_id": 1,
      "cell_key": "py_code",
      "cell_type": "py_code",
      "taggs": ["demo"],
      "content": "print('hello')",
      "cells": []
    }
  ]
}
```

### `POST /report`

Beschreibung:
- Erstellt einen Report.
- `public=true` erzeugt einen öffentlichen Report mit Gruppe `0`.
- `public=false` erzeugt eine neue Supabase-Gruppe.

Request:
```json
{
  "public": false,
  "object_key": "private-report",
  "description": "Private report",
  "cells": [
    {
      "cell_key": "py_code",
      "cell_type": "py_code",
      "taggs": ["demo"],
      "content": "print('hello')"
    }
  ]
}
```

Response:
```json
{
  "arkana_id": 8,
  "arkana_type": "report",
  "auth_group": 123,
  "object_key": "private-report",
  "description": "Private report",
  "arkana_group": 123,
  "cells": [
    {
      "cell_id": 1,
      "cell_key": "py_code",
      "cell_type": "py_code",
      "taggs": ["demo"],
      "content": "print('hello')",
      "cells": []
    }
  ]
}
```

### `DELETE /report/{arkana_id}`

Beschreibung:
- Löscht den Report, Sessions und Workspace.

Response:
```json
{
  "status": "deleted",
  "arkana_object_id": 8,
  "deleted_sessions": [],
  "deleted_workspaces": [
    "/app/arkana_spheres/workspaces/report_8"
  ]
}
```

### `POST /report/{arkana_id}/run`

Query:
- `save=true|false`

Response-Felder:
- `arkana_object_id: int`
- `save_result: bool`
- `results: object[]`

Beispiel:
```json
{
  "arkana_object_id": 8,
  "save_result": true,
  "results": [
    {
      "cell": 1,
      "results": [
        {
          "cell_id": 9,
          "cell_key": "py_code",
          "cell_type": "py_result",
          "content": "hello",
          "cells": []
        }
      ]
    }
  ]
}
```

### `GET /report/{arkana_id}/sessions`

Response-Felder:
- `arkana_object_id: int`
- `sessions: SessionInfo[]`

`SessionInfo`:
- `session_id: string`
- `container_name: string`
- `runtime_type: string`
- `language: string`
- `user_id: string`
- `arkana_object_id: string`
- `workspace_path: string`
- `created_at: string | null`
- `expires_at: string | null`
- `lifetime_seconds: int | null`

Beispiel:
```json
{
  "arkana_object_id": 8,
  "sessions": [
    {
      "session_id": "python-8-1234567890",
      "container_name": "arkana-python-python-8-1234567890",
      "runtime_type": "py",
      "language": "python",
      "user_id": "user-1",
      "arkana_object_id": "8",
      "workspace_path": "/app/arkana_spheres/workspaces/report_8",
      "created_at": "2026-04-15T08:00:00+00:00",
      "expires_at": "2026-04-15T08:30:00+00:00",
      "lifetime_seconds": 1800
    }
  ]
}
```

### `POST /report/{arkana_id}/sessions`

Beschreibung:
- Löscht und erzeugt die Sessions des aktuellen Users für den Report neu.

Response-Felder:
- `arkana_object_id: int`
- `previous_sessions: SessionInfo[]`
- `restarted_sessions: SessionInfo[]`
- `status: "restarted"`

## Report Uploads

### `POST /report/{arkana_id}/upload`

Content-Type:
- `multipart/form-data`

Form-Felder:
- `file`

Max:
- `10 MB`

Verhalten nach Dateiendung:
- `.csv` -> neue `file_csv`-Zelle, Datei wird gespeichert
- `.json` -> neue `file_json`-Zelle, Datei wird gespeichert
- `.rdata` / `.RData` -> neue `rdata`-Zelle, Datei wird gespeichert
- `.py` -> neue `py_code`-Zelle, Datei wird nicht gespeichert
- `.r` -> neue `r_code`-Zelle, Datei wird nicht gespeichert

Response-Felder:
- `status: "uploaded"`
- `arkana_object_id: int`
- `cell: ReportCell`
- `file_name: string`
- `file_size: int`

Beispiel Response für `.csv`:
```json
{
  "status": "uploaded",
  "arkana_object_id": 8,
  "cell": {
    "cell_id": 10,
    "cell_key": "cell_10",
    "cell_type": "file_csv",
    "taggs": null,
    "content": "http://127.0.0.1:8000/report/8/files/data.csv",
    "cells": []
  },
  "file_name": "data.csv",
  "file_size": 2048
}
```

Beispiel Response für `.py`:
```json
{
  "status": "uploaded",
  "arkana_object_id": 8,
  "cell": {
    "cell_id": 11,
    "cell_key": "cell_11",
    "cell_type": "py_code",
    "taggs": null,
    "content": "print('hello')",
    "cells": []
  },
  "file_name": "script.py",
  "file_size": 25
}
```

## Report Cells

### `GET /report/{arkana_id}/cell/{cell_identifier}`

Beschreibung:
- Liefert eine Zelle als JSON.

### `GET /report/{arkana_id}/cell?cell_id=<id>`

Beschreibung:
- Liefert eine Zelle über die exakte interne `cell_id`.

### `GET /report/{arkana_id}/cell/get?cell_id=<id>`

Beschreibung:
- Liefert den Zellinhalt direkt.
- File-Zellen erzeugen Redirects.
- `html` liefert HTML.
- `md` / `text` liefern Plaintext.

### `GET /report/{arkana_id}/cell/{cell_identifier}/get`

Beschreibung:
- Wie oben, aber Lookup über `cell_key` oder sichtbaren Index.

### `POST /report/{arkana_id}/cell/`

Query:
- `index` optional

Request:
```json
{
  "cell_key": "note_1",
  "cell_type": "text",
  "taggs": ["intro"],
  "content": "Hello"
}
```

Response:
```json
{
  "cell_id": 12,
  "cell_key": "note_1",
  "cell_type": "text",
  "taggs": ["intro"],
  "content": "Hello",
  "cells": []
}
```

### `PUT /report/{arkana_id}/cell/{cell_identifier}`

Beschreibung:
- Aktualisiert eine Zelle.
- Wenn `cell_type="file"` gesetzt wird und `content` auf `.csv`, `.json` oder `.jpg` zeigt, wird automatisch auf den spezifischen File-Typ umgestellt.

Request:
```json
{
  "cell_type": "file",
  "content": "result.json",
  "taggs": ["export"]
}
```

Beispiel Response:
```json
{
  "cell_id": 12,
  "cell_key": "note_1",
  "cell_type": "file_json",
  "taggs": ["export"],
  "content": "http://127.0.0.1:8000/report/8/files/result.json",
  "cells": []
}
```

### `DELETE /report/{arkana_id}/cell/{cell_identifier}`

Beschreibung:
- Löscht eine Zelle.
- Wenn es eine dateibasierte Zelle ist, wird die Datei nur gelöscht, wenn keine andere Zelle im Report mehr auf dieselbe Datei zeigt.

Response:
```json
{
  "status": "deleted",
  "cell": {
    "cell_id": 10,
    "cell_key": "cell_10",
    "cell_type": "file_csv",
    "content": "http://127.0.0.1:8000/report/8/files/data.csv",
    "cells": []
  }
}
```

### `GET /report/{arkana_id}/cell/{cell_identifier}/run`

Beschreibung:
- Führt eine Zelle aus, ohne Resultate zu persistieren.

### `POST /report/{arkana_id}/cell/{cell_identifier}/run`

Query:
- `save=true|false`

Beispiel Response:
```json
{
  "arkana_object_id": 8,
  "cell": "py_code",
  "save_result": true,
  "results": [
    {
      "cell_id": 13,
      "cell_key": "py_code",
      "cell_type": "py_result",
      "content": "hello",
      "cells": []
    }
  ]
}
```

### `POST /report/{arkana_id}/cell/{cell_identifier}/upload`

Content-Type:
- `multipart/form-data`

Voraussetzungen:
- Zielzelle muss bereits eine File-Zelle sein

Erlaubte Dateien:
- `.csv`
- `.json`

Response-Felder:
- `status`
- `arkana_object_id`
- `cell`
- `file_name`
- `file_size`

Beispiel Response:
```json
{
  "status": "uploaded",
  "arkana_object_id": 8,
  "cell": {
    "cell_id": 10,
    "cell_key": "cell_10",
    "cell_type": "file_csv",
    "content": "http://127.0.0.1:8000/report/8/files/upload.csv",
    "cells": []
  },
  "file_name": "upload.csv",
  "file_size": 1024
}
```

## Report Files

### `GET /report/{arkana_id}/files`

Response-Felder:
- `arkana_object_id: int`
- `files: FileEntry[]`

`FileEntry`:
- `file_name: string`
- `file_url: string`

Beispiel:
```json
{
  "arkana_object_id": 8,
  "files": [
    {
      "file_name": "data.csv",
      "file_url": "http://127.0.0.1:8000/report/8/files/data.csv"
    }
  ]
}
```

### `GET /report/{arkana_id}/files/{file_name}`

Beschreibung:
- Streamt die Datei direkt.

## Frames

### `POST /frames/execute`

Request-Felder:
- `frame: object`
- `input_parameters: object`
- `referenced_frames: object`

Beispiel:
```json
{
  "frame": {
    "frame_id": 1
  },
  "input_parameters": {
    "limit": 10
  },
  "referenced_frames": {}
}
```

## Database

### `GET /db/{db_id}/`

Beschreibung:
- Liefert DB-Schema-Metadaten.

### `GET /db/{db_id}/tables`

Response:
```json
{
  "db_id": 1,
  "tables": [
    {
      "table_name": "customers",
      "table_schema": "app"
    }
  ]
}
```

### `POST /db/{db_id}/key_models`

Request:
```json
{
  "start_tables": ["customers"],
  "max_distance": 2,
  "include_all": false
}
```

### `POST /db/`

Request-Felder:
- `user_group: int`
- `owner: string`
- `url: string | null`
- `ip: string | null`
- `db_name: string`
- `db_description: string | null`
- `db_con_id: int`

Beispiel:
```json
{
  "user_group": 0,
  "owner": "user-1",
  "db_name": "analytics",
  "db_description": "Analytics DB",
  "db_con_id": 2
}
```

### `POST /db_connection/`

Request-Felder:
- `user_group: int`
- `owner: string`
- `url: string | null`
- `ip: string | null`
- `server_description: string | null`
- `default_user: string | null`
- `admin_user: string | null`
- `db_type: string`

### `GET /db_connection/personal_user/?db_id=<id>`

Response:
```json
{
  "db_id": 1,
  "personal_user": {
    "db_id": 1,
    "arkana_user_id": "user-1",
    "db_user_name": "analytics_user"
  }
}
```

### `POST /db_connection/personal_user/`

Request:
```json
{
  "db_id": 1,
  "arkana_user_id": "user-1",
  "db_user_name": "analytics_user"
}
```

### `POST /db_connection/user/{user_name}/password`

Request:
```json
{
  "db_id": 1,
  "password": "secret"
}
```

Response:
```json
{
  "status": "ok",
  "keyring_service": "arkana/db_credentials"
}
```
