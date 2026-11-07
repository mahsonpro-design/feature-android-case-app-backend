"""Private API for the Arabic Albayda Court client.

The activity endpoint is protected by administrator authorization on the server.
"""
from __future__ import annotations
import json, logging, os, re, sqlite3, unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from case_records import CaseRecordsError, available_case_types, available_judges, generate_case_pdf, load_case_records, normalize_judge_name, search_case_records, search_sessions_by_date

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOG = logging.getLogger("albayda_api")
DB_PATH = Path(os.getenv("APP_DATABASE_PATH", "./data/app.sqlite3"))
HASHER = PasswordHasher()
DUMMY_HASH = HASHER.hash("constant-time-dummy-password")
BEARER = HTTPBearer(auto_error=False)
app = FastAPI(title="Albayda Court API", version="1.0.0", docs_url=None, redoc_url=None)

class RegisterBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=24)
    password: str = Field(min_length=10, max_length=128)
class LoginBody(BaseModel):
    phone: str = Field(min_length=7, max_length=24)
    password: str = Field(min_length=1, max_length=128)
class DecisionBody(BaseModel):
    approve: bool
class PdfBody(BaseModel):
    case_number: str = Field(min_length=1, max_length=40)

def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20); conn.row_factory = sqlite3.Row; conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn; conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()
def _phone(value):
    out=[]
    for c in value.strip():
        if c.isdecimal(): out.append(str(unicodedata.decimal(c)))
        elif c=="+" and not out: out.append(c)
        elif c in " -().": continue
        else: raise HTTPException(422,"رقم الجوال غير صالح.")
    s="".join(out); digits=s[1:] if s.startswith("+") else s
    if not digits.isdigit() or not 7<=len(digits)<=15: raise HTTPException(422,"رقم الجوال غير صالح.")
    return s
def _audit(actor, action, target=None, metadata=None):
    with _db() as c: c.execute("INSERT INTO activity(actor_id,action,target_id,metadata_json,created_at) VALUES(?,?,?,?,?)",(actor,action,target,json.dumps(metadata or {},ensure_ascii=False),_now()))
def _init():
    with _db() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user',state TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,reviewed_at TEXT,reviewed_by INTEGER REFERENCES users(id)); CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY,actor_id INTEGER REFERENCES users(id),action TEXT NOT NULL,target_id INTEGER REFERENCES users(id),metadata_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_users_state ON users(state,created_at); CREATE INDEX IF NOT EXISTS idx_activity_order ON activity(id DESC);""")
        if c.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone() is None:
            name=os.getenv("ADMIN_BOOTSTRAP_NAME","").strip(); phone=os.getenv("ADMIN_BOOTSTRAP_PHONE",""); password=os.getenv("ADMIN_BOOTSTRAP_PASSWORD","")
            if not name or not phone or len(password)<12: raise RuntimeError("Set ADMIN_BOOTSTRAP_NAME, ADMIN_BOOTSTRAP_PHONE and a 12+ character ADMIN_BOOTSTRAP_PASSWORD")
            c.execute("INSERT INTO users(name,phone,password_hash,role,state,created_at) VALUES(?,?,?,'admin','approved',?)",(name,_phone(phone),HASHER.hash(password),_now()))
@app.on_event("startup")
def startup():
    if len(os.getenv("JWT_SECRET",""))<32: raise RuntimeError("JWT_SECRET must be a random value of at least 32 characters")
    _init()
@app.middleware("http")
async def headers(request:Request,call_next):
    r=await call_next(request); r.headers["Cache-Control"]="no-store"; r.headers["X-Content-Type-Options"]="nosniff"; r.headers["X-Frame-Options"]="DENY"; r.headers["Referrer-Policy"]="no-referrer"; return r
def _public(u): return {k:u[k] for k in ("id","name","phone","role","state","created_at")}
def _current(credentials:Annotated[HTTPAuthorizationCredentials|None,Depends(BEARER)]):
    if credentials is None: raise HTTPException(401,"سجّل الدخول للمتابعة.")
    try: claims=jwt.decode(credentials.credentials,os.environ["JWT_SECRET"],algorithms=["HS256"],options={"require":["sub","exp"]}); uid=int(claims["sub"])
    except (jwt.PyJWTError,KeyError,ValueError,TypeError): raise HTTPException(401,"انتهت صلاحية الجلسة؛ سجّل الدخول مجدداً.")
    with _db() as c: u=c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    if not u: raise HTTPException(401,"الحساب غير موجود.")
    if u["state"]!="approved": raise HTTPException(403,"الحساب غير معتمد أو موقوف.")
    return dict(u)
def _admin(u:Annotated[dict,Depends(_current)]):
    if u["role"]!="admin": raise HTTPException(403,"هذه الخدمة لمدير النظام فقط.")
    return u
def _token(u):
    ts=int(datetime.now(timezone.utc).timestamp()); return jwt.encode({"sub":str(u["id"]),"iat":ts,"exp":ts+28800},os.environ["JWT_SECRET"],algorithm="HS256")
@app.get("/api/health")
def health(): return {"status":"ok"}
@app.post("/api/auth/register",status_code=202)
def register(b:RegisterBody):
    name=b.name.strip(); phone=_phone(b.phone)
    if len(name)<2: raise HTTPException(422,"أدخل الاسم كاملاً.")
    try:
        with _db() as c:
            cur=c.execute("INSERT INTO users(name,phone,password_hash,state,created_at) VALUES(?,?,?,'pending',?)",(name,phone,HASHER.hash(b.password),_now())); uid=cur.lastrowid
            c.execute("INSERT INTO activity(actor_id,action,target_id,created_at) VALUES(?,?,?,?)",(uid,"registration_submitted",uid,_now()))
    except sqlite3.IntegrityError: raise HTTPException(409,"رقم الجوال مسجل مسبقاً.")
    return {"state":"pending","message":"تم استلام طلب التسجيل. يمكنك الدخول بعد موافقة مدير النظام."}
