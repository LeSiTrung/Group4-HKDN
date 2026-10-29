import hashlib
import re
import secrets
import sqlite3
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from pwdlib import PasswordHash

router = APIRouter(prefix='/auth', tags=['accounts'])
password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash('not-an-account-password')


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def email_value(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', v):
            raise ValueError('Email không hợp lệ.')
        return v


class Registration(Login):
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        if not v.strip():
            raise ValueError('Vui lòng nhập tên.')
        return v.strip()


def public_user(row):
    return {k: row[k] for k in ('id', 'email', 'name', 'role')}


def optional_user(request: Request):
    token = request.cookies.get('library_session')
    if not token:
        return None
    with request.app.state.db() as db:
        row = db.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1',
                         (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
    return dict(row) if row else None


def require_user(user=Depends(optional_user)):
    if not user:
        raise HTTPException(401, 'Vui lòng đăng nhập.')
    return user


def require_admin(user=Depends(require_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Chỉ quản trị viên được thực hiện thao tác này.')
    return user


def ensure_current_account(db,user):
    if not db.in_transaction:
        db.execute('BEGIN IMMEDIATE')
    if not db.execute('SELECT id FROM users WHERE id=? AND password_hash=? AND active=1',(user['id'],user['password_hash'])).fetchone():
        raise HTTPException(409,'Tài khoản đã thay đổi trong khi xử lý. Vui lòng đăng nhập lại.')


def start_session(request, response, user_id, expected_hash):
    token = secrets.token_urlsafe(32)
    with request.app.state.db() as db:
        ensure_current_account(db,{'id':user_id,'password_hash':expected_hash})
        db.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user_id, int(time.time())+86400*7))
    response.set_cookie('library_session', token, httponly=True, secure=request.app.state.settings.secure_cookies,
                        samesite='strict', max_age=86400*7, path='/')


@router.post('/register', status_code=201)
def register(body: Registration, request: Request, response: Response):
    hashed = password_hash.hash(body.password)
    try:
        with request.app.state.db() as db:
            cursor = db.execute('INSERT INTO users(email,name,password_hash) VALUES (?,?,?)', (body.email, body.name, hashed))
            user = public_user(db.execute('SELECT * FROM users WHERE id=?', (cursor.lastrowid,)).fetchone())
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Không thể đăng ký email này. Hãy đăng nhập hoặc dùng email khác.')
    start_session(request, response, user['id'],hashed)
    return {'user': user}


@router.post('/login')
def login(body: Login, request: Request, response: Response):
    with request.app.state.db() as db:
        user = db.execute('SELECT * FROM users WHERE email=?', (body.email,)).fetchone()
    valid = password_hash.verify(body.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid or not user['active']:
        raise HTTPException(401, 'Email hoặc mật khẩu không đúng.')
    start_session(request, response, user['id'],user['password_hash'])
    return {'user': public_user(user)}


@router.get('/me')
def me(user=Depends(require_user)):
    return {'user': public_user(user)}


@router.post('/logout')
def logout(request: Request, response: Response):
    token = request.cookies.get('library_session', '')
    with request.app.state.db() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie('library_session', path='/')
    return {'ok': True}


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


@router.post('/password')
def change_password(body: PasswordChange, request: Request, response: Response, user=Depends(require_user)):
    if not password_hash.verify(body.current_password, user['password_hash']):
        raise HTTPException(400, 'Mật khẩu hiện tại không đúng.')
    hashed=password_hash.hash(body.new_password)
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (hashed, user['id']))
        db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
    start_session(request, response, user['id'],hashed)
    return {'ok': True}


class DeleteAccount(BaseModel):
    password: str = Field(max_length=128)


@router.delete('/me')
def delete_account(body: DeleteAccount, request: Request, response: Response, user=Depends(require_user)):
    if not password_hash.verify(body.password, user['password_hash']):
        raise HTTPException(400, 'Mật khẩu không đúng.')
    if user['role'] == 'admin':
        raise HTTPException(409, 'Không thể tự xóa tài khoản quản trị qua giao diện.')
    with request.app.state.db() as db:
        ensure_current_account(db,user)
        if db.execute("SELECT 1 FROM renewals WHERE user_id=? AND state IN ('pending','uncertain')",(user['id'],)).fetchone():
            raise HTTPException(409,'Có giao dịch gia hạn cần đối soát. Vui lòng xử lý với thư viện trước khi xóa tài khoản; bạn vẫn có thể xóa lịch sử chat.')
        if not db.execute("DELETE FROM users WHERE id=? AND role!='admin'", (user['id'],)).rowcount:
            raise HTTPException(409,'Tài khoản đã thay đổi. Không thể xóa tài khoản này.')
    response.delete_cookie('library_session', path='/')
    return {'ok': True}
