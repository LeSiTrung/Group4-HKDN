import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import BookInput, save_book
from app.services.knowledge import KnowledgeInput, insert_knowledge, today


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            for number,title in enumerate(['Python thực hành A','Python thực hành B','Java nhập môn'],1):
                url=f'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId={800+number}'
                row=save_book(db,BookInput(title=title,author=f'Tác giả mẫu {number}',year=str(2020+number),
                    subjects=title,source_url=url,checked_at=today(),published=True))
                db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                    (row['id'],url,today(),'a'*64,title,f'Nội dung mẫu riêng {number}.',f'Đối tượng mẫu {number}.'))
        yield client


def register(client,email='memory@example.test'):
    assert client.post('/api/auth/register',json={'name':'Memory test','email':email,'password':'memory-test-password-123'}).status_code==201


def turn(client,history,message,cid=None):
    payload={'message':message,'history':history[-6:]}
    if cid:
        payload['conversation_id']=cid
    response=client.post('/api/chat',json=payload)
    assert response.status_code==200,response.text
    data=response.json()
    history.extend([{'role':'user','content':message},
        {'role':'assistant','content':data['answer'][:2000],'book_ids':[book['id'] for book in data['books'][:5]]}])
    return data


@pytest.mark.parametrize('guest',[True,False])
def test_selected_book_survives_consecutive_attributes_beyond_the_original_search_window(client,guest):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    chosen=result['books'][1]
    for question,fact,status in [
        ('Cuốn thứ hai do ai viết?',chosen['author'],'answered'),
        ('Xuất bản năm nào?',chosen['year'],'answered'),
        ('Tóm tắt cuốn đó','Nội dung mẫu riêng 2.','answered'),
        ('Đối tượng đọc của cuốn đó?','Đối tượng mẫu 2.','answered'),
        ('ISBN của cuốn đó là gì?','chưa xác nhận','needs_confirmation'),
        ('Vậy cuốn đó do ai viết?',chosen['author'],'answered'),
    ]:
        result=turn(client,history,question,result['conversation_id'])
        assert result['status']==status,result
        assert [book['id'] for book in result['books']]==[chosen['id']],result
        assert fact in result['answer']
        assert result['sources'][0]['url']==chosen['url']


@pytest.mark.parametrize('guest',[True,False])
def test_courtesy_turn_does_not_erase_the_selected_book(client,guest):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    chosen=result['books'][1]
    for question in ['Cuốn thứ hai do ai viết?','Cảm ơn bạn','Xuất bản năm nào?']:
        result=turn(client,history,question,result['conversation_id'])
    assert [book['id'] for book in result['books']]==[chosen['id']]
    assert chosen['year'] in result['answer']


@pytest.mark.parametrize('guest',[True,False])
@pytest.mark.parametrize('question,fact,status',[
    ('Nó nói về gì?','Nội dung mẫu riêng 2.','answered'),
    ('Nó dành cho ai?','Đối tượng mẫu 2.','answered'),
    ('Cuốn ấy có nội dung gì?','Nội dung mẫu riêng 2.','answered'),
    ('Cho tôi biết tác giả của nó','Tác giả mẫu 2','answered'),
    ('Vậy nó xuất bản năm nào?','2022','answered'),
    ('Vậy cho mình biết năm xuất bản','2022','answered'),
    ('ISBN của nó là gì?','chưa xác nhận','needs_confirmation'),
])
def test_natural_pronouns_and_polite_attribute_followups_keep_the_selected_book(client,guest,question,fact,status):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    chosen=result['books'][1]
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    result=turn(client,history,question,result['conversation_id'])
    assert result['status']==status and fact in result['answer'],result
    assert [book['id'] for book in result['books']]==[chosen['id']]
    assert result['sources'][0]['url']==chosen['url']


