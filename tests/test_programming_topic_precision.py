import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.catalog import BookInput, save_book, search_books
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            for number,(title,subjects,author,summary) in enumerate([
                ('Lập trình C cơ bản','Ngôn ngữ C','Người viết A',''),
                ('Nhập môn lập trình','Tin học','Người viết B','Hướng dẫn lập trình C và các cấu trúc điều khiển.'),
                ('C++ Primer','Computer science; C++','Người viết D',''),
                ('Windows Forms với C#','Công nghệ thông tin; C#','Người viết E',''),
                ('Thiết kế tuyến đường qua A - C','Xây dựng cầu đường','Người viết F',''),
                ('Thiết kế tàu /$c','Đóng tàu','Người viết G',''),
                ('Vitamin C và dinh dưỡng','Y học','Người viết H',''),
                ('Sản phẩm vitamin C++','Dinh dưỡng','Người viết I',''),
                ('Sản phẩm khử khuẩn C#','Hóa học','Người viết K',''),
                ('Phân nhóm mạng loại C','Công nghệ thông tin','Người viết L',''),
                ('Thiết kế cầu khác','Xây dựng','C',''),
            ],1):
                url=f'https://lic.ut.edu.vn/synthetic-language-topic/{number}/'
                row=save_book(db,BookInput(title=title,subjects=subjects,author=author,
                    source_url=url,checked_at=today(),published=True))
                if summary:
                    db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',(row['id'],url,today(),'a'*64,subjects,summary,''))
        yield client


@pytest.mark.parametrize('field',['all','title','smart'])
@pytest.mark.parametrize('language,titles',[
    ('C',{'Lập trình C cơ bản','Nhập môn lập trình'}),
    ('C++',{'C++ Primer'}),('C#',{'Windows Forms với C#'}),
])
def test_language_topic_requires_programming_evidence(client,field,language,titles):
    if field=='title' and language=='C':
        titles={'Lập trình C cơ bản'}
    response=client.get('/api/catalog',params={'q':language,'field':field,'source':'local'}).json()
    assert {row['title'] for row in response['items']}==titles


@pytest.mark.parametrize('message',['Tìm sách C','Tìm sách lập trình C','Gợi ý sách C cho người mới'])
def test_chat_does_not_recommend_letter_matches_as_programming(client,message):
    response=client.post('/api/chat',json={'message':message}).json()
    assert response['books']
    assert {row['title'] for row in response['books']}<={'Lập trình C cơ bản','Nhập môn lập trình'}


@pytest.mark.parametrize('query',['Vitamin C','Thiết kế tuyến đường qua A - C'])
def test_explicit_non_programming_queries_are_preserved(client,query):
    response=client.get('/api/catalog',params={'q':query,'field':'title','source':'local'}).json()
    assert len(response['items'])==1 and query in response['items'][0]['title']


def test_author_initial_search_keeps_its_explicit_field(client):
    response=client.get('/api/catalog',params={'q':'C','field':'author','source':'local'}).json()
    assert [row['title'] for row in response['items']]==['Thiết kế cầu khác']


def test_semantics_cannot_reintroduce_non_programming_c_matches(client,monkeypatch):
    with client.app.state.db() as db:
        db.execute("UPDATE books SET published=0 WHERE title IN ('Lập trình C cơ bản','Nhập môn lập trình')")
    client.app.state.settings.testing=False
    monkeypatch.setenv('ENABLE_VECTORS','true')
    monkeypatch.setattr(client.app.state.vectors,'prepare_books',lambda load:'ready')
    monkeypatch.setattr(client.app.state.vectors,'search',lambda query,rows,**kwargs:[(row,.99) for row in rows])
    assert search_books(client.app.state,'lập trình C')==[]
