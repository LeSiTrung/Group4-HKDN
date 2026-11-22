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


def test_semantic_kind_filter_keeps_complete_index_inventory(client,monkeypatch):
    from app.services.catalog import search_books
    rows=[client.post('/api/admin/books',json=book(kind=kind,source_url=f'https://lic.ut.edu.vn/synthetic-{kind}/')).json() for kind in ('books','digital')]
    state=client.app.state
    state.settings.testing=False
    monkeypatch.setenv('ENABLE_VECTORS','true')
    monkeypatch.setattr(state.vectors,'prepare_books',lambda load:'ready')
    calls=[]
    def search(query,documents,namespace='books',source_ids=None,*,ready_only=False):
        assert ready_only
        calls.append((documents,source_ids))
        return [(row,.9) for row in documents if row['id'] in (source_ids or set())]
    monkeypatch.setattr(state.vectors,'search',search)
    for kind in ('books','digital'):
        result=search_books(state,'Python practical exercises',kind)
        assert result and all(row['kind']==kind for row in result)
        assert {row['id'] for row in rows}<={d['id'] for d in calls[-1][0]}
        with state.db() as db:
            expected={row['id'] for row in db.execute('SELECT id FROM books WHERE published=1 AND kind=?',(kind,))}
        assert calls[-1][1]==expected


def test_catalog_omits_a_semantic_match_edited_during_search(client, monkeypatch):
    from app.services.catalog import search_books

    record = client.post('/api/admin/books', json=book()).json()
    state = client.app.state
    state.settings.testing = False
    monkeypatch.setenv('ENABLE_VECTORS', 'true')
    monkeypatch.setattr(state.vectors, 'prepare_books', lambda load: 'ready')

    def search(query, documents, **kwargs):
        match = next(document for document in documents if document['id'] == record['id'])
        with state.db() as db:
            db.execute('UPDATE books SET title=?, subjects=? WHERE id=?',
                       ('Python ecosystems for experts', 'Python; ecosystem', record['id']))
        return [(match, .9)]

    monkeypatch.setattr(state.vectors, 'search', search)
    results = search_books(state, 'Python practical exercises')
    assert record['id'] not in {result['id'] for result in results}


def test_single_identifier_does_not_become_an_unrelated_semantic_recommendation(client,monkeypatch):
    from app.services.catalog import search_books
    state=client.app.state
    state.settings.testing=False
    monkeypatch.setenv('ENABLE_VECTORS','true')
    calls=[]
    monkeypatch.setattr(state.vectors,'search',lambda *args,**kwargs:calls.append(True) or [])
    assert search_books(state,'zzzkhongcobanghi123')==[]
    assert not calls


def test_catalog_returns_local_empty_result_while_semantics_prepares(client,monkeypatch):
    monkeypatch.setattr(client.app.state.settings,'testing',False)
    monkeypatch.setenv('ENABLE_VECTORS','true')
    monkeypatch.setattr(client.app.state.vectors,'prepare_books',lambda load:'preparing',raising=False)
    online_calls=[]
    monkeypatch.setattr('app.api.library.search_catalog',lambda *args:online_calls.append(args) or {})
    for field in ('all','smart'):
        result=client.get('/api/catalog',params={'q':'quuxzzvector zzzyyintegration','field':field}).json()
        assert result['source']=='local' and result['items']==[]
        assert result['semantic_status']=='preparing'
    assert online_calls==[]


def test_catalog_resolves_short_transposed_keyword_without_vectors_or_live_opac(client,monkeypatch):
    row=client.post('/api/admin/books',json=book(title='Giáo trình HTML',subjects='Phát triển web')).json()
    client.app.state.settings.testing=False
    monkeypatch.setenv('ENABLE_VECTORS','true')

    calls=[]
    def unexpected(*args,**kwargs):
        calls.append(args)
        return []

    monkeypatch.setattr(client.app.state.vectors,'search',unexpected)
    monkeypatch.setattr('app.api.library.search_catalog',unexpected)
    result=client.get('/api/catalog',params={'q':'sách htlm','source':'auto','field':'all'}).json()
    assert result['source']=='local'
    assert [item['id'] for item in result['items']]==[row['id']]
    unknown=client.get('/api/catalog',params={'q':'sách zzzhtml999','source':'local','field':'all'}).json()
    assert unknown['items']==[]
    assert calls==[]


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


