from difflib import SequenceMatcher

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


def test_exact_prefix_typo_and_author_search_keep_expected_ranking(store):
    exact=add(store,'Olympic cơ học')
    longer=add(store,'Tuyển tập Olympic cơ học nâng cao')
    unrelated=add(store,'Công nghệ thông tin')
    assert [r['id'] for r in catalog.search_local(store.connect,'olympic co hoc')]==[exact['id'],longer['id']]
    assert [r['id'] for r in catalog.search_local(store.connect,'olimpic co hoc')]==[exact['id'],longer['id']]
    assert [r['id'] for r in catalog.search_local(store.connect,'tuyen tap olympic')]==[longer['id']]
    assert {r['id'] for r in catalog.search_local(store.connect,'nguyen van an')}=={exact['id'],longer['id'],unrelated['id']}


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