@pytest.mark.parametrize('guest',[True,False])
@pytest.mark.parametrize('question,facts',[
    ('Bạn có thể cho mình biết năm xuất bản được không?',['2022']),
    ('Có thể cho tôi biết tác giả được không?',['Tác giả mẫu 2']),
    ('Vui lòng cho em biết tác giả và năm xuất bản',['Tác giả mẫu 2','2022']),
    ('Làm ơn cho mình biết tóm tắt và đối tượng đọc được không?',['Nội dung mẫu riêng 2.','Đối tượng mẫu 2.']),
])
def test_polite_attribute_requests_reuse_selected_book_instead_of_search_help(client,guest,question,facts):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    chosen=result['books'][1]
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    result=turn(client,history,question,result['conversation_id'])
    assert result['status']=='answered',result
    assert [book['id'] for book in result['books']]==[chosen['id']],result
    assert all(fact in result['answer'] for fact in facts),result
    assert result['sources'][0]['url']==chosen['url']


def test_polite_attribute_question_without_a_book_asks_for_the_title(client):
    result=turn(client,[],'Bạn có thể cho mình biết năm xuất bản được không?')
    assert result['status']=='clarify' and not result['books'],result
    assert not result['sources'],result


@pytest.mark.parametrize('guest',[True,False])
@pytest.mark.parametrize('question',[
    'Hướng dẫn tra cứu sách này theo tác giả trên OPAC',
    'Cách mượn sách này khi còn bản?',
])
def test_how_to_requests_keep_service_priority_after_a_book_selection(client,guest,question,monkeypatch):
    with client.app.state.db() as db:
        insert_knowledge(db,KnowledgeInput(title='Synthetic borrowing guide',question='Thủ tục mượn sách tại quầy',
            answer='Xuất trình thẻ và làm thủ tục tại quầy. Hướng dẫn thử nghiệm, không phải chính sách thực tế.',
            category='borrowing_guide',source_title='Synthetic library guide',source_url='https://lic.ut.edu.vn/synthetic-memory-borrowing/',
            checked_at=today(),status='reviewed_public',published=True))
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    def unexpected(*args,**kwargs):
        raise AssertionError('A how-to request must not trigger a live availability check')
    monkeypatch.setattr('app.services.assistant.get_availability',unexpected)
    result=turn(client,history,question,result['conversation_id'])
    assert result['status']=='answered' and result['mode']=='faq',result
    assert not result['books'] and result['sources']


@pytest.mark.parametrize('guest',[True,False])
@pytest.mark.parametrize('boundary',[
    'Tôi cần chuẩn bị gì để mượn sách?', 'Viết mã trò chơi cho tôi',
    'Tìm sách zzzmissingmemory999', 'Cuốn thứ 9 do ai viết?',
])
def test_new_or_unresolved_topic_does_not_reuse_the_previous_selection(client,guest,boundary):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    old_urls={source['url'] for source in result['sources']}
    for question in ['Cuốn thứ hai do ai viết?',boundary,'Xuất bản năm nào?']:
        result=turn(client,history,question,result['conversation_id'])
    assert result['status'] in ('clarify','not_found'),result
    assert not result['books'] and not any(source['url'] in old_urls for source in result['sources'])


@pytest.mark.parametrize('guest',[True,False])
def test_topic_switch_replaces_the_selected_book(client,guest):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    result=turn(client,history,'Tìm sách Java',result['conversation_id'])
    chosen=result['books'][0]
    result=turn(client,history,'Xuất bản năm nào?',result['conversation_id'])
    assert [book['id'] for book in result['books']]==[chosen['id']]
    assert chosen['year'] in result['answer']


@pytest.mark.parametrize('guest',[True,False])
@pytest.mark.parametrize('question,fact',[
    ('Tác giả của sách “Java nhập môn” là ai?','Tác giả mẫu 3'),
    ('Sách “Java nhập môn” xuất bản năm nào?','2023'),
    ('Bạn có thể cho mình biết tác giả của sách “Java nhập môn” được không?','Tác giả mẫu 3'),
    ('Cho tôi biết tóm tắt của sách “Java nhập môn”','Nội dung mẫu riêng 3.'),
])
def test_explicit_quoted_book_overrides_a_previous_selection(client,guest,question,fact):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    result=turn(client,history,question,result['conversation_id'])
    assert result['status']=='answered' and fact in result['answer'],result
    assert [book['title'] for book in result['books']]==['Java nhập môn']


