from difflib import SequenceMatcher
from contextlib import contextmanager
from types import SimpleNamespace
import re
import unicodedata

import pytest

from app.database.connection import Store
from app.services import catalog
from app.services.knowledge import today


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path/'library.sqlite3')


def add(store, title, **changes):
    with store.connect() as db:
        count=db.execute('SELECT count(*) FROM books').fetchone()[0]
        return catalog.save_book(db,catalog.BookInput(title=title,author='Nguyễn Văn An',year='1999',
            source_url=f'https://lic.ut.edu.vn/synthetic-scaling-{count}/',checked_at=today(),published=True,**changes))


@pytest.mark.parametrize('query',[
    'logistics bố trí vị trí lấy hàng giảm thời gian di chuyển',
    'bo tri mat bang kho',
])
def test_warehouse_search_finds_bilingual_operation_in_metadata(store,query):
    book=add(store,'World-Class Warehousing',description='Warehouse layout and order picking.')
    add(store,'Dịch vụ logistics cảng',description='Khách hàng giảm thời gian di chuyển đến vị trí nhận container.')
    add(store,'Sửa máy tàu để vào cảng lấy hàng')
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    assert [row['id'] for row in catalog.search_books(state,query)]==[book['id']]
    assert not catalog.search_books(state,query,field='title')


def test_warehouse_lookup_uses_marc_subjects_when_summary_is_missing(store):
    book=add(store,'Operations handbook')
    with store.connect() as db:
        db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
                   (book['id'],book['source_url'],today(),'a'*64,'Warehouse layout','',''))
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    assert [row['id'] for row in catalog.search_books(state,'bố trí mặt bằng kho')]==[book['id']]


def test_impossible_character_matches_do_not_compute_full_similarity(store,monkeypatch):
    add(store,'aaaaaa bbbbbb cccccc')
    comparisons=[]
    class CountedMatcher(SequenceMatcher):
        def ratio(self):
            comparisons.append(True)
            return super().ratio()
    monkeypatch.setattr(catalog,'SequenceMatcher',CountedMatcher)
    assert catalog.search_local(store.connect,'zzzzzz')==[]
    assert comparisons==[]


def test_precise_catalog_query_skips_fuzzy_comparison_of_unrelated_books(store,monkeypatch):
    exact=add(store,'Python cơ bản')
    add(store,'Thiết kế cầu đường')
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    def unexpected(*args):
        raise AssertionError('A precise result should not scan fuzzy candidates')
    monkeypatch.setattr(catalog,'_similar_words',unexpected)
    assert [row['id'] for row in catalog.search_books(state,'Python')]==[exact['id']]


def test_precise_fast_path_keeps_typo_fallback_and_publication_changes(store):
    exact=add(store,'Python cơ bản')
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    assert [row['id'] for row in catalog.search_books(state,'Pythno')]==[exact['id']]
    assert [row['id'] for row in catalog.search_books(state,'Python')]==[exact['id']]
    with store.connect() as db:
        db.execute('UPDATE books SET published=0 WHERE id=?',(exact['id'],))
    assert catalog.search_books(state,'Python')==[]
    current=add(store,'Python thực hành')
    assert [row['id'] for row in catalog.search_books(state,'Python')]==[current['id']]


def test_complete_keyword_evidence_skips_approximate_matches(store,monkeypatch):
    add(store,'Logistix quản lý kho')
    exact=add(store,'Sổ tay kho',subjects='Logistics; quản lý kho')
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))

    def unexpected(*args):
        pytest.fail('A record matches all keywords, so typo correction is unnecessary')

    monkeypatch.setattr(catalog,'_similar_words',unexpected)
    assert [row['id'] for row in catalog.search_books(state,'logistics kho quản lý')]==[exact['id']]


def test_typo_match_in_title_ranks_ahead_of_a_passive_mention(store):
    mention=add(store,'Thống kê ngành',description='Có ví dụ dùng Python.')
    exact_topic=add(store,'Nhập môn Python')
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    assert [row['id'] for row in catalog.search_books(state,'pyhton')]==[exact_topic['id'],mention['id']]


