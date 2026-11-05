from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app


HEADERS = {'X-Requested-With': 'LibraryAssistant'}
QUESTION = 'vậy bạn có thể đăng kí mượn sách giúp tôi được không'
PATH = '/api/demo/reservations'


def register(client, email):
    response = client.post('/api/auth/register', json={
        'email': email, 'name': 'Bạn đọc thử', 'password': 'synthetic-demo-password',
    })
    assert response.status_code == 201


def test_sample_stock_and_reservations_are_private_and_atomic(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS', 'true')
    with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as first:
        assert first.get(PATH).status_code == 401
        with TestClient(first.app, headers=HEADERS) as second:
            register(first, 'one@example.test')
            register(second, 'two@example.test')
            books = first.get(PATH).json()['books']
            book_id = next(book['id'] for book in books if book['available'] == 1)
            route = f'{PATH}/{book_id}'
            assert first.put(f'{PATH}/999999').status_code == 404
            with ThreadPoolExecutor(2) as executor:
                statuses = list(executor.map(lambda client: client.put(route).status_code, (first, second)))
            assert sorted(statuses) == [200, 409]
            winner, other = (first, second) if statuses[0] == 200 else (second, first)
            assert winner.put(route).status_code == 200
            assert other.delete(route).status_code == 204
            assert other.put(route).status_code == 409
            assert not any(book['reserved'] for book in other.get(PATH).json()['books'])
            assert winner.delete(route).status_code == 204
            assert other.put(route).status_code == 200


def test_chat_routes_action_to_enabled_demo_and_explains_disabled_mode(tmp_path, monkeypatch):
    for enabled in ('true', 'false'):
        monkeypatch.setenv('ENABLE_DEMO_RESERVATIONS', enabled)
        with TestClient(create_app(tmp_path, testing=True), headers=HEADERS) as client:
            response = client.post('/api/chat', json={'message': QUESTION}).json()
            assert not response['books']
            assert response['mode'] == ('demo_reservation' if enabled == 'true' else 'faq')
            if enabled == 'false':
                assert client.get(PATH).status_code == 404
