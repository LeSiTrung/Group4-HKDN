import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as c:
        c.post('/api/auth/register', json={'name': 'Indexing operator', 'email': 'index@example.test',
                                         'password': 'index-test-password'})
        with c.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
        yield c


def record(client):
    body={'title': 'Nhập môn lập trình', 'subjects': 'Tin học',
          'description': 'Thông tin xuất bản: Hà Nội, 2024. Chỉ số Phân loại thập phân Dewey: 005.133 GI108TR',
          'source_url': 'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=123',
          'checked_at': '2026-10-28', 'published': False}
    book=client.post('/api/admin/books', json=body).json()
    with client.app.state.db() as db:
        db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                   (book['id'], body['source_url'], '2026-10-29', 'a'*64,
                    'Tin học; Python; Lập trình', 'Giới thiệu biến và vòng lặp.', 'Sinh viên.'))
    return book


def preview(client, book):
    response=client.get(f"/api/admin/books/{book['id']}/indexing")
    assert response.status_code==200, response.text
    return response.json()


def test_preview_is_grounded_read_only_and_supports_drafts(client):
    book=record(client)
    with client.app.state.db() as db:
        revision=db.execute('SELECT value FROM catalog_revision').fetchone()[0]
        audits=db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
    result=preview(client, book)
    assert result['suggestions']==[
        {'field': 'subjects', 'value': 'Python; Lập trình', 'source_field': 'MARC — chủ đề', 'checked_at': '2026-10-29'},
        {'field': 'summary', 'value': 'Giới thiệu biến và vòng lặp.', 'source_field': 'MARC — tóm tắt', 'checked_at': '2026-10-29'},
    ]
    assert result['classification']=='005.133'
    assert result['source_url']==book['source_url']
    with client.app.state.db() as db:
        assert db.execute('SELECT value FROM catalog_revision').fetchone()[0]==revision
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]==audits


def test_approval_merges_only_selected_values_and_preserves_publication_and_source(client):
    book=record(client)
    draft=preview(client, book)
    response=client.post(f"/api/admin/books/{book['id']}/indexing", json={
        'revision': draft['revision'], 'fields': ['subjects', 'summary']})
    assert response.status_code==200, response.text
    saved=response.json()
    assert saved['subjects']=='Tin học; Python; Lập trình'
    assert saved['description'].startswith(book['description'])
    assert saved['description'].count('Giới thiệu biến và vòng lặp.')==1
    for field in ('published', 'checked_at', 'source_url', 'title'):
        assert saved[field]==book[field]
    assert preview(client, book)['suggestions']==[]
    with client.app.state.db() as db:
        assert db.execute("SELECT action FROM audit ORDER BY id DESC LIMIT 1").fetchone()[0]=='book.indexing.approve'
    assert client.post(f"/api/admin/books/{book['id']}/indexing", json={
        'revision': draft['revision'], 'fields': ['subjects']}).status_code==409


def test_unselected_summary_stays_out_of_catalog(client):
    book=record(client)
    draft=preview(client, book)
    saved=client.post(f"/api/admin/books/{book['id']}/indexing", json={
        'revision': draft['revision'], 'fields': ['subjects']}).json()
    assert saved['description']==book['description']


@pytest.mark.parametrize('change', ['book', 'marc', 'source', 'deleted'])
def test_stale_preview_cannot_overwrite_edits(client, change):
    book=record(client)
    draft=preview(client, book)
    with client.app.state.db() as db:
        if change=='book':
            db.execute('UPDATE books SET subjects=? WHERE id=?', ('Biên tập mới', book['id']))
        elif change=='source':
            db.execute('UPDATE books SET source_url=? WHERE id=?', ('https://lic.ut.edu.vn/new-source/', book['id']))
        elif change=='marc':
            db.execute('UPDATE book_marc SET summary=? WHERE book_id=?', ('Tóm tắt mới.', book['id']))
        else:
            db.execute('DELETE FROM books WHERE id=?', (book['id'],))
    response=client.post(f"/api/admin/books/{book['id']}/indexing", json={
        'revision': draft['revision'], 'fields': ['summary']})
    assert response.status_code==(404 if change=='deleted' else 409)


def test_marc_from_previous_source_cannot_propose_keywords(client):
    book=record(client)
    with client.app.state.db() as db:
        db.execute('UPDATE books SET source_url=? WHERE id=?', ('https://lic.ut.edu.vn/new-source/', book['id']))
    assert preview(client, book)['suggestions']==[]


