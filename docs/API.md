# Arkana API

Base URLs:
- `http://<host>:8000`
- optional server-side via Traefik: `https://arkanan8n.cloud`

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
- Bearer-Tokens aus Supabase funktionieren auf allen Endpoints.
- Basic Auth bleibt als Fallback aktiv.
- Viele Endpoints akzeptieren `?help=true` und hängen dann Metadaten an die JSON-Response an.
- CORS ist serverseitig in FastAPI aktiv. Standardmäßig sind alle Origins erlaubt, einschränkbar über `ARKANA_CORS_ALLOW_ORIGINS`.

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
- `cells: ReportCell[]`

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
- `public: bool = true`
- `auth_group: int = 0`
- `object_key: string | null`
- `description: string | null`
- `arkana_group: int | null`
- `cells: ReportCellRequest[]`

Regeln:
- `public=true` setzt `auth_group=0` und `arkana_group=0`.
- `public=false` ist nur mit Supabase-Login erlaubt und erzeugt automatisch eine neue Supabase-Objektgruppe mit `group_name=<arkana_id>`.

Beispiel:
```json
{
  "public": true,
  "object_key": "sales-q2",
  "description": "Quarterly report",
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

### Upload-Regeln

`POST /report/{arkana_id}/upload`
- max. `10 MB`
- Feldname: `file`
- `.csv` und `.json`: speichern Datei im Workspace und erzeugen neue File-Zelle
- `.RData` / `.rdata`: speichern Datei im Workspace und erzeugen neue `rdata`-Zelle
- `.py`: erzeugt immer eine neue `py_code`-Zelle, Datei wird nicht gespeichert
- `.r`: erzeugt immer eine neue `r_code`-Zelle, Datei wird nicht gespeichert

`POST /report/{arkana_id}/cell/{cell_identifier}/upload`
- max. `10 MB`
- Feldname: `file`
- nur für bestehende File-Zellen
- erlaubt nur `.csv` und `.json`
- ersetzt die Dateireferenz der Zielzelle

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

Beschreibung:
- Liefert die heutige Usage des aktuellen Users.

Response-Felder:
- `user_id: string`
- `service: string`
- weitere Usage-Zähler, abhängig vom Accounting-Backend

Beispiel:
```json
{
  "user_id": "d30ab318-15da-4bf7-8331-aa4e24098f1b",
  "service": "arkana",
  "runtime_seconds": 124,
  "tokens": 8912
}
```

### `GET /user/max_usage`

Beschreibung:
- Liefert das tägliche Limit.
- Root-User erhalten `-1`.

Beispiel:
```json
{
  "user_id": "d30ab318-15da-4bf7-8331-aa4e24098f1b",
  "service": "arkana",
  "runtime_seconds_max": 3600,
  "tokens_max": 100000
}
```

### `GET /user/{user_id}/usage`

Beschreibung:
- Admin/root only.
- Liefert heutige Usage eines beliebigen Users.

### `POST /user/{user_id}/reload`

Beschreibung:
- Admin/root only.
- Invalidiert den kompletten User-Buffer fuer den angegebenen User.

### `POST /user/reload`

Beschreibung:
- Invalidiert den kompletten Buffer des aktuell authentifizierten Users.

## Groups

Wichtig:
- Diese Endpunkte verlangen einen echten Supabase-Login.

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

## Notes

### `POST /notes`

Beschreibung:
- Erzeugt ein neues gepuffertes `ark_notes` Objekt.
- Das Objekt wird noch nicht in der DB gespeichert.
- Buffer-Lebensdauer: 24 Stunden.

### `GET /notes/{object_id}/`

Beschreibung:
- Liefert ein persistiertes `ark_notes` Objekt mit allen Chapters.

### `GET /notes/tmp_{buffer_id}/`

Beschreibung:
- Liefert ein gepuffertes Notes-Objekt.
- Buffer-Lebensdauer: 24 Stunden.

### `POST /notes/{note_id}/save`

Beschreibung:
- Persistiert ein gepuffertes `tmp_<buffer_id>` Notes-Objekt in die DB.
- Danach besitzt das Objekt eine echte `arkana_id`.

### `POST /notes/{node_id}/chapter`

Beschreibung:
- Erstellt ein oder mehrere Chapters.
- `node_id=0` erzeugt bzw. speichert ein neues Notes-Objekt nur im Buffer.
- `node_id=tmp_<buffer_id>` aktualisiert ein gepuffertes Notes-Objekt.
- `node_id=<arkana_id>` aktualisiert ein persistiertes Notes-Objekt.

### `GET /notes/{node_id}/chapter/{chapter_identifier}`

Beschreibung:
- Liefert ein Chapter per numerischer `chapter_id` oder `chapter_key`.

### `GET /notes/{node_id}/chapter/{chapter_identifier}/files`

Beschreibung:
- Liefert die Dateiliste des Chapters.

### `POST /notes/{node_id}/chapter/{chapter_identifier}/file`

Beschreibung:
- Laedt eine Datei bis max. `10 MB` hoch und haengt sie an das Chapter an.

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
- Lädt den kompletten Report mit Zellen und Sub-Zellen.

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
  "cells": [
    {
      "cell_id": 1,
      "cell_key": "py_code",
      "cell_type": "py_code",
      "taggs": [],
      "content": "print('hello')",
      "cells": []
    }
  ]
}
```