@pytest.mark.parametrize('query', [
    'hải đồ nhận diện luồng hàng hải bằng tín hiệu vệ tinh',
    'hai do nhan dien luong hang hai bang tin hieu ve tinh',
])
def test_long_search_prefers_a_title_with_the_leading_topic_phrase(store,query):
    add(store,'Đồ họa máy tính bằng hình ảnh dễ hiểu',
        description='Nhận dạng hàng loạt bằng tín hiệu vệ tinh và nhận biết luồng chuyển động.')
    topical=add(store,'Ứng dụng hải đồ điện tử trên tuyến luồng hàng hải',
        description='Nhận diện luồng hàng hải bằng tín hiệu số.')
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    assert [row['id'] for row in catalog.search_books(state,query)]==[topical['id']]


def test_long_search_avoids_fuzzy_work_outside_a_credible_topic(store,monkeypatch):
    add(store,'Unrelated material spuriousmarker',
        description='Nhận diện luồng hàng hải bằng tín hiệu vệ tinh và nhận biết chuyển động.')
    topical=add(store,'Ứng dụng hải đồ điện tử trên tuyến luồng hàng hải',
        description='Nhận diện luồng hàng hải bằng tín hiệu số.')
    matches_topic=catalog._matches_programming_topic

    def checked(row,languages):
        assert 'spuriousmarker' not in row['title']
        return matches_topic(row,languages)

    monkeypatch.setattr(catalog,'_matches_programming_topic',checked)
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    rows=catalog.search_books(state,'hải đồ nhận diện luồng hàng hải bằng tín hiệu vệ tinh')
    assert [row['id'] for row in rows]==[topical['id']]


def test_long_search_keeps_a_distinctive_topic_word_when_the_phrase_is_absent(store):
    add(store,'Tài liệu tài chính về cách bố trí và giảm thời gian',
        description='Vị trí lấy hàng và phân bổ tài nguyên.',subjects='TV Chuyên ngành Logistics')
    topical=add(store,'Quản lý kho Logistics',
        description='Bố trí vị trí lấy hàng để giảm thời gian và công sức.')
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=True))
    rows=catalog.search_books(state,'logistics bố trí vị trí lấy hàng giảm thời gian di chuyển')
    assert [row['id'] for row in rows]==[topical['id']]


def test_catalog_projection_is_reused_until_another_connection_changes_books(store):
    row=add(store,'Python cơ bản')
    scans=[]
    @contextmanager
    def counted():
        with store.connect() as db:
            db.set_trace_callback(lambda sql:scans.append(sql) if sql.startswith('SELECT * FROM books_discovery') else None)
            yield db
    assert catalog.search_local(counted,'Python',field='title')
    assert catalog.search_local(counted,'Python',field='title')
    assert len(scans)==1
    with store.connect() as db:
        db.execute('UPDATE books SET published=0 WHERE id=?',(row['id'],))
    assert catalog.search_local(counted,'Python',field='title')==[]
    assert len(scans)==2


def test_catalog_projection_invalidates_marc_edits_and_rolled_back_writes(store):
    row=add(store,'Biên mục thử nghiệm')
    with store.connect() as db:
        db.execute('INSERT INTO book_marc VALUES (?,?,?,?,?,?,?)',
            (row['id'],row['url'],today(),'a'*64,'quuxfirst','Nội dung gốc',''))
    assert catalog.search_local(store.connect,'quuxfirst')
    try:
        with store.connect() as db:
            db.execute("UPDATE book_marc SET subjects='quuxrollback' WHERE book_id=?",(row['id'],))
            raise RuntimeError('Synthetic rollback')
    except RuntimeError:
        pass
    assert catalog.search_local(store.connect,'quuxfirst')
    with store.connect() as db:
        db.execute("UPDATE book_marc SET subjects='quuxsecond' WHERE book_id=?",(row['id'],))
    assert catalog.search_local(store.connect,'quuxfirst')==[]
    assert catalog.search_local(store.connect,'quuxsecond')
    with store.connect() as db:
        db.execute('DELETE FROM book_marc WHERE book_id=?',(row['id'],))
    assert catalog.search_local(store.connect,'quuxsecond')==[]


