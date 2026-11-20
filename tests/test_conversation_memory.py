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
        {'role':'assistant','content':data['answer'][:2000],'book_ids':[book['id'] for book in data['books'][:5]],
         'list_book_ids':data.get('list_book_ids',[])}])
    return data


@pytest.mark.parametrize('guest',[True,False])
def test_recommendation_suggestions_ask_about_the_displayed_results(client,guest):
    if not guest:
        register(client)
    history=[]
    response=turn(client,history,'Gợi ý sách Java')
    assert response['suggestions']==['Em mới học','Tóm tắt cuốn đầu tiên']
    filtered=turn(client,history,response['suggestions'][0],response['conversation_id'])
    assert [b['title'] for b in filtered['books']]==['Java nhập môn']
    assert filtered['suggestions']==['Tóm tắt cuốn đầu tiên']
    summary=turn(client,history,filtered['suggestions'][0],filtered['conversation_id'])
    assert summary['status']=='answered' and 'Nội dung mẫu riêng 3.' in summary['answer']
    assert not summary['suggestions']


@pytest.mark.parametrize('guest',[True,False])
def test_learning_level_followups_keep_subject_until_reader_changes_it(client,guest):
    if not guest:
        register(client)
    with client.app.state.db() as db:
        for number,title,subjects in [
            (901,'Bài giảng xác suất thống kê cơ bản','Xác suất thống kê'),
            (902,'Giáo trình xác suất thống kê nâng cao','Xác suất thống kê'),
            (903,'Bài giảng cấu trúc dữ liệu','Công nghệ thông tin'),
            (904,'Địa chất cơ sở','Địa chất'),
            (905,'Giáo trình nhập môn công nghệ thông tin','Công nghệ thông tin'),
        ]:
            save_book(db,BookInput(title=title,subjects=subjects,published=True,checked_at=today(),
                source_url=f'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId={number}'))
    history=[]
    first=turn(client,history,'tìm giúp tôi những cuốn sách để học môn xác suất thống kê')
    assert len(first['books'])==2
    cid=first['conversation_id']
    for question,expected in [
        ('Em mới học',['Bài giảng xác suất thống kê cơ bản']),
        ('Em mới học, có cuốn cơ bản không?',['Bài giảng xác suất thống kê cơ bản']),
        ('Em muốn học nâng cao',['Giáo trình xác suất thống kê nâng cao']),
        ('em học IT thì nên mượn quyển sách nào đây',['Giáo trình nhập môn công nghệ thông tin','Bài giảng cấu trúc dữ liệu']),
        ('Em mới học',['Giáo trình nhập môn công nghệ thông tin']),
    ]:
        response=turn(client,history,question,cid)
        assert sorted(book['title'] for book in response['books'])==sorted(expected),response
        assert response['books'][0]['recommendation_reason'] and response['sources']


def test_learning_level_without_previous_subject_asks_for_it(client):
    response=turn(client,[],'Em mới học')
    assert response['status']=='clarify' and not response['books']
    assert 'chủ đề' in response['answer']


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
def test_switch_between_positions_uses_original_search_list(client,guest):
    if not guest:
        register(client)
    history=[]
    listing=turn(client,history,'Tìm sách Python')
    cid=listing['conversation_id']
    first,second=listing['books']
    for question,wanted in [
        ('Tác giả cuốn thứ hai là ai?',second),
        ('Năm xuất bản?',second),
        ('Đối tượng đọc?',second),
        ('Tóm tắt cuốn đó',second),
        ('Còn cuốn đầu thì sao?',first),
        ('Tác giả và năm?',first),
    ]:
        reply=turn(client,history,question,cid)
        assert [book['id'] for book in reply['books']]==[wanted['id']],reply
        if question=='Tác giả và năm?':
            assert wanted['author'] in reply['answer'] and wanted['year'] in reply['answer']
    new_topic=turn(client,history,'Tìm sách Java',cid)
    reply=turn(client,history,'Cuốn đầu tiên là cuốn nào?',cid)
    assert [book['id'] for book in reply['books']]==[new_topic['books'][0]['id']],reply


@pytest.mark.parametrize('guest',[True,False])
def test_format_question_and_isbn_definition_keep_the_current_book(client,guest):
    if not guest:
        register(client)
    with client.app.state.db() as db:
        db.execute("UPDATE books SET kind='digital' WHERE title='Python thực hành A'")
    history=[]
    first=turn(client,history,'Tìm theo nhan đề Python thực hành A')
    cid=first['conversation_id']
    book=first['books'][0]
    reply=turn(client,history,'Có phải sách in không?',cid)
    assert reply['status']=='answered' and 'là tài liệu số' in reply['answer'],reply
    assert [item['id'] for item in reply['books']]==[book['id']]
    definition=turn(client,history,'ISBN là gì?',cid)
    assert definition['status']=='answered' and not definition['books'] and 'ấn bản' in definition['answer'],definition
    reply=turn(client,history,'Tác giả và năm?',cid)
    assert book['author'] in reply['answer'] and book['year'] in reply['answer'],reply
    assert [item['id'] for item in reply['books']]==[book['id']]


