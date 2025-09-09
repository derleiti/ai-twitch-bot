import os, sqlite3, time, uuid, json, threading
from typing import Tuple, Optional, Dict

DB_PATH = os.getenv("AUTH_DB_PATH", "./auth.db")
_lock = threading.Lock()

def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _lock, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            roles TEXT NOT NULL DEFAULT '["member"]',
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identities (
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            provider_sub TEXT NOT NULL,
            linked_at INTEGER NOT NULL,
            UNIQUE(provider, provider_sub),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS link_codes (
            code TEXT PRIMARY KEY,
            twitch_username TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            ttl_seconds INTEGER NOT NULL
        );
        """)

def _now() -> int: return int(time.time())

def upsert_user(provider: str, provider_sub: str, email: str) -> Tuple[str, list]:
    """Legt User an (falls neu), verknüpft Identity, gibt (user_id, roles) zurück."""
    init_db()
    with _lock, _conn() as c:
        r = c.execute("SELECT u.id, u.roles FROM users u JOIN identities i ON u.id=i.user_id "
                      "WHERE i.provider=? AND i.provider_sub=?",
                      (provider, provider_sub)).fetchone()
        if r:
            return r["id"], json.loads(r["roles"])
        u = c.execute("SELECT id, roles FROM users WHERE email=?", (email,)).fetchone()
        if u:
            user_id = u["id"]; roles = json.loads(u["roles"])
        else:
            user_id = str(uuid.uuid4()); roles = ["member"]
            c.execute("INSERT INTO users(id,email,roles,created_at) VALUES(?,?,?,?)",
                      (user_id, email, json.dumps(roles), _now()))
        c.execute("INSERT OR IGNORE INTO identities(user_id,provider,provider_sub,linked_at) "
                  "VALUES(?,?,?,?)", (user_id, provider, provider_sub, _now()))
        return user_id, roles

def get_user(user_id: str) -> Optional[Dict]:
    with _lock, _conn() as c:
        u = c.execute("SELECT id,email,roles,created_at FROM users WHERE id=?", (user_id,)).fetchone()
        if not u: return None
        return {"id": u["id"], "email": u["email"], "roles": json.loads(u["roles"])}

def create_link_code(twitch_username: str, ttl_seconds: int = 600) -> Dict:
    code = uuid.uuid4().hex[:8].upper()
    with _lock, _conn() as c:
        c.execute("INSERT INTO link_codes(code,twitch_username,created_at,ttl_seconds) VALUES(?,?,?,?)",
                  (code, twitch_username, _now(), ttl_seconds))
    return {"code": code, "twitch_username": twitch_username, "ttl_seconds": ttl_seconds}

def consume_link_code(code: str) -> Optional[str]:
    now = _now()
    with _lock, _conn() as c:
        r = c.execute("SELECT twitch_username,created_at,ttl_seconds FROM link_codes WHERE code=?",
                      (code,)).fetchone()
        if not r: return None
        if now > r["created_at"] + r["ttl_seconds"]:
            c.execute("DELETE FROM link_codes WHERE code=?", (code,))
            return None
        c.execute("DELETE FROM link_codes WHERE code=?", (code,))
        return r["twitch_username"]

def link_identity(user_id: str, provider: str, provider_sub: str):
    with _lock, _conn() as c:
        c.execute("INSERT OR IGNORE INTO identities(user_id,provider,provider_sub,linked_at) "
                  "VALUES(?,?,?,?)", (user_id, provider, provider_sub, _now()))
