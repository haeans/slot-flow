import sqlite3

from app.errors import resource_not_found
from app.storage.db import write_unit
from app.validation.resource_input import WEEKDAYS, ResourceInput


def load_operating_hours(conn: sqlite3.Connection, resource_id: int) -> dict:
    hours = {day: None for day in WEEKDAYS}
    rows = conn.execute(
        "SELECT weekday, open_time, close_time FROM operating_hours WHERE resource_id = ?",
        (resource_id,),
    ).fetchall()
    for row in rows:
        hours[row["weekday"]] = {"open": row["open_time"], "close": row["close_time"]}
    return hours


def _load(conn: sqlite3.Connection, resource_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "operating_hours": load_operating_hours(conn, resource_id),
        "min_duration_minutes": row["min_duration_minutes"],
        "max_duration_minutes": row["max_duration_minutes"],
        "cancel_deadline_hours": row["cancel_deadline_hours"],
    }


def resource_exists(conn: sqlite3.Connection, resource_id: int) -> bool:
    row = conn.execute("SELECT 1 FROM resources WHERE id = ?", (resource_id,)).fetchone()
    return row is not None


def _save_operating_hours(conn: sqlite3.Connection, resource_id: int, data: ResourceInput) -> None:
    conn.execute("DELETE FROM operating_hours WHERE resource_id = ?", (resource_id,))
    for weekday, day in data.operating_hours.items():
        if day is not None:
            conn.execute(
                "INSERT INTO operating_hours (resource_id, weekday, open_time, close_time)"
                " VALUES (?, ?, ?, ?)",
                (resource_id, weekday, day.open, day.close),
            )


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
        _save_operating_hours(conn, cur.lastrowid, data)
        return _load(conn, cur.lastrowid)


def update_resource(conn: sqlite3.Connection, resource_id: int, data: ResourceInput) -> dict:
    with write_unit(conn):
        if not resource_exists(conn, resource_id):
            raise resource_not_found()
        conn.execute(
            "UPDATE resources SET name = ?, min_duration_minutes = ?, max_duration_minutes = ?,"
            " cancel_deadline_hours = ? WHERE id = ?",
            (data.name, data.min_duration_minutes, data.max_duration_minutes,
             data.cancel_deadline_hours, resource_id),
        )
        # 모든 필드를 한 번에 바꾸므로 운영시간 행은 지우고 다시 넣는다. (DATA-MODEL 2.2)
        _save_operating_hours(conn, resource_id, data)
        return _load(conn, resource_id)
