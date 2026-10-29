import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as c:
        c.post('/api/auth/register',json={'name':'Catalog operator','email':'catalog@example.test','password':'catalog-password-123'})
        with c.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
        yield c


def book(**changes):
    value={'title':'Python cho người mới','author':'Tác giả thử nghiệm','year':'2025','kind':'books','subjects':'Python; lập trình; người mới',
           'description':'Synthetic book fixture, not real library inventory.','source_url':'https://lic.ut.edu.vn/synthetic-book-test/',
           'checked_at':'2026-10-28','published':True}
    return {**value,**changes}


def test_admin_import_search_provenance_and_pagination(client):
    assert client.post('/api/admin/books/import',json={'items':[book(),book(title='Lập trình nâng cao',source_url='https://lic.ut.edu.vn/synthetic-advanced/')]}).status_code==201
    result=client.get('/api/catalog',params={'q':'python','source':'local','page_size':1}).json()
    assert result['source']=='local' and result['total']==2 and len(result['items'])==1
    assert result['items'][0]['checked_at']=='2026-10-28'
    assert 'availability' not in result['items'][0]
    assert client.get('/api/catalog',params={'q':'tac gia thu nghiem','source':'local'}).json()['total']==2


def test_import_is_atomic_and_drafts_are_not_searchable(client):
    assert client.post('/api/admin/books/import',json={'items':[book(),book(source_url='javascript:bad')]}).status_code==422
    assert client.get('/api/catalog',params={'q':'synthetic','source':'local'}).json()['total']==0
    created=client.post('/api/admin/books',json=book(published=False)).json()
    assert 'id' in created
    assert client.get('/api/catalog',params={'q':'python','source':'local'}).json()['total']==0
    assert client.get(f"/api/catalog/{created['id']}").status_code==404


def test_chat_search_followup_and_details_use_real_records(client):
    row=client.post('/api/admin/books',json=book()).json()
    reply=client.post('/api/chat',json={'message':'Tìm sách về Python'}).json()
    assert reply.get('books') and reply['books'][0]['id']==row['id']
    follow=client.post('/api/chat',json={'message':'Có cuốn nào dành cho người mới không?','conversation_id':reply['conversation_id']}).json()
    assert follow.get('books') and 'Python' in follow['books'][0]['title']
    history=client.get(f"/api/conversations/{reply['conversation_id']}").json()
    assert history['messages'][-1]['books'][0]['id']==row['id']
    detail=client.get(f"/api/catalog/{row['id']}").json()
    assert detail['title']==book()['title'] and 'availability' not in detail


def test_public_cannot_admin_import(client):
    client.post('/api/auth/logout')
    assert client.post('/api/admin/books/import',json={'items':[book()]}).status_code==401


def test_guest_followup_author_uses_retrieved_book_not_generic_faq(client):
    row=client.post('/api/admin/books',json=book()).json()
    client.post('/api/auth/logout')
    response=client.post('/api/chat',json={'message':'Cuốn đó của tác giả nào?', 'history':[{'role':'user','content':'Tìm sách về Python'}]})
    result=response.json()
    assert result['books'][0]['id']==row['id']
    assert book()['author'] in result['answer']


@pytest.mark.parametrize('question',['Cuốn đó còn bản nào không?','Cuốn đó còn sách để mượn không?'])
def test_guest_followup_cannot_invent_availability(client,question):
    client.post('/api/admin/books',json=book())
    client.post('/api/auth/logout')
    result=client.post('/api/chat',json={'message':question, 'history':[{'role':'user','content':'Tìm sách về Python'}]}).json()
    assert result['status']=='needs_confirmation'
    assert result['books']
    assert 'không' in result['answer'].lower()
