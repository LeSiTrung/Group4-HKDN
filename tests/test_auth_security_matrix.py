"""Synthetic, in-process account and private-history boundary regressions."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api import auth
from app.main import create_app

PASSWORD = 'Synthetic-matrix-password-123'
HEADERS = {'X-Requested-With': 'LibraryAssistant', 'Origin': 'http://app.example'}


@pytest.fixture
def reader(tmp_path, monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE', 'false')
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://app.example')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as client:
        response = client.post('/api/auth/register', json={
            'name': 'Synthetic reader', 'email': 'owner@example.test', 'password': PASSWORD,
        })
        assert response.status_code == 201
        client.app.state.answer = lambda message, history=None: {
            'answer': 'Synthetic public answer', 'status': 'answered',
            'sources': [], 'suggestions': [], 'mode': 'faq',
        }
        yield client


def add_history(client, user_id, marker):
    with client.app.state.db() as db:
        cid = db.execute('INSERT INTO conversations(user_id,title) VALUES (?,?)', (user_id, marker)).lastrowid
        question = db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user',?)", (cid, marker)).lastrowid
        answer = db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'assistant',?)", (cid, marker)).lastrowid
    return cid, question, answer


def test_export_delete_and_feedback_cannot_cross_reader_boundary(reader):
    owner_id = reader.get('/api/auth/me').json()['user']['id']
    owner_cid, _, owner_mid = add_history(reader, owner_id, 'owner-private-marker')
    with TestClient(reader.app, headers=HEADERS) as other:
        response = other.post('/api/auth/register', json={
            'name': 'Other reader', 'email': 'other@example.test', 'password': PASSWORD,
        })
        assert response.status_code == 201
        other_id = response.json()['user']['id']
        other_cid, other_question, other_mid = add_history(other, other_id, 'other-private-marker')
        assert [row['id'] for row in other.get('/api/conversations').json()] == [other_cid]
        exported = other.get('/api/export').json()
        assert exported['user']['id'] == other_id
        assert [row['id'] for row in exported['conversations']] == [other_cid]
        assert 'owner-private-marker' not in json.dumps(exported)
        assert 'password_hash' not in json.dumps(exported)
        assert other.get(f'/api/conversations/{owner_cid}').status_code == 404
        assert other.delete(f'/api/conversations/{owner_cid}').status_code == 404
        assert other.post('/api/feedback', json={'message_id': owner_mid, 'rating': -1}).status_code == 404
        assert other.post('/api/feedback', json={'message_id': other_question, 'rating': 1}).status_code == 404
        assert other.post('/api/chat', json={'message': 'Forged follow-up', 'conversation_id': owner_cid}).status_code == 404
        assert other.post('/api/feedback', json={'message_id': other_mid, 'rating': 1}).status_code == 200
    with reader.app.state.db() as db:
        assert db.execute('SELECT count(*) FROM messages WHERE conversation_id=?', (owner_cid,)).fetchone()[0] == 2
        assert [tuple(row) for row in db.execute('SELECT user_id,message_id FROM feedback')] == [(other_id, other_mid)]
    assert reader.get(f'/api/conversations/{owner_cid}').status_code == 200


@pytest.mark.parametrize('state', ['expired', 'disabled', 'deleted', 'revoked', 'forged'])
def test_stale_cookie_cannot_access_any_private_history_surface(reader, state):
    user_id = reader.get('/api/auth/me').json()['user']['id']
    cid, _, mid = add_history(reader, user_id, 'stale-session-private-marker')
    token = reader.cookies.get('library_session') if state != 'forged' else 'forged-invalid-cookie-token'
    with reader.app.state.db() as db:
        if state == 'expired':
            db.execute('UPDATE sessions SET expires_at=?', (int(time.time()) - 1,))
        elif state == 'disabled':
            db.execute('UPDATE users SET active=0 WHERE id=?', (user_id,))
        elif state == 'deleted':
            db.execute('DELETE FROM users WHERE id=?', (user_id,))
        elif state == 'revoked':
            db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
    for method, url, payload in [
        ('GET', '/api/auth/me', None), ('GET', '/api/conversations', None), ('GET', f'/api/conversations/{cid}', None),
        ('GET', '/api/export', None), ('DELETE', f'/api/conversations/{cid}', None),
        ('POST', '/api/feedback', {'message_id': mid, 'rating': 1}),
    ]:
        reader.cookies.set('library_session', token, domain='testserver.local', path='/')
        response = reader.request(method, url, json=payload)
        assert response.status_code == 401, (state, method, url, response.text)
        assert 'stale-session-private-marker' not in response.text
        assert reader.cookies.get('library_session') is None
    for payload in [{'message': 'Forged follow-up', 'conversation_id': cid}, {'message': 'Unsaved authenticated question'}]:
        reader.cookies.set('library_session', token, domain='testserver.local', path='/')
        response = reader.post('/api/chat', json=payload)
        assert response.status_code == 401
        assert reader.cookies.get('library_session') is None
    guest = reader.post('/api/chat', json={'message': 'Explicit guest question'})
    assert guest.status_code == 200
    assert guest.json()['conversation_id'] is None
    assert guest.json()['message_id'] is None


@pytest.mark.parametrize('conversation', [False, True])
@pytest.mark.parametrize('token', ['', 'forged-invalid-cookie-token'])
def test_present_invalid_session_never_silently_runs_chat_as_guest(reader, conversation, token):
    uid = reader.get('/api/auth/me').json()['user']['id']
    cid, _, _ = add_history(reader, uid, 'Synthetic existing history')
    reader.cookies.set('library_session', token, domain='testserver.local', path='/')
    payload = {'message': 'Unsaved authenticated message'}
    if conversation:
        payload['conversation_id'] = cid
    response = reader.post('/api/chat', json=payload)
    assert response.status_code == 401
    assert reader.cookies.get('library_session') is None
    guest = reader.post('/api/chat', json={'message': 'Guest retry after session reset'})
    assert guest.status_code == 200
    assert guest.json()['conversation_id'] is None


@pytest.mark.parametrize(('method', 'url', 'payload'), [
    ('GET', '/api/conversations/9223372036854775808', None),
    ('DELETE', '/api/conversations/9223372036854775808', None),
    ('POST', '/api/feedback', {'message_id': 9223372036854775808, 'rating': 1}),
    ('POST', '/api/chat', {'message': 'Synthetic follow-up', 'conversation_id': 9223372036854775808}),
])
def test_out_of_range_history_ids_are_client_errors(reader, method, url, payload):
    response = reader.request(method, url, json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize('identifier', [0, -1, -9223372036854775809])
def test_nonpositive_history_ids_are_rejected(reader, identifier):
    assert reader.get(f'/api/conversations/{identifier}').status_code == 422
    assert reader.delete(f'/api/conversations/{identifier}').status_code == 422
    assert reader.post('/api/feedback', json={'message_id': identifier, 'rating': 1}).status_code == 422


def test_largest_supported_history_id_is_not_mistaken_for_invalid_input(reader):
    maximum = 9223372036854775807
    assert reader.get(f'/api/conversations/{maximum}').status_code == 404
    assert reader.delete(f'/api/conversations/{maximum}').status_code == 404
    assert reader.post('/api/feedback', json={'message_id': maximum, 'rating': 1}).status_code == 404
    assert reader.post('/api/chat', json={'message': 'Synthetic follow-up', 'conversation_id': maximum}).status_code == 404


@pytest.mark.parametrize(('field', 'value'), [('email', 'bad\ud800@example.test'), ('name', 'bad\ud800'), ('password', 'bad-password-\ud800')])
def test_surrogate_account_text_is_rejected_without_creating_account(reader, field, value):
    payload = {'name': 'Valid name', 'email': 'new@example.test', 'password': PASSWORD, field: value}
    response = reader.post('/api/auth/register', content=json.dumps(payload), headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    with reader.app.state.db() as db:
        assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 1


def test_surrogate_feedback_does_not_write_or_break_existing_feedback(reader):
    uid = reader.get('/api/auth/me').json()['user']['id']
    _, _, mid = add_history(reader, uid, 'Synthetic answer')
    assert reader.post('/api/feedback', json={'message_id': mid, 'rating': 1, 'comment': 'Valid feedback'}).status_code == 200
    response = reader.post('/api/feedback', content=json.dumps({'message_id': mid, 'rating': -1, 'comment': '\ud800'}), headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    with reader.app.state.db() as db:
        assert tuple(db.execute('SELECT rating,comment FROM feedback').fetchone()) == (1, 'Valid feedback')


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_unsafe_methods_reject_foreign_origin_before_account_or_history_mutation(reader, method):
    uid = reader.get('/api/auth/me').json()['user']['id']
    cid, _, _ = add_history(reader, uid, 'Synthetic protected history')
    response = reader.request(method, f'/api/conversations/{cid}', headers={'Origin': 'http://app.example.evil.test'})
    assert response.status_code == 403
    assert reader.get(f'/api/conversations/{cid}').status_code == 200


@pytest.mark.parametrize('content', [b'{', b'{"email":', b'null', b'[]', b'"reader@example.test"', b'{"name":"\xff"}'])
def test_malformed_registration_bodies_are_client_errors_and_create_no_user(reader, content):
    response = reader.post('/api/auth/register', content=content, headers={'Content-Type': 'application/json'})
    assert response.status_code in (400, 422)
    with reader.app.state.db() as db:
        assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 1


def test_validation_errors_preserve_field_location_without_reflecting_credentials(reader):
    response = reader.post('/api/auth/login', json={'email': 'owner@example.test', 'password': 'secret-123'})
    assert response.status_code == 422
    error = response.json()['detail'][0]
    assert error['loc'] == ['body', 'password']
    assert error['type'] == 'string_too_short'
    assert error['msg']
    assert set(error) == {'loc', 'type', 'msg'}
    assert 'secret-123' not in response.text


def test_vietnamese_and_valid_emoji_round_trip_through_account_feedback_and_export(reader):
    name = 'Độc giả kiểm thử 📚'
    response = reader.post('/api/auth/register', content=json.dumps({
        'name': name, 'email': 'unicode@example.test', 'password': 'Mật-khẩu-thử-nghiệm-123',
    }), headers={'Content-Type': 'application/json'})
    assert response.status_code == 201
    assert response.json()['user']['name'] == name
    uid = response.json()['user']['id']
    cid, _, mid = add_history(reader, uid, 'Lịch sử tìm sách 📖')
    comment = 'Hữu ích cho người mới 👍'
    assert reader.post('/api/feedback', json={'message_id': mid, 'rating': 1, 'comment': comment}).status_code == 200
    exported = reader.get('/api/export').json()
    assert exported['user']['name'] == name
    assert exported['conversations'][0]['id'] == cid
    assert exported['conversations'][0]['messages'][0]['content'] == 'Lịch sử tìm sách 📖'
    with reader.app.state.db() as db:
        assert db.execute('SELECT comment FROM feedback WHERE message_id=?', (mid,)).fetchone()[0] == comment


@pytest.mark.parametrize('state', ['disabled', 'password_changed'])
@pytest.mark.parametrize('surface', ['list', 'read', 'export', 'delete', 'feedback'])
def test_account_changed_after_authentication_cannot_access_or_mutate_private_history(reader, state, surface):
    uid = reader.get('/api/auth/me').json()['user']['id']
    cid, _, mid = add_history(reader, uid, 'In-flight private marker')

    def changed_after_authentication(request: Request):
        user = auth.optional_user(request)
        assert user is not None
        with reader.app.state.db() as db:
            if state == 'disabled':
                db.execute('UPDATE users SET active=0 WHERE id=?', (uid,))
            else:
                db.execute("UPDATE users SET password_hash='changed-synthetic-hash' WHERE id=?", (uid,))
        return user

    reader.app.dependency_overrides[auth.optional_user] = changed_after_authentication
    method, url, payload = {
        'list': ('GET', '/api/conversations', None),
        'read': ('GET', f'/api/conversations/{cid}', None),
        'export': ('GET', '/api/export', None),
        'delete': ('DELETE', f'/api/conversations/{cid}', None),
        'feedback': ('POST', '/api/feedback', {'message_id': mid, 'rating': 1}),
    }[surface]
    response = reader.request(method, url, json=payload)
    assert response.status_code == 409
    assert 'In-flight private marker' not in response.text
    with reader.app.state.db() as db:
        assert db.execute('SELECT count(*) FROM conversations WHERE id=?', (cid,)).fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM feedback').fetchone()[0] == 0


def test_concurrent_normalized_registration_creates_one_identity_and_one_session(reader):
    barrier = Barrier(2)

    def register(email):
        concurrent = TestClient(reader.app, headers=HEADERS)
        try:
            barrier.wait(timeout=5)
            response = concurrent.post('/api/auth/register', json={
                'name': 'Concurrent reader', 'email': email, 'password': PASSWORD,
            })
            return response.status_code
        finally:
            concurrent.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, [' RACE@EXAMPLE.TEST ', 'race@example.test']))
    assert sorted(results) == [201, 409]
    with reader.app.state.db() as db:
        assert db.execute("SELECT count(*) FROM users WHERE email='race@example.test'").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM sessions s JOIN users u ON u.id=s.user_id WHERE u.email='race@example.test'").fetchone()[0] == 1


KNOWLEDGE = {
    'title': 'Synthetic FAQ', 'question': 'Synthetic question', 'answer': 'Synthetic answer',
    'category': 'faq', 'source_url': 'https://example.test/synthetic-faq',
    'source_title': 'Synthetic fixture', 'checked_at': '2026-01-01', 'status': 'reviewed_public',
}
BOOK = {'title': 'Synthetic book', 'source_url': 'https://example.test/synthetic-book', 'checked_at': '2026-01-01'}


@pytest.mark.parametrize(('identifier', 'expected'), [
    (9223372036854775808, 422), (-9223372036854775809, 422), (9223372036854775807, 404),
])
@pytest.mark.parametrize(('method', 'path', 'payload'), [
    ('PUT', '/api/admin/knowledge', KNOWLEDGE), ('DELETE', '/api/admin/knowledge', None),
    ('PATCH', '/api/admin/users', {'active': False}), ('DELETE', '/api/admin/schedules', None),
    ('PUT', '/api/admin/books', BOOK), ('DELETE', '/api/admin/books', None),
    ('GET', '/api/catalog', None),
])
def test_admin_and_catalog_ids_are_bounded_before_database_access(reader, identifier, expected, method, path, payload):
    with reader.app.state.db() as db:
        db.execute("UPDATE users SET role='admin'")
        before = [db.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in ('users', 'books', 'knowledge', 'schedules', 'audit')]
    response = reader.request(method, f'{path}/{identifier}', json=payload)
    assert response.status_code == expected
    with reader.app.state.db() as db:
        after = [db.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in ('users', 'books', 'knowledge', 'schedules', 'audit')]
    assert after == before