@pytest.mark.parametrize('guest',[True,False])
def test_format_filter_preserves_the_search_topic_across_followups(client,guest):
    if not guest:
        register(client)
    with client.app.state.db() as db:
        db.execute("UPDATE books SET kind='digital' WHERE title='Python thực hành A'")
    history=[]
    first=turn(client,history,'Tìm sách Python')
    cid=first['conversation_id']
    ebooks=turn(client,history,'Còn ebook thì sao?',cid)
    assert [item['title'] for item in ebooks['books']]==['Python thực hành A'],ebooks
    printed=turn(client,history,'Loại giấy có không?',cid)
    assert [item['title'] for item in printed['books']]==['Python thực hành B'],printed
    first_printed=turn(client,history,'Cuốn đầu thì sao?',cid)
    assert [item['title'] for item in first_printed['books']]==['Python thực hành B'],first_printed
    turn(client,history,'Thư viện mở cửa thứ Bảy không?',cid)
    reply=turn(client,history,'Còn ebook thì sao?',cid)
    assert reply['status']=='clarify' and not reply['books'],reply


@pytest.mark.parametrize('guest',[True,False])
def test_short_availability_question_checks_only_the_selected_copy(client,guest,monkeypatch):
    if not guest:
        register(client)
    checked=[]
    def unavailable(url):
        checked.append(url)
        return {'status':'unknown'}
    monkeypatch.setattr('app.services.assistant.get_availability',unavailable)
    history=[]
    listing=turn(client,history,'Tìm sách Python')
    cid=listing['conversation_id']
    chosen=listing['books'][1]
    turn(client,history,'Cuốn thứ hai do ai viết?',cid)
    reply=turn(client,history,'Còn sách có sẵn để mượn không?',cid)
    assert [book['id'] for book in reply['books']]==[chosen['id']],reply
    assert checked==[chosen['url']]


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
    ('Còn nhà xuất bản thì sao?','chưa xác nhận nhà xuất bản','needs_confirmation'),
    ('Còn in năm mấy thì sao?','2022','answered'),
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
def test_short_title_resolves_subtitle_and_keeps_selected_book(client,guest):
    if not guest:
        register(client)
    history=[]
    with client.app.state.db() as db:
        db.execute("UPDATE books SET title='Java nhập môn : Từ cú pháp đến dự án' WHERE author='Tác giả mẫu 3'")
        db.execute("UPDATE books SET title='Ôn tập Java nhập môn' WHERE author='Tác giả mẫu 2'")
    previous=turn(client,history,'Tìm theo nhan đề Python thực hành A')
    found=turn(client,history,'Tác giả của sách “Java nhập môn” là ai?',previous['conversation_id'])
    assert found['status']=='answered' and 'Tác giả mẫu 3' in found['answer'],found
    assert [s['url'] for s in found['sources']]==['https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=803']
    for message,fact in [('Xuất bản năm nào?','2023'),('Nó nói về gì?','Nội dung mẫu riêng 3.')]:
        followup=turn(client,history,message,found['conversation_id'])
        assert followup['status']=='answered' and fact in followup['answer'],followup
        assert [b['id'] for b in followup['books']]==[found['books'][0]['id']]


@pytest.mark.parametrize('question',['Tác giả của sách “Python thực hành” là ai?', 'Sách “Python thực hành” còn bản không?'])
def test_short_title_with_multiple_editions_asks_before_using_an_edition(client,monkeypatch,question):
    monkeypatch.setattr('app.services.assistant.get_availability',lambda _:pytest.fail('Resolve the edition before checking availability'))
    history=[]
    found=turn(client,history,question)
    assert found['status']=='clarify',found
    assert [b['title'] for b in found['books']]==['Python thực hành A','Python thực hành B']
    assert len(found['sources'])==2
    chosen=turn(client,history,'Cuốn thứ hai xuất bản năm nào?',found['conversation_id'])
    assert chosen['status']=='answered' and '2022' in chosen['answer'],chosen


@pytest.mark.parametrize('title',['nhập môn','Java','Java nâng cao'])
def test_quoted_metadata_does_not_guess_a_title_from_a_fragment(client,title):
    found=turn(client,[],f'Tác giả của sách “{title}” là ai?')
    assert found['status']=='not_found' and not found['books'],found


def test_exact_title_wins_and_draft_subtitle_never_creates_ambiguity(client):
    with client.app.state.db() as db:
        db.execute("UPDATE books SET title='Java nhập môn : Bản nâng cao' WHERE author='Tác giả mẫu 2'")
        db.execute("UPDATE books SET title='Java nhập môn : Bản nháp',published=0 WHERE author='Tác giả mẫu 1'")
    question='Tác giả của sách “Java nhập môn” là ai?'
    exact=turn(client,[],question)
    assert exact['status']=='answered' and [b['author'] for b in exact['books']]==['Tác giả mẫu 3']
    with client.app.state.db() as db:
        db.execute("UPDATE books SET published=0 WHERE author='Tác giả mẫu 3'")
    subtitle=turn(client,[],question)
    assert subtitle['status']=='answered' and [b['author'] for b in subtitle['books']]==['Tác giả mẫu 2']


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
