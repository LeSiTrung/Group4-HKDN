import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as client:
        client.post('/api/auth/register', json={'name': 'Pagination operator', 'email': 'pagination@example.test', 'password': 'pagination-test-password'})
        with client.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
            db.execute('DELETE FROM books')
            db.executemany('INSERT INTO books(title,author,subjects,source_url,checked_at,published) VALUES (?,?,?,?,?,?)',
                           [(f'Tài liệu {index}', 'Nguyễn Văn An', 'Điện tử', f'https://lic.ut.edu.vn/pagination/{index}', '2026-10-28', index != 45) for index in range(1, 46)])
        yield client


def test_admin_list_is_bounded_ordered_and_includes_drafts(client):
    first = client.get('/api/admin/books').json()
    assert (first['total'], first['page'], first['page_size']) == (45, 1, 20)
    assert len(first['items']) == 20
    assert first['items'][0]['title'] == 'Tài liệu 45'
    assert first['items'][0]['published'] is False
    second = client.get('/api/admin/books', params={'page': 2}).json()
    assert len(second['items']) == 20
    assert second['items'][0]['title'] == 'Tài liệu 25'
    assert not {row['id'] for row in first['items']} & {row['id'] for row in second['items']}
    assert client.get('/api/catalog/' + str(first['items'][0]['id'])).status_code == 404


@pytest.mark.parametrize('query,total', [('TÀI LIỆU 4', 7), ('NGUYỄN VĂN AN', 45), ('ĐIỆN TỬ', 45), ('%', 0), ('_', 0), ("' OR 1=1 --", 0)])
def test_search_uses_unicode_substrings_and_literal_bound_parameters(client, query, total):
    result = client.get('/api/admin/books', params={'q': query, 'page_size': 2}).json()
    assert result['total'] == total
    assert len(result['items']) == min(2, total)


def test_empty_and_huge_pages_are_clamped_without_sqlite_overflow(client):
    result = client.get('/api/admin/books', params={'page': 10**30}).json()
    assert (result['page'], len(result['items'])) == (3, 5)
    result = client.get('/api/admin/books', params={'q': 'missing', 'page': 10**30}).json()
    assert result == {'items': [], 'total': 0, 'page': 1, 'page_size': 20}


def test_delete_and_import_reload_the_filtered_last_page(client):
    params = {'q': 'Tài liệu', 'page': 3}
    for row in client.get('/api/admin/books', params=params).json()['items']:
        assert client.delete(f"/api/admin/books/{row['id']}").status_code == 200
    result = client.get('/api/admin/books', params=params).json()
    assert (result['total'], result['page'], len(result['items'])) == (40, 2, 20)
    imported = {'title': 'Tài liệu nhập', 'source_url': 'https://lic.ut.edu.vn/pagination/import', 'checked_at': '2026-10-28', 'published': False}
    assert client.post('/api/admin/books/import', json={'items': [imported]}).status_code == 201
    result = client.get('/api/admin/books', params=params).json()
    assert (result['total'], result['page'], len(result['items'])) == (41, 3, 1)


@pytest.mark.parametrize('params', [{'page': 0}, {'page_size': 0}, {'page_size': 51}, {'q': 'x'*501}])
def test_query_bounds_are_validated(client, params):
    assert client.get('/api/admin/books', params=params).status_code == 422


def test_admin_list_still_requires_admin(client):
    with client.app.state.db() as db:
        db.execute("UPDATE users SET role='reader'")
    assert client.get('/api/admin/books').status_code == 403
    client.cookies.clear()
    assert client.get('/api/admin/books').status_code == 401
