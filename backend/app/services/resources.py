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


def bookable_resource(conn: sqlite3.Connection, resource_id: int) -> sqlite3.Row | None:
    """고객이 예약할 수 있는 자원. 소유 운영자가 승인된 상태여야 한다. 정지된 운영자의 자원은 새 예약을 받지 않는다. (D-065)"""
    return conn.execute(
        "SELECT r.* FROM resources r JOIN accounts a ON a.id = r.owner_account_id"
        " WHERE r.id = ? AND a.operator_status = 'approved'",
        (resource_id,),
    ).fetchone()


def _owned(conn: sqlite3.Connection, resource_id: int, owner_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM resources WHERE id = ? AND owner_account_id = ?", (resource_id, owner_id)
    ).fetchone()
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


def find_operator_by_slug(conn: sqlite3.Connection, booking_slug: str) -> sqlite3.Row | None:
    """예약 주소명의 승인된 운영자. 승인 대기·정지·없음은 모두 None 이다. (D-059, D-065)"""
    return conn.execute(
        "SELECT * FROM accounts WHERE booking_slug = ? AND role = 'operator'"
        " AND operator_status = 'approved'",
        (booking_slug,),
    ).fetchone()


def list_resource_names(conn: sqlite3.Connection, owner_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name FROM resources WHERE owner_account_id = ? ORDER BY id", (owner_id,)
    ).fetchall()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


def list_resources(conn: sqlite3.Connection, owner_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id FROM resources WHERE owner_account_id = ? ORDER BY id", (owner_id,)
    ).fetchall()
    return [_load(conn, row["id"]) for row in rows]


def create_resource(conn: sqlite3.Connection, data: ResourceInput, owner_id: int) -> dict:
    """요청한 운영자가 소유 운영자가 된다. 본문으로 소유자를 받지 않는다. (D-044)"""
    with write_unit(conn):
        cur = conn.execute(
            "INSERT INTO resources (name, min_duration_minutes, max_duration_minutes,"
            " cancel_deadline_hours, owner_account_id) VALUES (?, ?, ?, ?, ?)",
            (data.name, data.min_duration_minutes, data.max_duration_minutes,
             data.cancel_deadline_hours, owner_id),
        )
        _save_operating_hours(conn, cur.lastrowid, data)
        return _load(conn, cur.lastrowid)


def update_resource(conn: sqlite3.Connection, resource_id: int, data: ResourceInput,
                    owner_id: int) -> dict:
    with write_unit(conn):
        # 다른 운영자의 자원도 없는 자원과 같이 404 로 응답한다. (C-9, D-052)
        if not _owned(conn, resource_id, owner_id):
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
