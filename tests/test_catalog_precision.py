from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services import catalog
from app.services.knowledge import today


@pytest.fixture
def state(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS','true')
    store=Store(tmp_path/'library.sqlite3')
    return SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=False),vectors=SimpleNamespace())


def add(state,title='Python cơ bản',**changes):
    with state.db() as db:
        count=db.execute('SELECT count(*) FROM books').fetchone()[0]
        values={'title':title,'author':'Nguyễn Văn An','published':True,
                'source_url':f'https://lic.ut.edu.vn/synthetic-precision-{count}/','checked_at':today()}
        return catalog.save_book(db,catalog.BookInput(**{**values,**changes}))


@pytest.mark.parametrize('query',['quuxzzvector zzzyyintegration','frobnicator blarglesnort'])
def test_all_unknown_terms_cannot_become_high_scoring_semantic_results(state,query):
    add(state,subjects='Lập trình',description='Tài liệu hướng dẫn Python.')
    calls=[]
    def search(query,documents,**kwargs):
        calls.append(query)
        return [(documents[0],.99)]
    state.vectors.search=search
    assert catalog.search_books(state,query)==[]
    assert calls==[query]


@pytest.mark.parametrize('query,metadata',[
    ('Python practical exercises',{}),
    ('pythom practical exercises',{}),
    ('phân tích quan sát',{'title':'Thống kê cơ bản','subjects':'Phân tích dữ liệu'}),
    ('statistical forecasting uncertainty',{'title':'Thống kê cơ bản','description':'Statistical methods.'}),
])
def test_semantic_results_keep_partial_topic_evidence_including_typos(state,query,metadata):
    row=add(state,**metadata)
    assert catalog.search_local(state.db,query)==[]
    state.vectors.search=lambda query,documents,**kwargs:[(documents[0],.7)]
    assert [book['id'] for book in catalog.search_books(state,query)]==[row['id']]


def test_author_name_alone_does_not_ground_a_semantic_topic(state):
    add(state)
    state.vectors.search=lambda query,documents,**kwargs:[(documents[0],.99)]
    assert catalog.search_books(state,'nguyen quuxzz zzzyy')==[]


@pytest.mark.parametrize('field',['title','author'])
def test_structured_missing_terms_do_not_use_semantic_fallback(state,field):
    add(state)
    state.vectors.search=lambda *args,**kwargs:pytest.fail('Structured lookup must remain exact')
    assert catalog.search_books(state,'quuxzzvector zzzyyintegration',field=field)==[]


def test_semantic_gate_keeps_kind_filter_full_inventory_and_draft_isolation(state):
    printed=add(state,kind='books')
    digital=add(state,kind='digital')
    draft=add(state,published=False)
    calls=[]
    def search(query,documents,namespace,source_ids):
        calls.append((documents,namespace,source_ids))
        return [(document,.8) for document in [*documents,draft]]
    state.vectors.search=search
    assert [row['id'] for row in catalog.search_books(state,'python practical exercises','digital')]==[digital['id']]
    documents,namespace,source_ids=calls[0]
    assert {document['id'] for document in documents}=={printed['id'],digital['id']}
    assert namespace=='books' and source_ids=={digital['id']}


@pytest.mark.parametrize('change',["published=0","title='Thống kê',description='',subjects=''"])
def test_semantic_candidates_revalidate_current_visibility_and_topic(state,change):
    row=add(state)
    def search(query,documents,**kwargs):
        with state.db() as db:
            db.execute('UPDATE books SET '+change+' WHERE id=?',(row['id'],))
        return [(documents[0],.99)]
    state.vectors.search=search
    assert catalog.search_books(state,'python practical exercises')==[]
