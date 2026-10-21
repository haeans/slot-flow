import sqlite3

from app.errors import resource_not_found
from app.storage.db import write_unit
from app.validation.resource_input import ResourceInput


def _to_object(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "min_duration_minutes": row["min_duration_minutes"],
        "max_duration_minutes": row["max_duration_minutes"],
        "cancel_deadline_hours": row["cancel_deadline_hours"],
    }


def _load(conn: sqlite3.Connection, resource_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    return _to_object(row) if row else None


def list_resource_names(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name FROM resources ORDER BY id").fetchall()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


def create_resource(conn: sqlite3.Connection, data: ResourceInput) -> dict:
    with write_unit(conn):
        cur = conn.execute(
            "INSERT INTO resources (name, min_duration_minutes, max_duration_minutes,"
            " cancel_deadline_hours) VALUES (?, ?, ?, ?)",
            (data.name, data.min_duration_minutes, data.max_duration_minutes,
             data.cancel_deadline_hours),
        )
        return _load(conn, cur.lastrowid)


def update_resource(conn: sqlite3.Connection, resource_id: int, data: ResourceInput) -> dict:
    with write_unit(conn):
        if _load(conn, resource_id) is None:
            raise resource_not_found()
        conn.execute(
            "UPDATE resources SET name = ?, min_duration_minutes = ?, max_duration_minutes = ?,"
            " cancel_deadline_hours = ? WHERE id = ?",
            (data.name, data.min_duration_minutes, data.max_duration_minutes,
             data.cancel_deadline_hours, resource_id),
        )
        return _load(conn, resource_id)
