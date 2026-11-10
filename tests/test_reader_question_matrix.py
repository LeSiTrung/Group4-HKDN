import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import BookInput, save_book
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            for number,language in enumerate(('C','C++','C#','Python','Java'),1):
                url=f'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId={900+number}'
                row=save_book(db,BookInput(title=f'Giáo trình lập trình {language} căn bản',author=f'Tác giả thử {number}',
                    year=str(2020+number),subjects=language,description='Dành cho người mới bắt đầu.',source_url=url,checked_at=today(),published=True))
                db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                    (row['id'],url,today(),'b'*64,language,f'Nội dung thử riêng {language}.',f'Người học {language}.'))
        yield client


@pytest.mark.parametrize('language',['C','C++','C#'])
@pytest.mark.parametrize('field',['all','title','smart'])
def test_programming_language_symbols_do_not_match_a_different_language(client,language,field):
    response=client.get('/api/catalog',params={'q':language,'field':field,'source':'local'}).json()
    assert [book['title'] for book in response['items']]==[f'Giáo trình lập trình {language} căn bản']


@pytest.mark.parametrize('language',['C++','C#'])
@pytest.mark.parametrize('message',[
    'Tìm sách {language}', 'Tìm theo nhan đề Giáo trình lập trình {language} căn bản',
    'Tóm tắt sách “Giáo trình lập trình {language} căn bản”', 'Gợi ý sách {language} cho người mới',
])
def test_chat_keeps_symbols_in_lookup_summary_and_recommendations(client,language,message):
    response=client.post('/api/chat',json={'message':message.format(language=language)}).json()
    assert response['status']=='answered',response
    assert [book['title'] for book in response['books']]==[f'Giáo trình lập trình {language} căn bản']
    if message.startswith('Tóm tắt'):
        assert f'Nội dung thử riêng {language}.' in response['answer']


@pytest.mark.parametrize('message,facts,status',[
    ('Tác giả và năm xuất bản của cuốn đó?',['Tác giả thử 4','2024'],'answered'),
    ('Tóm tắt và đối tượng đọc của cuốn đó?',['Nội dung thử riêng Python.','Người học Python.'],'answered'),
    ('Tác giả, năm xuất bản và ISBN của cuốn đó?',['Tác giả thử 4','2024','ISBN','chưa xác nhận'],'needs_confirmation'),
])
def test_multiple_book_attributes_are_not_silently_dropped(client,message,facts,status):
    first=client.post('/api/chat',json={'message':'Tìm sách Python'}).json()
    response=client.post('/api/chat',json={'message':message,'history':[
        {'role':'user','content':'Tìm sách Python'},
        {'role':'assistant','content':first['answer'],'book_ids':[book['id'] for book in first['books']]},
    ]}).json()
    assert response['status']==status,response
    assert all(fact in response['answer'] for fact in facts),response
    assert [book['id'] for book in response['books']]==[first['books'][0]['id']]


@pytest.mark.parametrize('message',[
    'Không, tôi muốn tìm sách Java', 'Ý tôi là tìm sách Java', 'Tôi hỏi nhầm, tìm sách Java giúp tôi',
])
def test_explicit_reader_correction_replaces_the_old_book_topic(client,message):
    response=client.post('/api/chat',json={'message':message,'history':[
        {'role':'user','content':'Tìm sách Python'}, {'role':'assistant','content':'Các sách Python.'},
    ]}).json()
    assert response['status']=='answered',response
    assert [book['title'] for book in response['books']]==['Giáo trình lập trình Java căn bản']


@pytest.mark.parametrize('output,expected',[('C#',None),('C',None),('C++','C++')])
def test_local_topic_extraction_does_not_change_programming_language(monkeypatch,output,expected):
    from app.services import llm_service
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    monkeypatch.setattr(llm_service,'_generate',lambda *args:{'answer':output})
    assert llm_service.extract_book_topic('Gợi ý sách C++ cho người mới')==expected


def test_mixed_metadata_dates_keep_both_provenances(client):
    first=client.post('/api/chat',json={'message':'Tìm sách Python'}).json()
    chosen=first['books'][0]
    with client.app.state.db() as db:
        db.execute('UPDATE book_marc SET checked_at=? WHERE book_id=?',('2026-10-28',chosen['id']))
    result=client.post('/api/chat',json={'message':'Tác giả và tóm tắt của cuốn đó?','history':[
        {'role':'assistant','content':first['answer'],'book_ids':[chosen['id']]},
    ]}).json()
    assert 'Tác giả thử 4' in result['answer'] and 'Nội dung thử riêng Python.' in result['answer']
    assert {source['checked_at'] for source in result['sources']}=={today().isoformat(),'2026-10-28'}


def test_multiple_attributes_of_a_new_quoted_title_replace_the_prior_book(client):
    first=client.post('/api/chat',json={'message':'Tìm sách Python'}).json()
    result=client.post('/api/chat',json={'message':'Tác giả và năm xuất bản của sách “Giáo trình lập trình Java căn bản” là gì?',
        'history':[{'role':'assistant','content':first['answer'],'book_ids':[first['books'][0]['id']]}]}).json()
    assert result['status']=='answered' and 'Tác giả thử 5' in result['answer'] and '2025' in result['answer']
    assert [book['title'] for book in result['books']]==['Giáo trình lập trình Java căn bản']


@pytest.mark.parametrize('message',[
    'Ý tôi là tìm theo nhan đề Giáo trình lập trình Java căn bản',
    'Tìm sách Java giúp tôi', 'Tìm sách Java trên OPAC', 'Tìm sách Java tại thư viện',
])
def test_lookup_corrections_and_courtesy_do_not_become_search_terms(client,message):
    response=client.post('/api/chat',json={'message':message}).json()
    assert response['status']=='answered',response
    assert [book['title'] for book in response['books']]==['Giáo trình lập trình Java căn bản']


@pytest.mark.parametrize('message',['Không tìm sách Python','Đừng tìm sách Java','Tôi không muốn tìm sách Python'])
def test_negated_lookup_is_not_executed(client,message):
    response=client.post('/api/chat',json={'message':message}).json()
    assert response['status']=='clarify' and not response['books'],response


def test_missing_search_results_is_a_guidance_question_not_a_negated_command(client):
    response=client.post('/api/chat',json={'message':'Không tìm thấy sách Python trên OPAC'}).json()
    assert response['mode']=='faq' and not response['books']
    assert 'kết quả' in response['answer']


@pytest.mark.parametrize('language',['C','C++','C#'])
def test_missing_language_is_not_replaced_by_a_shared_programming_topic(client,language):
    with client.app.state.db() as db:
        db.execute('UPDATE books SET published=0 WHERE title=?',(f'Giáo trình lập trình {language} căn bản',))
    response=client.post('/api/chat',json={'message':f'Tìm sách lập trình {language}'}).json()
    assert response['status']=='not_found' and not response['books'],response


def test_semantic_overlap_cannot_replace_an_explicit_language_symbol(client,monkeypatch):
    from app.services.catalog import search_books
    with client.app.state.db() as db:
        db.execute("UPDATE books SET published=0 WHERE title LIKE '%C++%'")
    client.app.state.settings.testing=False
    monkeypatch.setenv('ENABLE_VECTORS','true')
    monkeypatch.setattr(client.app.state.vectors,'prepare_books',lambda load:'ready')
    monkeypatch.setattr(client.app.state.vectors,'search',lambda query,rows,**kwargs:[(row,.99) for row in rows])
    assert search_books(client.app.state,'lập trình C++')==[]