@pytest.mark.parametrize('guest',[True,False])
@pytest.mark.parametrize('question',[
    'ISBN của sách “Java nhập môn” là gì?',
    'Nhà xuất bản của sách “Java nhập môn” là gì?',
    'Vị trí kệ của sách “Java nhập môn” ở đâu?',
])
def test_unknown_attribute_of_a_named_book_does_not_reuse_the_previous_book(client,guest,question):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    result=turn(client,history,question,result['conversation_id'])
    assert result['status']=='needs_confirmation',result
    assert [book['title'] for book in result['books']]==['Java nhập môn'],result
    assert all('intItemId=803' in source['url'] for source in result['sources']),result
    result=turn(client,history,'Xuất bản năm nào?',result['conversation_id'])
    assert result['status']=='answered' and '2023' in result['answer'],result
    assert [book['title'] for book in result['books']]==['Java nhập môn'],result


def test_availability_for_a_quoted_title_checks_that_title_only(client,monkeypatch):
    calls=[]
    def unknown(url):
        calls.append(url)
        return {'status':'unknown','checked_at':None}
    monkeypatch.setattr('app.services.assistant.get_availability',unknown)
    history=[]
    turn(client,history,'Tìm sách Python')
    turn(client,history,'Cuốn thứ hai do ai viết?')
    result=turn(client,history,'Sách “Java nhập môn” còn bản không?')
    assert result['status']=='needs_confirmation',result
    assert [book['title'] for book in result['books']]==['Java nhập môn'],result
    assert calls==['https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=803']


def test_unknown_quoted_title_cannot_fall_back_to_an_old_book(client):
    history=[]
    turn(client,history,'Tìm sách Python')
    turn(client,history,'Cuốn thứ hai do ai viết?')
    result=turn(client,history,'ISBN của sách “zzzmissingbook999” là gì?')
    assert result['status']=='not_found' and not result['books'],result
    assert not any('intItemId=802' in source['url'] for source in result['sources']),result


@pytest.mark.parametrize('guest',[True,False])
def test_multiple_explicit_titles_require_clarification_instead_of_old_book_metadata(client,guest):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    result=turn(client,history,'ISBN của sách “Java nhập môn” và “Python thực hành A” là gì?',result['conversation_id'])
    assert result['status']=='clarify' and not result['books'] and not result['sources'],result
    result=turn(client,history,'Xuất bản năm nào?',result['conversation_id'])
    assert result['status']=='clarify' and not result['books'] and not result['sources'],result


@pytest.mark.parametrize('guest',[True,False])
def test_selected_metadata_is_reread_after_publication_changes(client,guest):
    if not guest:
        register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    with client.app.state.db() as db:
        db.execute('UPDATE books SET published=0 WHERE id=?',(result['books'][0]['id'],))
    result=turn(client,history,'Xuất bản năm nào?',result['conversation_id'])
    assert result['status']=='clarify',result
    assert not result['books'] and not result['sources']


def test_saved_memory_survives_relogin_and_is_private_to_the_owner(client):
    register(client)
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?',result['conversation_id'])
    cid=result['conversation_id']
    chosen=result['books'][0]
    client.post('/api/auth/logout')
    register(client,'other-memory@example.test')
    assert client.get(f'/api/conversations/{cid}').status_code==404
    assert client.post('/api/chat',json={'message':'Xuất bản năm nào?','conversation_id':cid}).status_code==404
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login',json={'email':'memory@example.test','password':'memory-test-password-123'}).status_code==200
    assert len(client.get(f'/api/conversations/{cid}').json()['messages'])==4
    result=turn(client,[],'Xuất bản năm nào?',cid)
    assert [book['id'] for book in result['books']]==[chosen['id']]
    assert chosen['year'] in result['answer']


def test_guest_new_conversation_has_no_previous_memory_or_persisted_history(client):
    history=[]
    result=turn(client,history,'Tìm sách Python')
    result=turn(client,history,'Cuốn thứ hai do ai viết?')
    assert result['conversation_id'] is None
    result=turn(client,[],'Xuất bản năm nào?')
    assert result['status']=='clarify' and not result['books']
    with client.app.state.db() as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]==0
