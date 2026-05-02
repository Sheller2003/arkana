from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from src.arkana_auth.user_object import ArkanaUser


@dataclass(frozen=True)
class RouteAuthSpec:
    auth_class: str
    auth_key: str
    required_value: int = 1


ROUTE_AUTH_SPECS: dict[str, RouteAuthSpec] = {
    "health": RouteAuthSpec("api.health", "api.health.read"),
    "get_user_login_check": RouteAuthSpec("api.user", "api.user.login_check.read"),
    "get_user_usage": RouteAuthSpec("api.user", "api.user.usage.read"),
    "get_user_max_usage": RouteAuthSpec("api.user", "api.user.max_usage.read"),
    "get_specific_user_usage": RouteAuthSpec("api.user", "api.user.usage.user.read"),
    "reload_specific_user": RouteAuthSpec("api.user", "api.user.reload.user.write"),
    "reload_current_user": RouteAuthSpec("api.user", "api.user.reload.self.write"),
    "get_db": RouteAuthSpec("api.db", "api.db.read"),
    "get_db_tables": RouteAuthSpec("api.db", "api.db.tables.read"),
    "get_database_table": RouteAuthSpec("api.db", "api.db.table.read"),
    "get_key_models": RouteAuthSpec("api.db", "api.db.key_models.read"),
    "create_db": RouteAuthSpec("api.db", "api.db.create"),
    "create_db_connection": RouteAuthSpec("api.db", "api.db.connection.create"),
    "get_personal_user": RouteAuthSpec("api.db", "api.db.personal_user.read"),
    "create_personal_user": RouteAuthSpec("api.db", "api.db.personal_user.create"),
    "set_db_user_password": RouteAuthSpec("api.db", "api.db.user_password.write"),
    "execute_frame": RouteAuthSpec("api.frames", "api.frames.execute"),
    "create_notes": RouteAuthSpec("api.notes", "api.notes.create"),
    "get_notes": RouteAuthSpec("api.notes", "api.notes.read"),
    "get_tmp_notes": RouteAuthSpec("api.notes", "api.notes.tmp.read"),
    "save_notes": RouteAuthSpec("api.notes", "api.notes.save"),
    "create_notes_chapter": RouteAuthSpec("api.notes", "api.notes.chapter.create"),
    "get_note_chapter": RouteAuthSpec("api.notes", "api.notes.chapter.read"),
    "get_note_chapter_files": RouteAuthSpec("api.notes", "api.notes.chapter.files.read"),
    "upload_note_chapter_file": RouteAuthSpec("api.notes", "api.notes.chapter.file.upload"),
    "create_group": RouteAuthSpec("api.groups", "api.groups.create"),
    "get_group_members": RouteAuthSpec("api.groups", "api.groups.members.read"),
    "delete_group": RouteAuthSpec("api.groups", "api.groups.delete"),
    "assign_group": RouteAuthSpec("api.groups", "api.groups.assign"),
    "get_report": RouteAuthSpec("api.report", "api.report.read"),
    "create_report": RouteAuthSpec("api.report", "api.report.create"),
    "get_report_cell": RouteAuthSpec("api.report", "api.report.cell.read"),
    "get_report_cell_by_id": RouteAuthSpec("api.report", "api.report.cell_by_id.read"),
    "get_report_cell_content_by_id": RouteAuthSpec("api.report", "api.report.cell_content_by_id.read"),
    "get_report_cell_content": RouteAuthSpec("api.report", "api.report.cell_content.read"),
    "get_report_files": RouteAuthSpec("api.report", "api.report.files.read"),
    "get_report_file": RouteAuthSpec("api.report", "api.report.file.read"),
    "get_report_sessions": RouteAuthSpec("api.report", "api.report.sessions.read"),
    "restart_report_sessions": RouteAuthSpec("api.report", "api.report.sessions.restart"),
    "update_report_cell": RouteAuthSpec("api.report", "api.report.cell.update"),
    "delete_report_cell": RouteAuthSpec("api.report", "api.report.cell.delete"),
    "upload_report_cell_file": RouteAuthSpec("api.report", "api.report.cell.upload"),
    "upload_report_file": RouteAuthSpec("api.report", "api.report.file.upload"),
    "delete_report": RouteAuthSpec("api.report", "api.report.delete"),
    "create_report_cell": RouteAuthSpec("api.report", "api.report.cell.create"),
    "run_report_cells": RouteAuthSpec("api.report", "api.report.run"),
    "get_run_report_cell": RouteAuthSpec("api.report", "api.report.cell.run.read"),
    "post_run_report_cell": RouteAuthSpec("api.report", "api.report.cell.run"),
}


def require_route_auth(current_user: ArkanaUser, route_name: str) -> None:
    if getattr(current_user, "user_role", "") == "root":
        return
    spec = ROUTE_AUTH_SPECS[route_name]
    if not current_user.has_auth_class_assignment(spec.auth_class):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing auth class: {spec.auth_class}",
        )
    if not current_user.has_effective_auth(spec.auth_key, required_value=spec.required_value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing auth object: {spec.auth_key}",
        )


__all__ = ["ROUTE_AUTH_SPECS", "RouteAuthSpec", "require_route_auth"]