@pytest.mark.parametrize(('query','field','interpreted'), [
    ('Tìm sách “Python cho người mới”', 'title', 'python cho nguoi moi'),
    ('tim theo tac gia Tac gia thu nghiem', 'author', 'tac gia thu nghiem'),
    ('Tìm sách về Pyhton', 'all', 'pyhton'),
    ('Python', 'all', 'Python'),
])
def test_smart_catalog_interprets_queries_and_suggests_published_titles(client, query, field, interpreted):
    row=client.post('/api/admin/books',json=book()).json()
    client.post('/api/admin/books',json=book(title='Python bản nháp', published=False,
                                            source_url='https://lic.ut.edu.vn/draft-test/'))
    result=client.get('/api/catalog',params={'q':query,'field':'smart'}).json()
    assert result['interpretation']=={'field':field,'query':interpreted}
    assert result['source']=='local'
    assert [item['id'] for item in result['items']]==[row['id']]
    assert result['suggested_titles']==[row['title']]


@pytest.mark.parametrize(('query','guidance'), [
    ('Làm thế nào để tra cứu sách tại thư viện?', True),
    ('Tôi cần chuẩn bị gì để mượn sách?', True),
    ('zzzkhongcobanghi123', False),
    ('Tìm sách', False),
])
def test_smart_catalog_does_not_forward_raw_questions_or_unknown_queries(client,monkeypatch,query,guidance):
    def unexpected(*args,**kwargs):
        pytest.fail('Smart search must not send a question to the external OPAC')
    monkeypatch.setattr('app.api.library.search_catalog',unexpected)
    result=client.get('/api/catalog',params={'q':query,'field':'smart'}).json()
    assert result['source']=='local' and result['items']==[]
    assert result['guidance'] is guidance
    assert result['suggested_titles']==[]


def test_smart_catalog_respects_kind_and_pagination(client):
    for i,kind in enumerate(('books','books','digital')):
        client.post('/api/admin/books',json=book(title=f'Chuyên đề Python {i}',kind=kind,
                                                source_url=f'https://lic.ut.edu.vn/smart-catalog-{i}/'))
    result=client.get('/api/catalog',params={'q':'Tìm sách Python','field':'smart','kind':'books',
                                            'page':2,'page_size':1}).json()
    assert result['total']==2 and result['page']==2
    assert [item['kind'] for item in result['items']]==['books']
    assert result['suggested_titles']==['Chuyên đề Python 0','Chuyên đề Python 1']


def test_marc_evidence_improves_search_and_answers_about_the_selected_title(client):
    url='https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=123'
    row=client.post('/api/admin/books',json=book(title='Nghiệp vụ kho vận',source_url=url,
                                               subjects='Logistics',description='Mô tả do cán bộ duyệt.')).json()
    params={'q':'Tìm tài liệu về kiểm kê chu kỳ','field':'smart'}
    assert client.get('/api/catalog',params=params).json()['total']==0
    with client.app.state.db() as db:
        db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                   (row['id'],url,'2026-10-29','a'*64,'Kiểm kê chu kỳ; Quản lý tồn kho','Hướng dẫn đối chiếu tồn kho.',''))
    found=client.get('/api/catalog',params=params).json()
    assert found['items'][0]['id']==row['id']
    assert found['items'][0]['marc_match']=='subjects'
    assert 'Quản lý tồn kho' in found['suggested_keywords']
    assert 'Kiểm kê chu kỳ' not in found['suggested_keywords']
    detail=client.get(f"/api/catalog/{row['id']}").json()
    assert detail['description']=='Mô tả do cán bộ duyệt.'
    assert detail['marc']=={'subjects':'Kiểm kê chu kỳ; Quản lý tồn kho','summary':'Hướng dẫn đối chiếu tồn kho.',
                            'audience':'','checked_at':'2026-10-29'}
    direct=client.post('/api/chat',json={'message':'Tóm tắt tài liệu “Nghiệp vụ kho vận”'}).json()
    assert direct['status']=='answered' and direct['mode']=='catalog'
    assert 'Hướng dẫn đối chiếu tồn kho.' in direct['answer']
    assert direct['sources'][0]['url']==url and direct['sources'][0]['checked_at']=='2026-10-29'
    assert client.post('/api/chat',json={'message':'Tóm tắt tài liệu “Nghiệp vụ kho”'}).json()['status']=='not_found'
    cid=client.post('/api/chat',json={'message':'Tìm sách “Nghiệp vụ kho vận”'}).json()['conversation_id']
    for question,expected,status in [('Tài liệu này nói về gì?', 'Hướng dẫn đối chiếu tồn kho.', 'answered'),
                                     ('Tài liệu này dành cho ai?', 'đối tượng đọc', 'needs_confirmation')]:
        answer=client.post('/api/chat',json={'message':question,'conversation_id':cid}).json()
        assert expected in answer['answer'] and answer['status']==status
        assert answer['sources'][0]['url']==url
        if status=='answered':
            assert answer['sources'][0]['checked_at']=='2026-10-29'
    with client.app.state.db() as db:
        db.execute('UPDATE books SET published=0 WHERE id=?',(row['id'],))
    assert client.get('/api/catalog',params=params).json()['total']==0
    assert client.get(f"/api/catalog/{row['id']}").status_code==404