### `POST /report`

Beschreibung:
- Erstellt einen Report.

Request:
```json
{
  "public": false,
  "object_key": "private-report",
  "description": "Only for a group",
  "cells": [
    {
      "cell_key": "py_code",
      "cell_type": "py_code",
      "content": "print('hello')"
    }
  ]
}
```

Response:
```json
{
  "arkana_id": 12,
  "arkana_type": "report",
  "auth_group": 321,
  "object_key": "private-report",
  "description": "Only for a group",
  "modeling_db": 0,
  "arkana_group": 321,
  "cells": [
    {
      "cell_id": 1,
      "cell_key": "py_code",
      "cell_type": "py_code",
      "taggs": null,
      "content": "print('hello')",
      "cells": []
    }
  ]
}
```

### `POST /report/{arkana_id}/cell/`

Beschreibung:
- Erstellt eine neue Top-Level-Zelle.
- optional mit `?index=...` für eine sichtbare Position.

Request:
```json
{
  "cell_key": "notes",
  "cell_type": "md",
  "taggs": ["intro"],
  "content": "# Hello"
}
```

Response:
```json
{
  "cell_id": 7,
  "cell_key": "notes",
  "cell_type": "md",
  "taggs": ["intro"],
  "content": "# Hello",
  "cells": []
}
```

### `PUT /report/{arkana_id}/cell/{cell_identifier}`

Beschreibung:
- Aktualisiert eine Zelle über sichtbaren Index oder `cell_key`.
- `cell_type` kann manuell gesetzt werden.
- Tags werden über `taggs` gesetzt oder überschrieben.

Request:
```json
{
  "cell_type": "file",
  "taggs": ["data"],
  "content": "customers.csv"
}
```

Response:
```json
{
  "cell_id": 10,
  "cell_key": "customers",
  "cell_type": "file_csv",
  "taggs": ["data"],
  "content": "http://72.61.87.45:8000/report/8/files/customers.csv",
  "cells": []
}
```

### `DELETE /report/{arkana_id}/cell/{cell_identifier}`

Beschreibung:
- Löscht die Zelle.
- Bei File-Zellen wird die Datei nur gelöscht, wenn keine andere Zelle mehr darauf zeigt.

Response:
```json
{
  "status": "deleted",
  "cell": {
    "cell_id": 10,
    "cell_key": "customers",
    "cell_type": "file_csv",
    "taggs": ["data"],
    "content": "customers.csv"
  }
}
```

