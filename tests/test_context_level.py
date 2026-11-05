from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services.assistant import answer_question
from app.services.catalog import BookInput, save_book
from app.services.knowledge import today


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    store = Store(tmp_path/'library.sqlite3')
    with store.connect() as db:
        save_book(db, BookInput(title='Python programming', source_url='https://lic.ut.edu.vn/synthetic-python-level/',
                               checked_at=today(), published=True))
    return SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=True))


@pytest.mark.parametrize('question', ['Có cuốn nào dành cho người mới không?', 'Co cuon nao danh cho nguoi moi khong?', 'Nâng cao'])
def test_unlabelled_level_retains_books_without_claiming_suitability(state, question):
    result = answer_question(state, question, [{'role': 'user', 'content': 'Tìm sách Python'}])
    assert result['status'] == 'clarify' and result['books'][0]['title'] == 'Python programming'
    assert 'chưa' in result['answer'].lower() and result['sources']
    assert result['context_query'] == 'Tìm sách Python'


@pytest.mark.parametrize('history,question', [
    ([{'role': 'user', 'content': 'Tìm sách Python'}], 'Có cuốn nào về Java dành cho người mới không?'),
    ([{'role': 'user', 'content': 'Tìm sách Python'}, {'role': 'user', 'content': 'Hướng dẫn tra cứu OPAC'}], 'Có cuốn nào dành cho người mới không?'),
])
def test_level_fallback_does_not_ignore_new_topics_or_unrelated_turns(state, history, question):
    result = answer_question(state, question, history)
    assert not result.get('books')
