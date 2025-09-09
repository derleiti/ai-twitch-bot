import os, time
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from jose import jwt, JWTError
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from dotenv import load_dotenv
from auth.db import init_db, upsert_user, get_user, create_link_code, consume_link_code, link_identity

load_dotenv(); init_db()
app = FastAPI(title="AILinux Auth Service")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("JWT_SECRET","insecure"))

oauth = OAuth()
SITE_URL = os.getenv("SITE_URL","http://localhost:3000")
AUTH_BASE_URL = os.getenv("AUTH_BASE_URL","http://localhost:8088")
JWT_SECRET = os.getenv("JWT_SECRET","CHANGE_ME")
JWT_ISS = os.getenv("JWT_ISS","https://auth.ailinux.local")
JWT_AUD = os.getenv("JWT_AUD","ailinux")
JWT_TTL = int(os.getenv("JWT_TTL_SECONDS","3600"))

def issue_jwt(sub: str, email: str, roles: list) -> str:
    now = int(time.time())
    return jwt.encode({"iss":JWT_ISS,"aud":JWT_AUD,"iat":now,"exp":now+JWT_TTL,
                       "sub":sub,"email":email,"roles":roles},
                      JWT_SECRET, algorithm="HS256")

def verify_jwt(token: str):
    return jwt.decode(token, JWT_SECRET, audience=JWT_AUD, algorithms=["HS256"])

oauth.register("google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    client_kwargs={"scope":"openid email profile"},
)

WP_WELL_KNOWN = os.getenv("WP_WELL_KNOWN")
if WP_WELL_KNOWN:
    oauth.register("wordpress",
        server_metadata_url=WP_WELL_KNOWN,
        client_id=os.getenv("WP_CLIENT_ID",""),
        client_secret=os.getenv("WP_CLIENT_SECRET",""),
        client_kwargs={"scope":"openid email profile"},
    )
else:
    oauth.register("wordpress",
        api_base_url=os.getenv("WP_ISS",""),
        authorize_url=os.getenv("WP_AUTH_URL",""),
        access_token_url=os.getenv("WP_TOKEN_URL",""),
        client_id=os.getenv("WP_CLIENT_ID",""),
        client_secret=os.getenv("WP_CLIENT_SECRET",""),
        client_kwargs={"scope":"openid email profile"},
    )

COOKIE_SECURE = os.getenv("COOKIE_SECURE","true").lower() != "false"

def set_session_cookie(resp: Response, token: str):
    resp.set_cookie(
        "session", token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=JWT_TTL,
    )

def current_user(request: Request) -> dict:
    auth = request.headers.get("authorization","")
    tok: Optional[str] = None
    if auth.lower().startswith("bearer "): tok = auth.split(" ",1)[1].strip()
    if not tok: tok = request.cookies.get("session")
    if not tok: raise HTTPException(401, "login required")
    try: return verify_jwt(tok)
    except JWTError: raise HTTPException(401, "invalid token")

@app.get("/auth/login/google")
async def login_google(request: Request):
    return await oauth.google.authorize_redirect(request, f"{AUTH_BASE_URL}/auth/callback/google")

@app.get("/auth/callback/google")
async def cb_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = await oauth.google.parse_id_token(request, token)
    email = userinfo.get("email"); sub = userinfo.get("sub")
    if not email or not sub: raise HTTPException(400, "no email/sub")
    user_id, roles = upsert_user("google", sub, email)
    jwt_tok = issue_jwt(user_id, email, roles)
    resp = RedirectResponse(url=f"{SITE_URL}/app"); set_session_cookie(resp, jwt_tok); return resp

@app.get("/auth/login/wp")
async def login_wp(request: Request):
    return await oauth.wordpress.authorize_redirect(request, f"{AUTH_BASE_URL}/auth/callback/wp")

@app.get("/auth/callback/wp")
async def cb_wp(request: Request):
    token = await oauth.wordpress.authorize_access_token(request)
    userinfo = {}
    try: userinfo = await oauth.wordpress.parse_id_token(request, token)
    except Exception: pass
    if not userinfo:
        userinfo = (await oauth.wordpress.get("userinfo", token=token)).json()
    email = userinfo.get("email") or userinfo.get("preferred_username")
    sub = str(userinfo.get("sub") or userinfo.get("id"))
    if not email or not sub: raise HTTPException(400, "wp userinfo incomplete")
    user_id, roles = upsert_user("wordpress", sub, email)
    jwt_tok = issue_jwt(user_id, email, roles)
    resp = RedirectResponse(url=f"{SITE_URL}/app"); set_session_cookie(resp, jwt_tok); return resp

@app.get("/auth/me")
def me(user=Depends(current_user)):
    u = get_user(user["sub"])
    if not u: raise HTTPException(404, "user not found")
    return {"email": u["email"], "roles": u["roles"]}

@app.post("/auth/logout")
def logout():
    resp = JSONResponse({"ok": True}); resp.delete_cookie("session"); return resp

@app.post("/api/link/code")
async def link_code(req: Request):
    data = await req.json()
    tw = (data.get("twitch_username") or "").strip()
    if not tw: raise HTTPException(400, "twitch_username required")
    rec = create_link_code(tw, ttl_seconds=600)
    url = f"{AUTH_BASE_URL}/link?code={rec['code']}"
    return {"code": rec["code"], "url": url, "ttl_seconds": rec["ttl_seconds"]}

@app.get("/link")
def link_consume(code: str, user=Depends(current_user)):
    tw = consume_link_code(code)
    if not tw: return HTMLResponse("<h3>Code ungültig oder abgelaufen.</h3>", status_code=400)
    link_identity(user["sub"], "twitch", tw)
    return HTMLResponse(f"<h3>Twitch '{tw}' wurde mit deinem Account verknüpft.</h3>")

@app.get("/")
def root(): return {"service":"auth","status":"ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("auth_service:app", host="0.0.0.0", port=8088, reload=False)