### `GET /report/{arkana_id}/cell/{cell_identifier}`

Beschreibung:
- Liefert eine Zelle als JSON.
- `cell_identifier` ist sichtbarer Top-Level-Index oder `cell_key`.
- alternativ: `?cell_id=<internal id>`

### `GET /report/{arkana_id}/cell`

Beschreibung:
- Liefert eine Zelle per exakter `cell_id`.

Beispiel:
```http
GET /report/8/cell?cell_id=10
```

### `GET /report/{arkana_id}/cell/get`

Beschreibung:
- Liefert Zellinhalt nach Typ:
- File-Zellen: Redirect
- `html`: HTML-Body
- `md` und `text`: Plain Text
- sonst JSON

### `GET /report/{arkana_id}/cell/{cell_identifier}/get`

Beschreibung:
- Wie oben, aber per sichtbarem Index oder `cell_key`.

## Files

### `GET /report/{arkana_id}/files`

Beschreibung:
- Listet exportierte Report-Dateien.
- aktuell werden nur `.csv`, `.txt` und `.png` ausgeliefert.

Response:
```json
{
  "arkana_object_id": 8,
  "files": [
    {
      "file_name": "sinus.png",
      "file_url": "http://72.61.87.45:8000/report/8/files/sinus.png"
    }
  ]
}
```

### `GET /report/{arkana_id}/files/{file_name}`

Beschreibung:
- Streamt eine Report-Datei.
- mit `?help=true` stattdessen JSON-Metadaten.

## Upload

### `POST /report/{arkana_id}/upload`

Request:
- `multipart/form-data`
- Feld: `file`

Beispiel `curl`:
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@customers.csv" \
  http://72.61.87.45:8000/report/8/upload
```

Beispiel Response für `.csv`:
```json
{
  "status": "uploaded",
  "arkana_object_id": 8,
  "cell": {
    "cell_id": 11,
    "cell_key": "customers",
    "cell_type": "file_csv",
    "taggs": null,
    "content": "http://72.61.87.45:8000/report/8/files/customers.csv",
    "cells": []
  },
  "file_name": "customers.csv",
  "file_size": 2048
}
```

Beispiel Response für `.py`:
```json
{
  "status": "uploaded",
  "arkana_object_id": 8,
  "cell": {
    "cell_id": 12,
    "cell_key": "py_code",
    "cell_type": "py_code",
    "taggs": null,
    "content": "print('hello')",
    "cells": []
  },
  "file_name": "script.py",
  "file_size": 84
}
```

### `POST /report/{arkana_id}/cell/{cell_identifier}/upload`

Beschreibung:
- Weist eine hochgeladene `.csv`- oder `.json`-Datei einer bestehenden File-Zelle zu.

Request:
- `multipart/form-data`
- Feld: `file`

Beispiel `curl`:
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@customers.json" \
  http://72.61.87.45:8000/report/8/cell/customers/upload
```

## Sessions

### `GET /report/{arkana_id}/sessions`

Beschreibung:
- Listet alle Runtime-Sessions des aktuellen Users in diesem Report.

Response:
```json
{
  "arkana_object_id": 8,
  "sessions": [
    {
      "session_id": "8-py-d30ab318",
      "container_name": "arkana-py-report-8",
      "runtime_type": "py",
      "language": "python",
      "user_id": "d30ab318-15da-4bf7-8331-aa4e24098f1b",
      "arkana_object_id": "8",
      "workspace_path": "/app/arkana_spheres/workspaces/report_8",
      "created_at": "2026-04-23T10:12:00",
      "expires_at": "2026-04-23T12:12:00",
      "lifetime_seconds": 7200
    }
  ]
}
```

### `POST /report/{arkana_id}/sessions`

Beschreibung:
- Löscht und erstellt die Runtime-Session-Container des aktuellen Users für diesen Report neu.
- der Workspace bleibt report-basiert.

