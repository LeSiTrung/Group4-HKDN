"""Independent regression checks for account/session and request boundaries."""

import asyncio
import hashlib
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import RequestGate

PASSWORD = 'Synthetic-test-password-123'
HEADERS = {'X-Requested-With': 'D7', 'Origin': 'http://app.example'}


@pytest.fixture
def account_client(tmp_path, monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE', 'false')
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://app.example')
    with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as client:
        yield client


def register(client, email='reader@example.com', **extra):
    return client.post('/api/auth/register', json={'name': 'Reader', 'email': email, 'password': PASSWORD, **extra})


def test_registration_cannot_elevate_role_or_expose_credentials(account_client):
    response = register(account_client, role='admin', active=1)
    assert response.status_code == 201
    assert set(response.json()['user']) == {'id', 'email', 'name', 'role'}
    assert response.json()['user']['role'] == 'reader'
    token = account_client.cookies.get('d7_session')
    with account_client.app.state.db() as db:
        user = db.execute('SELECT * FROM users').fetchone()
        session = db.execute('SELECT * FROM sessions').fetchone()
    assert user['password_hash'].startswith('$argon2id$')
    assert user['password_hash'] != PASSWORD
    assert session['token_hash'] == hashlib.sha256(token.encode()).hexdigest()
    assert session['token_hash'] != token


def test_email_normalization_prevents_duplicate_identity(account_client):
    assert register(account_client, ' READER@EXAMPLE.COM ').status_code == 201
    assert register(account_client, 'reader@example.com').status_code == 409
    assert account_client.post('/api/auth/login', json={'email': ' Reader@Example.COM ', 'password': PASSWORD}).status_code == 200


def test_password_change_revokes_other_sessions_and_old_password(account_client):
    assert register(account_client).status_code == 201
    other = TestClient(account_client.app, headers=HEADERS)
    assert other.post('/api/auth/login', json={'email': 'reader@example.com', 'password': PASSWORD}).status_code == 200
    old_token = account_client.cookies.get('d7_session')
    replacement = 'Another-synthetic-password-456'
    assert account_client.post('/api/auth/password', json={'current_password': PASSWORD, 'new_password': replacement}).status_code == 200
    assert account_client.cookies.get('d7_session') != old_token
    assert account_client.get('/api/auth/me').status_code == 200
    assert other.get('/api/auth/me').status_code == 401
    assert other.post('/api/auth/login', json={'email': 'reader@example.com', 'password': PASSWORD}).status_code == 401
    assert other.post('/api/auth/login', json={'email': 'reader@example.com', 'password': replacement}).status_code == 200


def test_logout_revokes_copied_cookie_server_side(account_client):
    register(account_client)
    old_token = account_client.cookies.get('d7_session')
    assert account_client.post('/api/auth/logout').status_code == 200
    account_client.cookies.set('d7_session', old_token)
    assert account_client.get('/api/auth/me').status_code == 401


def test_expired_and_disabled_accounts_reject_existing_cookie(account_client):
    response = register(account_client)
    user_id = response.json()['user']['id']
    with account_client.app.state.db() as db:
        db.execute('UPDATE sessions SET expires_at=?', (int(time.time()) - 1,))
    assert account_client.get('/api/auth/me').status_code == 401
    assert account_client.post('/api/auth/login', json={'email': 'reader@example.com', 'password': PASSWORD}).status_code == 200
    with account_client.app.state.db() as db:
        db.execute('UPDATE users SET active=0 WHERE id=?', (user_id,))
    assert account_client.get('/api/auth/me').status_code == 401
    assert account_client.post('/api/auth/login', json={'email': 'reader@example.com', 'password': PASSWORD}).status_code == 401


def test_wrong_password_cannot_change_or_delete_account(account_client):
    register(account_client)
    assert account_client.post('/api/auth/password', json={'current_password': 'wrong', 'new_password': 'Replacement-password-123'}).status_code == 400
    assert account_client.request('DELETE', '/api/auth/me', json={'password': 'wrong'}).status_code == 400
    assert account_client.get('/api/auth/me').status_code == 200


def test_account_deletion_cascades_private_data_only(account_client):
    user_id = register(account_client).json()['user']['id']
    with account_client.app.state.db() as db:
        cursor = db.execute('INSERT INTO conversations(user_id,title) VALUES (?,?)', (user_id, 'Private conversation'))
        message = db.execute('INSERT INTO messages(conversation_id,role,content) VALUES (?,?,?)', (cursor.lastrowid, 'assistant', 'Private answer'))
        db.execute('INSERT INTO feedback VALUES (?,?,?,?)', (user_id, message.lastrowid, 1, 'Private feedback'))
        # Completed transactions can be erased; unresolved ones require reconciliation first.
        db.execute('INSERT INTO renewals VALUES (?,?,?,?,?)', ('test-key', user_id, 'loan', 'succeeded', None))
        db.execute('INSERT INTO users(email,name,password_hash) VALUES (?,?,?)', ('other@example.com', 'Other', 'synthetic-unused-hash'))
    assert account_client.request('DELETE', '/api/auth/me', json={'password': PASSWORD}).status_code == 200
    assert account_client.get('/api/auth/me').status_code == 401
    assert account_client.get('/api/export').status_code == 401
    with account_client.app.state.db() as db:
        for table in ('sessions', 'conversations', 'messages', 'feedback', 'renewals'):
            assert db.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0
        assert db.execute('SELECT email FROM users').fetchone()[0] == 'other@example.com'


@pytest.mark.parametrize('headers', [{}, {'X-Requested-With': 'XMLHttpRequest'}, {'X-Requested-With': 'D7', 'Origin': 'null'}, {'X-Requested-With': 'D7', 'Origin': 'http://app.example.evil.test'}])
def test_csrf_rejects_missing_marker_and_untrusted_origins(account_client, headers):
    response = TestClient(account_client.app).post('/api/auth/logout', headers=headers)
    assert response.status_code == 403


def test_secure_cookie_flags_and_response_headers(tmp_path, monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    monkeypatch.setenv('ALLOWED_ORIGINS', 'https://app.example')
    with TestClient(create_app(tmp_path, testing=True), base_url='https://app.example', headers={'X-Requested-With': 'D7', 'Origin': 'https://app.example'}) as client:
        response = register(client)
        assert response.status_code == 201
        cookie = response.headers['set-cookie'].lower()
        assert 'httponly' in cookie and 'secure' in cookie and 'samesite=strict' in cookie
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['x-frame-options'] == 'DENY'
        assert 'max-age=31536000' in response.headers['strict-transport-security']
        assert client.get('/api/auth/me').status_code == 200


def test_auth_rate_limit_uses_actual_peer_not_forwarded_header(tmp_path):
    app = FastAPI()
    app.add_middleware(RequestGate, settings=Settings(tmp_path, testing=False))
    @app.post('/api/auth/login')
    def login_probe():
        return {'ok': True}
    with TestClient(app, headers={'X-Requested-With': 'D7'}) as client:
        for index in range(10):
            assert client.post('/api/auth/login', headers={'X-Forwarded-For': '198.51.100.' + str(index)}).status_code == 200
        response = client.post('/api/auth/login', headers={'X-Forwarded-For': '198.51.100.99'})
        assert response.status_code == 429
        assert response.headers['retry-after'] == '60'


def test_chunked_body_limit_counts_bytes_without_content_length(tmp_path):
    reached_app, sent = [], []
    async def downstream(scope, receive, send):
        reached_app.append(True)
    requests = iter([{'type': 'http.request', 'body': b'x' * 40000, 'more_body': True}, {'type': 'http.request', 'body': b'x' * 30000, 'more_body': False}])
    async def receive():
        return next(requests)
    async def send(message):
        sent.append(message)
    gate = RequestGate(downstream, Settings(tmp_path, testing=True))
    scope = {'type': 'http', 'method': 'POST', 'path': '/api/chat', 'headers': [(b'x-requested-with', b'D7')]}
    asyncio.run(gate(scope, receive, send))
    assert sent[0]['status'] == 413
    assert not reached_app


def test_rate_limit_peer_tracking_stays_bounded_during_address_rotation(tmp_path):
    async def downstream(scope, receive, send):
        return None
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(message):
        return None
    gate = RequestGate(downstream, Settings(tmp_path, testing=False))
    async def rotate():
        for index in range(10002):
            peer = f'198.18.{index // 256}.{index % 256}'
            await gate({'type': 'http', 'method': 'GET', 'path': '/api/auth/me', 'client': (peer, 12345), 'headers': []}, receive, send)
    asyncio.run(rotate())
    assert len(gate.hits) <= 10000