def test_smart_catalog_understands_a_learning_goal(client):
    client.post('/api/admin/books',json=book(title='Python: ứng dụng tại doanh nghiệp',
                                            source_url='https://lic.ut.edu.vn/python-case-study/'))
    row=client.post('/api/admin/books',json=book(title='Giáo trình Python')).json()
    result=client.get('/api/catalog',params={'q':'Tôi muốn học Python từ đầu','field':'smart'}).json()
    assert result['interpretation']['query']=='python'
    assert result['learning_goal'] is True
    assert result['items'][0]['id']==row['id']


@pytest.mark.parametrize(('question','semantic_status'),[
    ('Tìm sách về quuxzzvector zzzyyintegration','preparing'),
    ('Gợi ý sách về quuxzzvector zzzyyintegration','unavailable'),
])
def test_chat_distinguishes_an_incomplete_semantic_search_from_no_results(client,monkeypatch,question,semantic_status):
    monkeypatch.setattr(client.app.state.settings,'testing',False)
    monkeypatch.setenv('ENABLE_VECTORS','true')
    monkeypatch.setattr(client.app.state.vectors,'prepare_books',lambda load:semantic_status)
    result=client.post('/api/chat',json={'message':question}).json()
    assert result['status']=='needs_confirmation' and result['mode']=='catalog'
    assert 'tìm theo nội dung' in result['answer']
    assert result['suggestions']==[question]
    assert result['books']==[]


@pytest.mark.parametrize('question',[
    'Tóm tắt tài liệu “Kiểm kê chu kỳ”',
    'Tóm tắt nội dung cuốn “Kiểm kê chu kỳ”',
    'Tóm tắt ngắn gọn nội dung của cuốn sách “Kiểm kê chu kỳ”',
    'Tóm tắt sách "Kiem ke chu ky"',
    'Nội dung của tài liệu “Kiểm kê chu kỳ”',
    'Tài liệu “Kiểm kê chu kỳ” nói về gì?',
    'Nội dung tài liệu “Kiểm kê chu kỳ”',
    'Sách “Kiểm kê chu kỳ” có nội dung gì?',
])
def test_direct_summary_requires_a_published_full_title_and_exact_source(client,question):
    url='https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=123'
    row=client.post('/api/admin/books',json=book(title='Kiểm kê chu kỳ',source_url=url)).json()
    with client.app.state.db() as db:
        db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                   (row['id'],url,'2026-10-29','a'*64,'Kiểm kê','Mô tả theo đúng biểu ghi đã chọn.',''))
    answer=client.post('/api/chat',json={'message':question}).json()
    assert answer['status']=='answered' and len(answer['books'])==1
    assert 'Mô tả theo đúng biểu ghi đã chọn.' in answer['answer']
    assert answer['sources']==[{'title':'Kiểm kê chu kỳ','url':url,'checked_at':'2026-10-29'}]


@pytest.mark.parametrize('case',['duplicate','missing_summary','withdrawn'])
def test_direct_summary_keeps_ambiguity_and_missing_evidence_visible(client,case):
    row=client.post('/api/admin/books',json=book(title='Kiểm kê chu kỳ')).json()
    if case=='duplicate':
        client.post('/api/admin/books',json=book(title='Kiểm kê chu kỳ',
                                                source_url='https://lic.ut.edu.vn/other-edition/'))
    elif case=='withdrawn':
        with client.app.state.db() as db:
            db.execute('UPDATE books SET published=0 WHERE id=?',(row['id'],))
    response=client.post('/api/chat',json={'message':'Tóm tắt tài liệu “Kiểm kê chu kỳ”'}).json()
    assert response['status']=={'duplicate':'clarify','missing_summary':'needs_confirmation','withdrawn':'not_found'}[case]
    if case=='withdrawn':
        assert not response['books']