@app.post("/api/auth/login")
def login(b:LoginBody):
    phone=_phone(b.phone)
    with _db() as c: u=c.execute("SELECT * FROM users WHERE phone=?",(phone,)).fetchone()
    try: valid=HASHER.verify(u["password_hash"] if u else DUMMY_HASH,b.password)
    except (VerifyMismatchError,InvalidHashError): valid=False
    if not valid: _audit(None,"login_failed"); raise HTTPException(401,"رقم الجوال أو كلمة المرور غير صحيحة.")
    if u["state"]!="approved": _audit(u["id"],"login_denied_unapproved"); raise HTTPException(403,"طلب الحساب بانتظار موافقة مدير النظام.")
    _audit(u["id"],"login_succeeded"); return {"access_token":_token(u),"token_type":"bearer","user":_public(u)}
@app.get("/api/me")
def me(u:Annotated[dict,Depends(_current)]): return _public(u)
@app.get("/api/case-types")
def case_types(u:Annotated[dict,Depends(_current)]):
    try: records=load_case_records()
    except CaseRecordsError as e: raise HTTPException(503,str(e))
    _audit(u["id"],"case_types_viewed"); return {"case_types":available_case_types(records),"judges":available_judges(records)}
@app.get("/api/cases/search")
def search(u:Annotated[dict,Depends(_current)],q:str=Query(min_length=1,max_length=120),case_type:str="all",judge:str="all",limit:int=Query(20,ge=1,le=50)):
    method="number" if "/" in q else "name"
    try: results=search_case_records(load_case_records(),q.strip(),method,case_type,judge,limit=limit)
    except CaseRecordsError as e: raise HTTPException(503,str(e))
    _audit(u["id"],"case_search",metadata={"method":method,"result_count":len(results)}); return {"count":len(results),"cases":results}
def _date(s):
    s="".join(str(unicodedata.decimal(x)) if x.isdecimal() else x for x in s.strip())
    for fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y"):
        try: return datetime.strptime(s,fmt).date().isoformat()
        except ValueError: pass
    return None
@app.get("/api/sessions")
def sessions(u:Annotated[dict,Depends(_current)],date_value:str=Query(alias="date",min_length=8,max_length=10),judge:str="all"):
    d=_date(date_value)
    if not d: raise HTTPException(422,"التاريخ غير صالح؛ استخدم YYYY-MM-DD.")
    try: results=search_sessions_by_date(load_case_records(),d)
    except CaseRecordsError as e: raise HTTPException(503,str(e))
    if judge!="all": results=[r for r in results if normalize_judge_name(r.get("برئاسة القاضي"))==normalize_judge_name(judge)]
    _audit(u["id"],"sessions_search",metadata={"result_count":len(results)}); return {"date":d,"count":len(results),"sessions":results[:500]}
@app.post("/api/cases/pdf")
def case_pdf(b:PdfBody,u:Annotated[dict,Depends(_current)]):
    try:
        results=search_case_records(load_case_records(),b.case_number,"number",limit=1)
        if not results: raise HTTPException(404,"لم يتم العثور على القضية.")
        pdf=generate_case_pdf(results[0])
    except CaseRecordsError as e: raise HTTPException(503,str(e))
    _audit(u["id"],"case_pdf_downloaded"); safe=re.sub(r"[^0-9A-Za-z_-]","_",b.case_number)[:40]
    return Response(pdf.getvalue(),media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="case_{safe}.pdf"'})
@app.get("/api/admin/users")
def admin_users(u:Annotated[dict,Depends(_admin)],state:str=Query("pending",pattern="^(pending|approved|rejected|all)$")):
    with _db() as c: rows=c.execute("SELECT * FROM users"+("" if state=="all" else " WHERE state=?")+" ORDER BY created_at DESC LIMIT 500",() if state=="all" else (state,)).fetchall()
    _audit(u["id"],"admin_users_listed",metadata={"filter":state}); return {"users":[_public(r) for r in rows]}
@app.post("/api/admin/users/{user_id}/decision")
def decide(user_id:int,b:DecisionBody,u:Annotated[dict,Depends(_admin)]):
    state="approved" if b.approve else "rejected"
    with _db() as c:
        target=c.execute("SELECT id,role FROM users WHERE id=?",(user_id,)).fetchone()
        if not target: raise HTTPException(404,"الحساب غير موجود.")
        if target["role"]=="admin": raise HTTPException(409,"لا يمكن تغيير حالة مدير النظام.")
        c.execute("UPDATE users SET state=?,reviewed_at=?,reviewed_by=? WHERE id=?",(state,_now(),u["id"],user_id))
        c.execute("INSERT INTO activity(actor_id,action,target_id,created_at) VALUES(?,?,?,?)",(u["id"],"user_"+state,user_id,_now()))
    return {"id":user_id,"state":state}
@app.get("/api/admin/activity")
def activity(u:Annotated[dict,Depends(_admin)],limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):
    # Authorization is enforced above: non-admin callers receive HTTP 403.
    with _db() as c: rows=c.execute("SELECT a.*,u.name AS actor_name,u.phone AS actor_phone FROM activity a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall()
    _audit(u["id"],"admin_activity_viewed",metadata={"count":len(rows)})
    return {"events":[{"id":r["id"],"action":r["action"],"actor":{"name":r["actor_name"],"phone":r["actor_phone"]} if r["actor_id"] else None,"target_user_id":r["target_id"],"metadata":json.loads(r["metadata_json"] or "{}"),"created_at":r["created_at"]} for r in rows]}
