import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import BookInput,save_book,search_books,search_local
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS','false')
    monkeypatch.setenv('LLM_PROVIDER','none')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            for i,(title,author,description,kind,published) in enumerate([
                ('Python cơ bản','Nguyễn Văn An','','digital',True),
                ('Python nâng cao','Nguyễn Văn Anh','Nguyễn Văn An','digital',True),
                ('Học Python','Trần Bình; Nguyễn Văn An','','books',True),
                ('Bản nháp','Nguyễn Văn An','','digital',False),
            ]):
                save_book(db,BookInput(title=title,author=author,description=description,kind=kind,published=published,
                    year='2020',source_url=f'https://lic.ut.edu.vn/synthetic-field-{i}',checked_at=today()))
        yield client


def test_author_field_preserves_name_words_boundaries_and_coauthors(client):
    rows=search_local(client.app.state.db,'nguyen van an',field='author')
    assert {r['title'] for r in rows}=={'Python cơ bản','Học Python'}
    assert [r['title'] for r in search_local(client.app.state.db,'Nguyễn Văn An','digital',field='author')]==['Python cơ bản']
    assert [r['title'] for r in search_local(client.app.state.db,'van anh',field='author')]==['Python nâng cao']


def test_title_field_and_exact_title_priority_do_not_match_abstracts(client):
    rows=search_local(client.app.state.db,'python co ban',field='title')
    assert [r['title'] for r in rows]==['Python cơ bản']
    assert search_local(client.app.state.db,'nguyen van an',field='title')==[]


def test_structured_miss_never_becomes_unrelated_semantic_result(client,monkeypatch):
    client.app.state.settings.testing=False
    monkeypatch.setenv('ENABLE_VECTORS','true')
    monkeypatch.setattr(client.app.state.vectors,'search',lambda *a,**k:pytest.fail('Structured lookup must not broaden to semantic results'))
    assert search_books(client.app.state,'Không có tác giả này',field='author')==[]


def test_api_enforces_fields_and_does_not_silently_fallback_to_opac(client,monkeypatch):
    from app.api import library
    monkeypatch.setattr(library,'search_catalog',lambda *a,**k:pytest.fail('No upstream field contract'))
    result=client.get('/api/catalog',params={'q':'Nguyễn Văn An','field':'author'}).json()
    assert result['source']=='local' and result['total']==2
    assert client.get('/api/catalog',params={'q':'Missing','field':'author'}).json()['total']==0
    assert client.get('/api/catalog',params={'q':'Python','field':'invalid'}).status_code==422
    assert client.get('/api/catalog',params={'q':'Python','field':'title','source':'opac'}).status_code==422


@pytest.mark.parametrize('question',['Tìm sách của Nguyễn Văn An','Tìm tài liệu theo tác giả Nguyễn Văn An','Sách của Nguyễn Văn An'])
def test_chat_author_requests_search_only_author_metadata(client,question):
    result=client.post('/api/chat',json={'message':question}).json()
    assert result['status']=='answered'
    assert {r['title'] for r in result['books']}=={'Python cơ bản','Học Python'}
    assert len(result['sources'])==2


def test_author_filter_survives_persisted_context_without_old_user_turn(client):
    question='Tìm tài liệu của tác giả Nguyễn Văn Anh'
    result=client.post('/api/chat',json={'message':question}).json()
    history=[{'role':'assistant','content':'Previous response','context_query':question}]
    # Server-loaded history carries context_query; use service directly for this internal field.
    from app.services.assistant import answer_question
    follow=answer_question(client.app.state,'Năm xuất bản?',history)
    assert follow['status']=='answered'
    assert [r['title'] for r in follow['books']]==['Python nâng cao']
    assert '2020' in follow['answer']


def test_exact_title_ranks_above_other_fields_even_when_author_terms_boost_other_record(client):
    with client.app.state.db() as db:
        save_book(db,BookInput(title='Python cơ bản mở rộng',author='Python cơ bản',kind='digital',published=True,
            source_url='https://lic.ut.edu.vn/synthetic-exact-title',checked_at=today()))
    assert search_local(client.app.state.db,'Python cơ bản')[0]['title']=='Python cơ bản'


def test_related_books_use_author_metadata_instead_of_name_mentions(client):
    row=search_local(client.app.state.db,'Python cơ bản',field='title')[0]
    detail=client.get('/api/catalog/'+str(row['id'])).json()
    assert [r['title'] for r in detail['related']]==['Học Python']


@pytest.mark.parametrize('author_interpretation',[False,True])
@pytest.mark.parametrize('prefix',['Tìm sách','Sách'])
def test_author_syntax_does_not_hide_a_real_title_beginning_with_cua(client,author_interpretation,prefix):
    with client.app.state.db() as db:
        save_book(db,BookInput(title='Của chuột và người',author='John Steinbeck',published=True,
            source_url='https://lic.ut.edu.vn/synthetic-cua-title',checked_at=today()))
        if author_interpretation:
            save_book(db,BookInput(title='Một tài liệu khác',author='Chuột và người',published=True,
                source_url='https://lic.ut.edu.vn/synthetic-cua-author',checked_at=today()))
    result=client.post('/api/chat',json={'message':prefix+' Của chuột và người'}).json()
    assert result['status']==('clarify' if author_interpretation else 'answered')
    assert any(row['title']=='Của chuột và người' for row in result['books'])
