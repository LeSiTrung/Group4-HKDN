"""Real session rows must remain valid through private work in a request."""

import hashlib
import time

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api import auth
from app.main import create_app

PASSWORD = 'Synthetic-revocation-password-123'
HEADERS = {'X-Requested-With': 'LibraryAssistant'}


@pytest.fixture
def reader(tmp_path, monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as client:
        response = client.post('/api/auth/register', json={
            'name': 'Synthetic reader', 'email': 'reader@example.test', 'password': PASSWORD,
        })
        assert response.status_code == 201
        uid = response.json()['user']['id']
        with client.app.state.db() as db:
            cid = db.execute('INSERT INTO conversations(user_id,title) VALUES (?,?)', (uid, 'Private history')).lastrowid
            mid = db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'assistant','Private answer marker')", (cid,)).lastrowid
            # Another valid login must not keep the revoked login authorized.
            db.execute('INSERT INTO sessions VALUES (?,?,?)', ('other-synthetic-session-hash', uid, int(time.time()) + 3600))
        yield client, uid, cid, mid


def end_request_session(client, state):
    token_hash = hashlib.sha256(client.cookies.get('library_session').encode()).hexdigest()
    with client.app.state.db() as db:
        if state == 'revoked':
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash,))
        else:
            db.execute('UPDATE sessions SET expires_at=? WHERE token_hash=?', (int(time.time()) - 1, token_hash))


def test_public_account_surfaces_do_not_expose_session_proof(reader):
    client, _, _, _ = reader
    token = client.cookies.get('library_session')
    for url in ['/api/auth/me', '/api/export']:
        response = client.get(url)
        assert response.status_code == 200
        assert set(response.json()['user']) == {'id', 'email', 'name', 'role'}
        assert token not in response.text
        assert hashlib.sha256(token.encode()).hexdigest() not in response.text


def test_revoking_another_login_keeps_current_session_authorized(reader):
    client, uid, _, _ = reader
    old_token = client.cookies.get('library_session')
    response = client.post('/api/auth/login', json={'email': 'reader@example.test', 'password': PASSWORD})
    assert response.status_code == 200
    assert client.cookies.get('library_session') != old_token
    with client.app.state.db() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(old_token.encode()).hexdigest(),))
    client.app.state.answer = lambda message, history=None: {
        'answer': 'Current session answer', 'status': 'answered', 'sources': [], 'suggestions': [], 'mode': 'faq',
    }
    response = client.post('/api/chat', json={'message': 'Current session question'})
    assert response.status_code == 200
    exported = client.get('/api/export')
    assert exported.status_code == 200
    assert exported.json()['user']['id'] == uid
    assert exported.json()['conversations'][-1]['messages'][-1]['content'] == 'Current session answer'


@pytest.mark.parametrize('state', ['revoked', 'expired'])
@pytest.mark.parametrize('existing', [False, True])
def test_ended_session_during_generation_cannot_persist_chat(reader, state, existing):
    client, uid, cid, _ = reader

    def answer(message, history=None):
        end_request_session(client, state)
        return {'answer': 'Generated answer', 'status': 'answered', 'sources': [], 'suggestions': [], 'mode': 'faq'}

    client.app.state.answer = answer
    payload = {'message': 'Message that must not be saved'}
    if existing:
        payload['conversation_id'] = cid
    response = client.post('/api/chat', json=payload)
    assert response.status_code == 401
    assert client.cookies.get('library_session') is None
    with client.app.state.db() as db:
        assert db.execute('SELECT count(*) FROM conversations WHERE user_id=?', (uid,)).fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM messages WHERE conversation_id=?', (cid,)).fetchone()[0] == 1


@pytest.mark.parametrize('state', ['revoked', 'expired'])
@pytest.mark.parametrize('surface', ['list', 'read', 'export', 'delete', 'feedback', 'password', 'account_delete'])
def test_ended_session_after_authentication_cannot_read_or_mutate_private_data(reader, state, surface):
    client, uid, cid, mid = reader
    with client.app.state.db() as db:
        original_hash = db.execute('SELECT password_hash FROM users WHERE id=?', (uid,)).fetchone()[0]

    def ended_after_authentication(request: Request):
        user = auth.optional_user(request)
        end_request_session(client, state)
        return user

    client.app.dependency_overrides[auth.optional_user] = ended_after_authentication
    method, url, payload = {
        'list': ('GET', '/api/conversations', None),
        'read': ('GET', f'/api/conversations/{cid}', None),
        'export': ('GET', '/api/export', None),
        'delete': ('DELETE', f'/api/conversations/{cid}', None),
        'feedback': ('POST', '/api/feedback', {'message_id': mid, 'rating': 1}),
        'password': ('POST', '/api/auth/password', {'current_password': PASSWORD, 'new_password': 'Changed-synthetic-password-456'}),
        'account_delete': ('DELETE', '/api/auth/me', {'password': PASSWORD}),
    }[surface]
    response = client.request(method, url, json=payload)
    assert response.status_code == 401
    assert 'Private answer marker' not in response.text
    assert client.cookies.get('library_session') is None
    with client.app.state.db() as db:
        assert db.execute('SELECT password_hash FROM users WHERE id=?', (uid,)).fetchone()[0] == original_hash
        assert db.execute('SELECT count(*) FROM conversations WHERE id=?', (cid,)).fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM messages WHERE id=?', (mid,)).fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM feedback').fetchone()[0] == 0