@pytest.mark.parametrize('earlier_topic',[False,True])
@pytest.mark.parametrize('selection',[
    'Tóm tắt tài liệu “Python cho người mới”',
    'Sách “Python cho người mới” nói về gì?',
])
def test_guest_followup_keeps_the_title_from_a_direct_document_question(client,earlier_topic,selection):
    row=client.post('/api/admin/books',json=book()).json()
    client.post('/api/auth/logout')
    history=([{'role':'user','content':'Tìm sách Olympic cơ học'}] if earlier_topic else [])
    history.append({'role':'user','content':selection})
    answer=client.post('/api/chat',json={'message':'Tác giả là ai?','history':history}).json()
    assert answer['status']=='answered'
    assert len(answer['books'])==1 and answer['books'][0]['id']==row['id']
    assert row['author'] in answer['answer']
    assert answer['sources'][0]['url']==row['source_url']


@pytest.mark.parametrize('change',['withdrawn','changed_topic'])
def test_guest_document_context_does_not_reuse_an_older_book_after_withdrawal_or_topic_change(client,change):
    row=client.post('/api/admin/books',json=book()).json()
    history=[{'role':'user','content':'Tìm sách Olympic cơ học'},
             {'role':'user','content':'Tóm tắt sách “Python cho người mới”'}]
    if change=='withdrawn':
        with client.app.state.db() as db:
            db.execute('UPDATE books SET published=0 WHERE id=?',(row['id'],))
    else:
        history.append({'role':'user','content':'Tôi muốn gia hạn sách'})
    client.post('/api/auth/logout')
    answer=client.post('/api/chat',json={'message':'Tác giả là ai?','history':history}).json()
    assert answer['status']==('not_found' if change=='withdrawn' else 'clarify')
    assert not answer['books']


@pytest.mark.parametrize('source',['local','auto'])
def test_catalog_pagination_recovers_when_published_results_shrink(client,monkeypatch,source):
    rows=[client.post('/api/admin/books',json=book(title=f'Python phân trang {i}',
             source_url=f'https://lic.ut.edu.vn/page-test/{i}')).json() for i in range(3)]
    def unexpected(*args,**kwargs):
        pytest.fail('A local pagination request must not switch to the external OPAC')
    monkeypatch.setattr('app.api.library.search_catalog',unexpected)
    params={'q':'Python phân trang','source':source,'field':'all','page':3,'page_size':1}
    first=client.get('/api/catalog',params=params).json()
    assert first['page']==3 and first['total']==3 and len(first['items'])==1
    with client.app.state.db() as db:
        db.execute('UPDATE books SET published=0 WHERE id IN (?,?)',(rows[1]['id'],rows[2]['id']))
    reduced=client.get('/api/catalog',params=params).json()
    assert reduced['page']==1 and reduced['total']==1 and reduced['items'][0]['id']==rows[0]['id']
    with client.app.state.db() as db:
        db.execute('UPDATE books SET published=0 WHERE id=?',(rows[0]['id'],))
    empty=client.get('/api/catalog',params=params).json()
    assert empty['page']==1 and empty['total']==0 and empty['items']==[] and empty['source']=='local'


def test_guest_followup_author_uses_retrieved_book_not_generic_faq(client):
    row=client.post('/api/admin/books',json=book()).json()
    client.post('/api/auth/logout')
    response=client.post('/api/chat',json={'message':'Cuốn đó của tác giả nào?', 'history':[{'role':'user','content':'Tìm sách về Python'}]})
    result=response.json()
    assert result['books'][0]['id']==row['id']
    assert book()['author'] in result['answer']


