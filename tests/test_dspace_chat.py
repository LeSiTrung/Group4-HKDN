import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import assistant
from app.services.catalog import BookInput,save_book
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS','false')
    monkeypatch.setenv('LLM_PROVIDER','none')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            save_book(db,BookInput(title='Nghiên cứu XML và xây dựng trang Web hỗ trợ khách hàng',
                author='Tác giả thử nghiệm',kind='digital',subjects='XML; Website',
                source_url='https://thuvienso.ut.edu.vn/items/0009688f-12f3-4902-9b95-7a31e878ee77',checked_at=today(),published=True))
        yield client


@pytest.mark.parametrize('kind',['luận văn','luận án','khóa luận','đồ án','giáo trình','bài giảng'])
def test_digital_document_search_uses_public_catalog(client,kind):
    result=client.post('/api/chat',json={'message':f'Tìm {kind} về XML hỗ trợ khách hàng'}).json()
    assert result['status']=='answered' and result['books']
    assert result['books'][0]['title'].startswith('Nghiên cứu XML')
    assert result['sources'][0]['url'].startswith('https://thuvienso.ut.edu.vn/items/')
    assert 'OPAC' not in result['answer']


@pytest.mark.parametrize('message',['Tìm luận văn khóa luận','Tim luan van khoa luan','Tìm luận văn và khóa luận'])
def test_document_types_without_a_topic_keep_the_digital_library_guide(client,monkeypatch,message):
    searches=[]
    monkeypatch.setattr(assistant,'search_books',lambda *args,**kwargs:searches.append(args[1]) or [])
    response=client.post('/api/chat',json={'message':message}).json()
    assert not searches
    assert response['status']=='answered' and not response['books']
    assert any(row['url']=='https://thuvienso.ut.edu.vn/home' for row in response['sources'])


def test_large_chat_lookup_requests_narrower_query_before_expensive_catalog_scan(client,monkeypatch):
    monkeypatch.setattr(assistant,'search_books',lambda *args,**kwargs:pytest.fail('Oversized lookup must not scan the catalog'))
    result=client.post('/api/chat',json={'message':'Tìm tài liệu về '+'XML khách hàng '*80}).json()
    assert result['status']=='clarify' and 'ngắn' in result['answer']


@pytest.mark.parametrize('selection,duplicate,expected',[
    ('Nghien cuu XML va xay dung trang Web ho tro khach hang',False,'answered'),
    ('XML hỗ trợ khách hàng',False,'clarify'),
    ('Nghiên cứu XML và xây dựng trang Web hỗ trợ khách hàng',True,'clarify'),
])
def test_followup_distinguishes_selected_full_title_from_ambiguous_results(client,selection,duplicate,expected):
    title='Nghiên cứu XML và xây dựng trang Web hỗ trợ khách hàng'
    with client.app.state.db() as db:
        save_book(db,BookInput(title=title if duplicate else title+' nâng cao',author='Tác giả khác',
            kind='digital',source_url='https://thuvienso.ut.edu.vn/items/11111111-1111-4111-8111-111111111111',
            checked_at=today(),published=True))
    response=client.post('/api/chat',json={'message':'Tác giả là ai?',
        'history':[{'role':'user','content':'Tìm tài liệu '+selection}]}).json()
    assert response['status']==expected
    if expected=='answered':
        assert 'Tác giả thử nghiệm' in response['answer'] and 'Tác giả khác' not in response['answer']
        assert len(response['books'])==len(response['sources'])==1


@pytest.mark.parametrize('selection,expected',[('học','clarify'),('Cơ học','answered')])
def test_full_title_selection_preserves_words_removed_by_keyword_search(client,selection,expected):
    with client.app.state.db() as db:
        for i,title in enumerate(['Cơ học','Học máy']):
            save_book(db,BookInput(title=title,author='Tác giả '+title,kind='digital',
                source_url=f'https://lic.ut.edu.vn/synthetic-collision-{i}',checked_at=today(),published=True))
    response=client.post('/api/chat',json={'message':'Tác giả là ai?',
        'history':[{'role':'user','content':'Tìm tài liệu '+selection}]}).json()
    assert response['status']==expected
    if expected=='answered':
        assert len(response['books'])==1 and response['books'][0]['title']=='Cơ học'


def test_selected_title_is_resolved_before_display_limit(client):
    with client.app.state.db() as db:
        for i,title in enumerate([f'Học máy phiên bản {n}' for n in range(6)]+['Cơ học']):
            save_book(db,BookInput(title=title,author='Tác giả kiểm thử',kind='digital',
                source_url=f'https://lic.ut.edu.vn/synthetic-display-limit-{i}',checked_at=today(),published=True))
    response=client.post('/api/chat',json={'message':'Tác giả là ai?',
        'history':[{'role':'user','content':'Tìm tài liệu Cơ học'}]}).json()
    assert response['status']=='answered' and len(response['books'])==1
    assert response['books'][0]['title']=='Cơ học'


def test_title_beginning_with_ve_is_not_changed_into_another_title(client):
    with client.app.state.db() as db:
        for i,title in enumerate(['Về cơ học','Cơ học']):
            save_book(db,BookInput(title=title,author=f'Tác giả {i}',kind='digital',
                source_url=f'https://lic.ut.edu.vn/synthetic-preposition-{i}',checked_at=today(),published=True))
    response=client.post('/api/chat',json={'message':'Tác giả là ai?',
        'history':[{'role':'user','content':'Tìm tài liệu Về cơ học'}]}).json()
    assert response['status']=='answered' and len(response['books'])==1
    assert response['books'][0]['title']=='Về cơ học' and 'Tác giả 0' in response['answer']
