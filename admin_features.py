"""Administrator management/report routes and advanced search.

Mounted by app_entry.py after api.py has defined auth and database helpers.
All admin endpoints are authorized on the server, not just hidden in the UI.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api import HASHER, _admin, _audit, _current, _db, _now, _phone, _public
from case_records import CaseRecordsError, case_type_matches, load_case_records, normalize_judge_name, search_case_records

router = APIRouter()


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=7, max_length=24)
    state: str | None = Field(default=None, pattern=r"^(pending|approved|rejected)$")
    password: str | None = Field(default=None, min_length=10, max_length=128)


@router.get("/api/admin/users/manage")
def manage_users(
    admin: Annotated[dict, Depends(_admin)],
    state: str = Query(default="all", pattern=r"^(pending|approved|rejected|all)$"),
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    clauses, values = [], []
    if state != "all":
        clauses.append("state=?")
        values.append(state)
    if q.strip():
        clauses.append("(name LIKE ? OR phone LIKE ?)")
        values.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users" + where, values).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM users" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
    _audit(admin["id"], "admin_users_managed", metadata={"filter": state, "count": len(rows)})
    return {"total": total, "users": [_public(row) for row in rows]}


@router.patch("/api/admin/users/{user_id}")
def update_user(user_id: int, patch: UserPatch, admin: Annotated[dict, Depends(_admin)]):
    changes = patch.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "لا توجد حقول لتحديثها.")
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "الحساب غير موجود.")
        if row["role"] == "admin" and user_id != admin["id"]:
            raise HTTPException(409, "لا يمكن تعديل حساب مدير آخر.")
        updates, params = [], []
        if "name" in changes:
            updates.append("name=?"); params.append(changes["name"].strip())
        if "phone" in changes:
            updates.append("phone=?"); params.append(_phone(changes["phone"]))
        if "state" in changes:
            if row["role"] == "admin" and changes["state"] != "approved":
                raise HTTPException(409, "لا يمكن إيقاف حساب مدير النظام من هنا.")
            updates.extend(["state=?", "reviewed_at=?", "reviewed_by=?"])
            params.extend([changes["state"], _now(), admin["id"]])
        if "password" in changes:
            updates.append("password_hash=?"); params.append(HASHER.hash(changes["password"]))
        try:
            conn.execute("UPDATE users SET " + ",".join(updates) + " WHERE id=?", [*params, user_id])
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise HTTPException(409, "رقم الجوال مستخدم من حساب آخر.")
            raise
        updated = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    _audit(admin["id"], "admin_user_updated", target=user_id, metadata={"fields": sorted(changes)})
    return {"user": _public(updated)}


@router.delete("/api/admin/users/{user_id}")
def deactivate_user(user_id: int, admin: Annotated[dict, Depends(_admin)]):
    """Deactivate rather than erase: retain audit history and referential integrity."""
    if user_id == admin["id"]:
        raise HTTPException(409, "لا يمكنك إيقاف حسابك أثناء تسجيل الدخول.")
    with _db() as conn:
        row = conn.execute("SELECT id,role FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "الحساب غير موجود.")
        if row["role"] == "admin":
            raise HTTPException(409, "لا يمكن إيقاف حساب مدير النظام.")
        conn.execute("UPDATE users SET state='rejected',reviewed_at=?,reviewed_by=? WHERE id=?", (_now(), admin["id"], user_id))
    _audit(admin["id"], "admin_user_deactivated", target=user_id)
    return {"id": user_id, "state": "rejected"}


@router.get("/api/admin/reports/stats")
def statistics(admin: Annotated[dict, Depends(_admin)]):
    with _db() as conn:
        states = {r["state"]: r["n"] for r in conn.execute("SELECT state,COUNT(*) n FROM users GROUP BY state")}
        roles = {r["role"]: r["n"] for r in conn.execute("SELECT role,COUNT(*) n FROM users GROUP BY role")}
        today = conn.execute("SELECT COUNT(*) FROM activity WHERE substr(created_at,1,10)=date('now')").fetchone()[0]
        week = conn.execute("SELECT COUNT(*) FROM activity WHERE julianday(created_at)>=julianday('now','-7 days')").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
        top = conn.execute("SELECT action,COUNT(*) n FROM activity WHERE julianday(created_at)>=julianday('now','-30 days') GROUP BY action ORDER BY n DESC LIMIT 10").fetchall()
    _audit(admin["id"], "admin_statistics_viewed")
    return {"users": {"total": sum(states.values()), "by_state": states, "by_role": roles}, "activity": {"total": total, "today": today, "last_7_days": week, "top_actions_30_days": [{"action": r["action"], "count": r["n"]} for r in top]}}


@router.get("/api/cases/advanced-search")
def advanced_search(
    user: Annotated[dict, Depends(_current)],
    q: str = Query(default="", max_length=120),
    case_type: str = Query(default="all", max_length=80),
    judge: str = Query(default="all", max_length=120),
    session_from: str | None = Query(default=None, max_length=10),
    session_to: str | None = Query(default=None, max_length=10),
    limit: int = Query(default=30, ge=1, le=100),
):
    if not q.strip() and case_type == "all" and judge == "all" and not session_from and not session_to:
        raise HTTPException(422, "أدخل معيار بحث واحداً على الأقل.")
    try:
        records = load_case_records()
        if q.strip():
            method = "number" if "/" in q else "name"
            results = search_case_records(records, q.strip(), method, case_type, judge, limit=100000)
        else:
            results = [r for r in records if (case_type == "all" or case_type_matches(r.get("نوع القضية", ""), case_type)) and (judge == "all" or normalize_judge_name(r.get("برئاسة القاضي")) == normalize_judge_name(judge))]
        def date_value(value):
            raw = str(value or "").strip()
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(raw[:10], fmt).date().isoformat()
                except ValueError:
                    continue
            return ""
        if session_from:
            results = [r for r in results if date_value(r.get("الجلسة القادمة")) >= session_from]
        if session_to:
            results = [r for r in results if date_value(r.get("الجلسة القادمة")) <= session_to]
    except CaseRecordsError as exc:
        raise HTTPException(503, str(exc))
    results = results[:limit]
    _audit(user["id"], "advanced_case_search", metadata={"result_count": len(results), "date_filter": bool(session_from or session_to)})
    return {"count": len(results), "cases": results}