def test_exact_prefix_typo_and_author_search_keep_expected_ranking(store):
    exact=add(store,'Olympic cơ học')
    longer=add(store,'Tuyển tập Olympic cơ học nâng cao')
    unrelated=add(store,'Công nghệ thông tin')
    assert [r['id'] for r in catalog.search_local(store.connect,'olympic co hoc')]==[exact['id'],longer['id']]
    assert [r['id'] for r in catalog.search_local(store.connect,'olimpic co hoc')]==[exact['id'],longer['id']]
    assert [r['id'] for r in catalog.search_local(store.connect,'tuyen tap olympic')]==[longer['id']]
    assert {r['id'] for r in catalog.search_local(store.connect,'nguyen van an')}=={exact['id'],longer['id'],unrelated['id']}


@pytest.mark.parametrize('text', ['Công nghệ đóng tàu thủy', 'Đà Nẵng – 2026',
    'Cà phê A\u1ab0B A\ufe0fB', 'A\u093eB', 'ASCII\t+ HTML/CSS', 'A\U000e0100B', ''])
def test_fast_normalization_preserves_existing_unicode_token_boundaries(text):
    decomposed=unicodedata.normalize('NFD',text.lower().replace('đ','d'))
    old=' '.join(re.sub(r'[^a-z0-9 ]',' ',''.join(
        ch for ch in decomposed if unicodedata.category(ch)!='Mn')).split())
    assert catalog.normalize(text)==old


def test_filters_and_withdrawals_remain_current_after_search(store):
    printed=add(store,'Olympic cơ học',kind='books')
    digital=add(store,'Olympic cơ học số',kind='digital')
    assert [r['id'] for r in catalog.search_local(store.connect,'olimpic','digital')]==[digital['id']]
    with store.connect() as db:
        db.execute('UPDATE books SET published=0 WHERE id=?',(digital['id'],))
    assert catalog.search_local(store.connect,'olimpic','digital')==[]
    assert [r['id'] for r in catalog.search_local(store.connect,'olimpic','books')]==[printed['id']]
    with store.connect() as db:
        db.execute("UPDATE books SET title='Máy tính lượng tử',author='' WHERE id=?",(printed['id'],))
    assert catalog.search_local(store.connect,'olimpic','books')==[]
    assert [r['id'] for r in catalog.search_local(store.connect,'may tinh','books')]==[printed['id']]


def test_book_documents_match_query_time_index_projection():
    rows=[{'id':4,'title':'Nghiên cứu XML','author':'Nguyễn A','subjects':'XML','description':'Tóm tắt có nguồn'},
        {'id':5,'title':'Thiết kế cầu','author':'Trần B','subjects':'Xây dựng','description':''}]
    assert catalog.book_documents(rows)==[
        {'id':4,'question':'Nghiên cứu XML','aliases':['Nguyễn A','XML'],'answer':'Tóm tắt có nguồn'},
        {'id':5,'question':'Thiết kế cầu','aliases':['Trần B','Xây dựng'],'answer':'Thiết kế cầu'}]


def test_semantic_catalog_snapshot_is_reused_until_metadata_changes(store,monkeypatch):
    book=add(store,'Python cơ bản')
    monkeypatch.setenv('ENABLE_VECTORS','true')
    calls=[]
    def search(query,documents,**kwargs):
        calls.append(documents)
        return []
    vectors=SimpleNamespace(prepare_books=lambda load:'ready',search=search)
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=False),vectors=vectors)
    for _ in range(2):
        assert catalog.search_books_with_status(state,'zzzzz xxxxx')==([],None)
    assert calls[0] is calls[1]
    with store.connect() as db:
        db.execute("UPDATE books SET title='Python nâng cao' WHERE id=?",(book['id'],))
    assert catalog.search_books_with_status(state,'zzzzz xxxxx')==([],None)
    assert calls[2] is not calls[1] and calls[2][0]['question']=='Python nâng cao'


