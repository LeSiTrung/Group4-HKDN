from fastapi.testclient import TestClient
import pytest
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as client:
        yield client


def test_blank_input_is_rejected(client):
    assert client.post('/api/chat', json={'message': '   '}).status_code == 422


def test_reader_can_register(client):
    response = client.post('/api/auth/register', json={'email': 'reader@example.com', 'name': 'Reader', 'password': 'A-secure-password-123'})
    assert response.status_code == 201
    assert response.json()['user']['role'] == 'reader'
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/auth/me').status_code == 200
    assert client.get('/api/admin/knowledge').status_code in (403,404)
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/me').status_code == 401


def test_csrf_and_large_body_rejected(client):
    assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/chat', content='x'*65537).status_code == 413