Response:
```json
{
  "arkana_object_id": 8,
  "previous_sessions": [],
  "restarted_sessions": [],
  "status": "restarted"
}
```

## Report-Ausführung

### `POST /report/{arkana_id}/run`

Beschreibung:
- Führt alle ausführbaren Code-Zellen aus.
- `?save=true|false`

Beispiel:
```http
POST /report/8/run?save=true
```

Response:
```json
{
  "arkana_object_id": 8,
  "save_result": true,
  "results": [
    {
      "cell": "py_code",
      "results": [
        {
          "cell_id": 13,
          "cell_type": "py_result",
          "content": "hello\n"
        }
      ]
    }
  ]
}
```

### `GET /report/{arkana_id}/cell/{cell_identifier}/run`

Beschreibung:
- Führt genau eine Zelle aus.
- `GET` speichert Ergebnisse nicht.

### `POST /report/{arkana_id}/cell/{cell_identifier}/run`

Beschreibung:
- Führt genau eine Zelle aus.
- `POST` akzeptiert `?save=true|false`.

Hinweis zu R:
- Wenn `rdata`-Zellen im Report existieren, werden die referenzierten `.RData`-Dateien vor jedem `r_code`-Run automatisch geladen.

## Report-Löschen

### `DELETE /report/{arkana_id}`

Beschreibung:
- Admin-only.
- Löscht Report, Zellen, Container und Workspaces.

Response:
```json
{
  "status": "deleted",
  "arkana_object_id": 8,
  "deleted_sessions": 2,
  "deleted_workspaces": 1
}
```

## Database

### `GET /db/{db_id}/`

Beschreibung:
- Liefert Schema-Metadaten für eine zugreifbare Datenbank.

### `GET /db/{db_id}/tables`

Beschreibung:
- Listet sichtbare Tabellen ohne interne Systemtabellen.

Response:
```json
{
  "db_id": 1,
  "tables": [
    {
      "table_name": "customers",
      "table_schema": "analytics"
    }
  ]
}
```

### `GET /database/{db_id}/table/{table_key}`

Beschreibung:
- Liefert eine JSON-Beschreibung einer konkreten Tabelle und ihrer Spalten.

Response:
```json
{
  "database_id": 1,
  "table_key": "customers",
  "table_name": "customers",
  "columns": [
    {
      "column_name": "id",
      "data_type": "bigint",
      "is_nullable": "NO",
      "column_key": "PRI"
    },
    {
      "column_name": "name",
      "data_type": "varchar",
      "is_nullable": "YES",
      "column_key": ""
    }
  ]
}
```

### `POST /db/{db_id}/key_models`

Request:
```json
{
  "start_tables": ["customers", "orders"],
  "max_distance": 2,
  "include_all": false
}
```

### `POST /db/`

Request-Felder:
- `user_group`
- `owner`
- `url`
- `ip`
- `db_name`
- `db_description`
- `db_con_id`

### `POST /db_connection/`

Request-Felder:
- `user_group`
- `owner`
- `url`
- `ip`
- `server_description`
- `default_user`
- `admin_user`
- `db_type`

### `GET /db_connection/personal_user/?db_id=<id>`

Beschreibung:
- Liefert den persönlichen DB-User des aktuellen Users.

### `POST /db_connection/personal_user/`

Request:
```json
{
  "db_id": 1,
  "arkana_user_id": "d30ab318-15da-4bf7-8331-aa4e24098f1b",
  "db_user_name": "niklas_private"
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

## Frames

### `POST /frames/execute`

Beschreibung:
- Führt ein Frame-Definition-Objekt aus.

Request:
```json
{
  "frame": {
    "frame_id": 1,
    "nodes": []
  },
  "input_parameters": {
    "country": "DE"
  },
  "referenced_frames": {}
}
```

Response:
```json
{
  "frame_id": 1,
  "result": {}
}
```
