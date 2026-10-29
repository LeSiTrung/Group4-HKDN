"""Independent review regressions; synthetic accounts and mocked model IO only."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.api import auth as account_auth
from app.services import assistant, llm_service
from app.services.knowledge import today

PASSWORD = 'Synthetic-review-password-123'
HEADERS = {'X-Requested-With': 'LibraryAssistant'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as client:
        response = client.post('/api/auth/register', json={'name': 'Review reader', 'email': 'review@example.test', 'password': PASSWORD})
        assert response.status_code == 201
        with client.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
            db.execute('DELETE FROM knowledge')
        yield client


def add_knowledge(client, **changes):
    body = {'title': 'Chuyên mục trực tuyến', 'question': 'Truy cập chuyên mục trực tuyến', 'aliases': [], 'keywords': ['chuyên mục'],
            'answer': 'Truy cập chuyên mục trực tuyến từ trang thư viện.', 'category': 'faq', 'source_url': 'https://lic.ut.edu.vn/',
            'source_title': 'Synthetic reviewed evidence', 'checked_at': str(today()), 'status': 'reviewed_public', 'published': True}
    body.update(changes)
    response = client.post('/api/admin/knowledge', json=body)
    assert response.status_code == 201
    return response.json()


def mock_model(monkeypatch, content):
    monkeypatch.setenv('LLM_PROVIDER', 'ollama')
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'message': {'content': content}}))
    monkeypatch.setattr(llm_service, 'client', lambda: httpx.Client(transport=transport))


@pytest.mark.parametrize('content', ['[]', 'null'])
def test_nonobject_model_json_falls_back_without_raising(monkeypatch, content):
    mock_model(monkeypatch, content)
    assert llm_service.generate_answer('Question', [{'id': 1, 'answer': 'Evidence'}]) is None


def test_blank_model_answer_falls_back(monkeypatch):
    mock_model(monkeypatch, json.dumps({'answer': '   ', 'source_ids': [1]}))
    assert llm_service.generate_answer('Question', [{'id': 1, 'answer': 'Evidence'}]) is None


def test_sensitive_policy_requires_verification_even_if_categorized_faq(client):
    add_knowledge(client, question='Phí quá hạn là bao nhiêu?', keywords=['phí quá hạn'], answer='Phí quá hạn là 100000 đồng mỗi ngày.', category='faq')
    reply = client.post('/api/chat', json={'message': 'Phí quá hạn là bao nhiêu?'})
    assert reply.status_code == 200
    assert reply.json()['status'] == 'needs_confirmation'


def test_source_withdrawn_during_generation_is_not_returned(client, monkeypatch):
    row = add_knowledge(client)
    client.app.state.settings.testing = False
    calls = []
    def withdraw(question, rows, history=None):
        calls.append(True)
        with client.app.state.db() as db:
            db.execute('DELETE FROM knowledge WHERE id=?', (row['id'],))
        return {'answer': 'Truy cập chuyên mục trực tuyến từ trang thư viện.', 'source_ids': [row['id']]}
    monkeypatch.setattr(assistant, 'generate_answer', withdraw)
    # A weaker lexical match exercises generation; strong FAQ matches bypass it.
    reply = client.post('/api/chat', json={'message': 'chuyên mục trực tuyến thông tin'})
    assert calls and reply.status_code == 200
    assert reply.json()['sources'] == []
    assert reply.json()['status'] != 'answered'


def test_deleted_account_inflight_chat_cannot_write_to_reused_user_id(client):
    with client.app.state.db() as db:
        db.execute("UPDATE users SET role='reader'")
    victim = client.get('/api/auth/me').json()['user']
    copied_cookie = client.cookies.get('library_session')
    replacement = TestClient(client.app, headers=HEADERS)
    replacement.cookies.set('library_session', copied_cookie)
    def account_replaced(message, history=None):
        assert replacement.request('DELETE', '/api/auth/me', json={'password': PASSWORD}).status_code == 200
        assert replacement.post('/api/auth/register', json={'name': 'Different reader', 'email': 'different@example.test', 'password': PASSWORD}).status_code == 201
        return {'answer': 'Synthetic answer', 'status': 'answered', 'sources': [], 'suggestions': [], 'mode': 'faq'}
    client.app.state.answer = account_replaced
    reply = client.post('/api/chat', json={'message': 'Victim private message that must disappear on account deletion'})
    assert replacement.get('/api/auth/me').json()['user']['email'] != victim['email']
    assert replacement.get('/api/conversations').json() == []
    assert reply.status_code in (401, 409)


def test_unset_provider_health_matches_actual_generation_behavior(client, monkeypatch):
    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={'message': {'content': '{"answer":"Evidence","source_ids":[1]}'}})
    monkeypatch.setattr(llm_service, 'client', lambda: httpx.Client(transport=httpx.MockTransport(handle)))
    reported = client.get('/health').json()['capabilities']['llm_provider']
    llm_service.generate_answer('Question', [{'id': 1, 'answer': 'Evidence'}])
    assert bool(calls) == (reported == 'ollama')


def replace_account_during_password_check(client, monkeypatch):
    with client.app.state.db() as db:
        db.execute("UPDATE users SET role='reader'")
        old_hash = db.execute('SELECT password_hash FROM users').fetchone()[0]
    replacement = TestClient(client.app, headers=HEADERS)
    replacement.cookies.set('library_session', client.cookies.get('library_session'))
    original_verify = account_auth.password_hash.verify
    replaced = []
    def verify(password, hashed):
        valid = original_verify(password, hashed)
        if hashed == old_hash and not replaced:
            replaced.append(True)
            assert replacement.request('DELETE', '/api/auth/me', json={'password': PASSWORD}).status_code == 200
            assert replacement.post('/api/auth/register', json={'name': 'Different reader', 'email': 'different@example.test', 'password': PASSWORD}).status_code == 201
        return valid
    monkeypatch.setattr(account_auth.password_hash, 'verify', verify)
    return replacement


def test_login_cannot_authenticate_new_account_reusing_deleted_id(client, monkeypatch):
    replacement = replace_account_during_password_check(client, monkeypatch)
    response = client.post('/api/auth/login', json={'email': 'review@example.test', 'password': PASSWORD})
    assert replacement.get('/api/auth/me').status_code == 200
    assert response.status_code in (401, 409)
    assert client.get('/api/auth/me').status_code == 401


def test_stale_account_delete_cannot_delete_replacement_account(client, monkeypatch):
    replacement = replace_account_during_password_check(client, monkeypatch)
    response = client.request('DELETE', '/api/auth/me', json={'password': PASSWORD})
    assert replacement.get('/api/auth/me').status_code == 200
    assert response.status_code in (401, 409)