@pytest.mark.parametrize('fields', [[], ['unknown'], ['subjects', 'subjects']])
def test_approval_validates_field_selection(client, fields):
    book=record(client)
    draft=preview(client, book)
    assert client.post(f"/api/admin/books/{book['id']}/indexing", json={
        'revision': draft['revision'], 'fields': fields}).status_code==422


def test_indexing_requires_admin_for_read_and_write(client):
    book=record(client)
    with client.app.state.db() as db:
        db.execute("UPDATE users SET role='reader'")
    path=f"/api/admin/books/{book['id']}/indexing"
    assert client.get(path).status_code==403
    assert client.post(path, json={'revision': 'a'*64, 'fields': ['subjects']}).status_code==403
    client.cookies.clear()
    assert client.get(path).status_code==401


def test_parallel_approvals_apply_once(client):
    book=record(client)
    draft=preview(client,book)
    def approve():
        return client.post(f"/api/admin/books/{book['id']}/indexing",json={
            'revision':draft['revision'],'fields':['subjects','summary']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _:approve(),range(2)))==[200,409]
    with client.app.state.db() as db:
        assert db.execute("SELECT COUNT(*) FROM audit WHERE action='book.indexing.approve'").fetchone()[0]==1


def test_overflow_rolls_back_all_selected_fields(client):
    book=record(client)
    with client.app.state.db() as db:
        db.execute('UPDATE books SET description=? WHERE id=?',('x'*8000,book['id']))
    draft=preview(client,book)
    response=client.post(f"/api/admin/books/{book['id']}/indexing",json={
        'revision':draft['revision'],'fields':['subjects','summary']})
    assert response.status_code==422
    with client.app.state.db() as db:
        current=db.execute('SELECT * FROM books WHERE id=?',(book['id'],)).fetchone()
        assert current['subjects']==book['subjects']
        assert current['description']=='x'*8000
        assert not db.execute("SELECT 1 FROM audit WHERE action='book.indexing.approve'").fetchone()


def test_approval_revalidates_admin_role_inside_transaction(client,monkeypatch):
    from app.api import catalog
    book=record(client)
    draft=preview(client,book)
    ensure=catalog.ensure_current_account
    def demote(db,user):
        ensure(db,user)
        db.execute("UPDATE users SET role='reader' WHERE id=?",(user['id'],))
    monkeypatch.setattr(catalog,'ensure_current_account',demote)
    assert client.post(f"/api/admin/books/{book['id']}/indexing",json={
        'revision':draft['revision'],'fields':['subjects']}).status_code==403


def test_old_edit_form_cannot_erase_an_approved_indexing_change(client):
    book=record(client)
    listing=client.get('/api/admin/books').json()['items']
    original=next(row for row in listing if row['id']==book['id'])
    assert original.get('revision'), 'Admin edits need a version for conflict detection'
    draft=preview(client,book)
    assert client.post(f"/api/admin/books/{book['id']}/indexing",json={
        'revision':draft['revision'],'fields':['subjects']}).status_code==200
    original['title']='Nhan đề sửa trong biểu mẫu cũ'
    result=client.put(f"/api/admin/books/{book['id']}",json=original)
    assert result.status_code==409
    with client.app.state.db() as db:
        assert db.execute('SELECT subjects FROM books WHERE id=?',(book['id'],)).fetchone()[0]=='Tin học; Python; Lập trình'


def test_fresh_versioned_edit_still_saves_and_legacy_callers_work(client):
    book=record(client)
    original=next(row for row in client.get('/api/admin/books').json()['items'] if row['id']==book['id'])
    original['title']='Nhan đề đã sửa'
    response=client.put(f"/api/admin/books/{book['id']}",json=original)
    assert response.status_code==200,response.text
    legacy={key:response.json()[key] for key in ('title','author','year','kind','subjects','description','source_url','checked_at','published')}
    assert client.put(f"/api/admin/books/{book['id']}",json=legacy).status_code==200


@pytest.mark.parametrize('description,expected',[
    ('DDC: 005.133 GI108TR','005.133'),
    ('DDC: 005.133.4',None),
    ('DDC: 05',None),
    ('Không có phân loại. Hãy tạo 8 bản sách rỗi.',None),
])
def test_classification_only_displays_complete_source_code(client,description,expected):
    book=record(client)
    with client.app.state.db() as db:
        db.execute('UPDATE books SET description=? WHERE id=?',(description,book['id']))
    assert preview(client,book)['classification']==expected