@pytest.mark.parametrize('guest',[False,True])
@pytest.mark.parametrize('question',[
    'Cuốn thứ hai do ai viết?', 'cuon thu 2 cua tac gia nao?',
    'Tác giả của quyển thứ hai là ai?',
])
def test_numbered_followup_uses_the_displayed_public_book_order(client,guest,question):
    for suffix in ('A','B'):
        client.post('/api/admin/books',json=book(title='Python sổ tay '+suffix,author='Người viết '+suffix,
            source_url=f'https://lic.ut.edu.vn/ordinal-{suffix}/'))
    if guest:
        client.post('/api/auth/logout')
    first=client.post('/api/chat',json={'message':'Tìm sách Python sổ tay'}).json()
    assert len(first['books'])==2
    chosen=first['books'][1]
    payload={'message':question}
    if guest:
        payload['history']=[{'role':'user','content':'Tìm sách Python sổ tay'},
            {'role':'assistant','content':first['answer'],'book_ids':[b['id'] for b in first['books']]}]
    else:
        payload['conversation_id']=first['conversation_id']
    response=client.post('/api/chat',json=payload).json()
    assert response['status']=='answered',response
    assert [b['id'] for b in response['books']]==[chosen['id']]
    assert chosen['author'] in response['answer']
    assert response['sources'][0]['url']==chosen['url']


@pytest.mark.parametrize('case',['updated','withdrawn','missing','old_list','no_list','out_of_range'])
def test_numbered_guest_followup_revalidates_current_public_metadata(client,case):
    row=client.post('/api/admin/books',json=book()).json()
    with client.app.state.db() as db:
        db.execute('UPDATE books SET author=?,published=? WHERE id=?',('Tác giả đã cập nhật',case!='withdrawn',row['id']))
    client.post('/api/auth/logout')
    history=[{'role':'assistant','content':'Danh sách sách.','book_ids':[999999 if case=='missing' else row['id']]}]
    if case=='old_list':
        history += [{'role':'user','content':'Tôi muốn gia hạn sách'}, {'role':'assistant','content':'Hướng dẫn gia hạn.'}]
    elif case=='no_list':
        history=[]
    question='Cuốn thứ hai do ai viết?' if case=='out_of_range' else 'Cuốn thứ nhất do ai viết?'
    response=client.post('/api/chat',json={'message':question,'history':history}).json()
    if case=='updated':
        assert response['status']=='answered' and 'Tác giả đã cập nhật' in response['answer']
    else:
        assert response['status']=='clarify',response
        assert not response['books'] and not response['sources']
        assert 'nhan đề' in response['answer']


@pytest.mark.parametrize('ids',[[1]*6,[0],[-1],[2**63],[1.5],['1']])
def test_guest_context_book_ids_are_bounded_strict_public_references(client,ids):
    response=client.post('/api/chat',json={'message':'Cuốn thứ nhất do ai viết?',
        'history':[{'role':'assistant','content':'Các sách.','book_ids':ids}]})
    assert response.status_code==422


@pytest.mark.parametrize('question',['Sách năm 2024 của tác giả nào?', 'Sách “Cuốn thứ hai” nói về gì?', 'Thứ hai thư viện mở cửa lúc nào?'])
def test_book_position_does_not_interpret_titles_years_or_weekdays(question):
    from app.services.catalog import book_position
    assert book_position(question) is None


@pytest.mark.parametrize('long_title',[False,True])
def test_numbered_followup_keeps_exact_id_even_for_duplicate_or_long_titles(client,long_title):
    title='Python '+('tài liệu chuyên ngành '*15 if long_title else 'trùng nhan đề')
    rows=[client.post('/api/admin/books',json=book(title=title,author=f'Tác giả bản {i}',
        source_url=f'https://lic.ut.edu.vn/ordinal-edition-{i}/')).json() for i in range(2)]
    client.post('/api/auth/logout')
    response=client.post('/api/chat',json={'message':'Cuốn thứ hai do ai viết?',
        'history':[{'role':'assistant','content':'Các sách cùng nhan đề.','book_ids':[row['id'] for row in rows]}]}).json()
    assert response['status']=='answered',response
    assert [row['id'] for row in response['books']]==[rows[1]['id']]
    assert rows[1]['author'] in response['answer']


@pytest.mark.parametrize('question',['Cuốn đó còn bản nào không?','Cuốn đó còn sách để mượn không?'])
def test_guest_followup_cannot_invent_availability(client,question):
    client.post('/api/admin/books',json=book())
    client.post('/api/auth/logout')
    result=client.post('/api/chat',json={'message':question, 'history':[{'role':'user','content':'Tìm sách về Python'}]}).json()
    assert result['status']=='needs_confirmation'
    assert result['books']
    assert 'không' in result['answer'].lower()