@pytest.mark.parametrize('document_type',['luận văn','luận án','khóa luận','đồ án','giáo trình','bài giảng'])
@pytest.mark.parametrize('command',['Tìm','Tra cứu'])
def test_institutional_document_search_strips_type_prefix(document_type,command):
    question=f'{command} {document_type} về tàu thủy'
    assert catalog.is_book_request(question)
    assert catalog.book_query(question)=='tau thuy'
    follow=catalog.contextual_question('Tác giả là ai?',[{'role':'user','content':question}])
    assert follow==question


@pytest.mark.parametrize('question',['Hướng dẫn tìm luận văn','Cách tra cứu giáo trình ở đâu?',
    'Viết luận văn cho tôi','Luận án là gì?'])
def test_document_guidance_and_non_search_requests_are_not_catalog_search(question):
    assert not catalog.is_book_request(question)


def test_document_words_inside_a_title_are_not_removed_as_a_type_prefix():
    assert 'luan van' in catalog.book_query('Tìm sách hướng dẫn viết luận văn')


def reference_search(store,query,kind='all'):
    from app.services.rag_service import normalize,tokens
    words=tokens(query)-{'tim','sach','tai','lieu','theo','quyen','cuon','tac','gia','chu','de','nguoi','viet'}
    if not words:
        return []
    with store.connect() as db:
        rows=db.execute('SELECT * FROM books WHERE published=1').fetchall()
    ranked=[]
    for row in rows:
        if kind!='all' and row['kind']!=kind:
            continue
        corpus=set(normalize(' '.join(row[k] for k in ('title','author','year','subjects','description'))).split())
        matched=len(words&corpus)
        for word in words-corpus:
            if len(word)>=4 and any(len(token)>=4 and SequenceMatcher(None,word,token).ratio()>=0.83 for token in corpus):
                matched+=1
        coverage=matched/len(words)
        if coverage>=0.6:
            score=coverage+len(words&tokens(row['title']))*0.15+len(words&tokens(row['author']))*0.1
            ranked.append((row,score))
    ranked.sort(key=lambda pair:(normalize(pair[0]['title'])!=normalize(query),-pair[1],pair[0]['id']))
    return [row['id'] for row,_ in ranked]


@pytest.mark.parametrize('query',['Python cơ bản','python co ban','pythom','nguyen van an','logistics','vận tải biển','sách','zzzzzz'])
@pytest.mark.parametrize('kind',['all','books','digital'])
def test_metadata_cache_preserves_reference_ranking(store,query,kind):
    add(store,'Python cơ bản',subjects='Lập trình; logistics',description='Vận tải biển')
    add(store,'Python cơ bản nâng cao',kind='digital',subjects='Logistics')
    add(store,'Vận tải biển',description='Python cho người mới')
    draft=add(store,'Python cơ bản')
    with store.connect() as db:
        db.execute('UPDATE books SET published=0 WHERE id=?',(draft['id'],))
    expected=reference_search(store,query,kind)
    for _ in range(2):
        assert [r['id'] for r in catalog.search_local(store.connect,query,kind)]==expected


@pytest.mark.parametrize('field',['all','title','author'])
def test_unchanged_metadata_reuses_normalization_but_edits_are_immediate(store,monkeypatch,field):
    row=add(store,'Python cơ bản')
    calls=[]
    original=catalog.normalize_catalog
    def counted(value):
        calls.append(value)
        return original(value)
    catalog._normalized_metadata.cache_clear()
    monkeypatch.setattr(catalog,'normalize_catalog',counted)
    query='Nguyễn Văn An' if field=='author' else 'Python'
    assert catalog.search_local(store.connect,query,field=field)
    calls.clear()
    assert catalog.search_local(store.connect,query,field=field)
    assert all(value==query for value in calls)
    with store.connect() as db:
        db.execute("UPDATE books SET title='Máy tính',author='Trần Bình' WHERE id=?",(row['id'],))
    assert catalog.search_local(store.connect,query,field=field)==[]
    replacement='Trần Bình' if field=='author' else 'Máy tính'
    assert [r['id'] for r in catalog.search_local(store.connect,replacement,field=field)]==[row['id']]
