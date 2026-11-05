from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services import assistant, catalog
from app.services.knowledge import today

QUESTION = 'vậy thư viện hiện tại có những sách python nào có thể đăng kí mượn và có thể hướng dẫn tôi quá trình đăng kí mượn được khongi'


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    store = Store(tmp_path/'library.sqlite3')
    with store.connect() as db:
        catalog.save_book(db, catalog.BookInput(title='Python thực hành', author='Tác giả thử nghiệm',
            source_url='https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=26521',
            checked_at=today(), published=True))
    return SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=True))


@pytest.mark.parametrize('question', [QUESTION, 'Thu vien co nhung sach Python nao dang roi de muon?', 'Tìm sách Python còn mượn được không?'])
def test_borrowable_topic_routes_to_catalog_with_live_idle_count(state, monkeypatch, question):
    calls = []
    def availability(url):
        calls.append(url)
        return {'status':'available', 'available':2, 'total':3, 'checked_at':'2026-11-03T09:00:00+07:00', 'source_url':url}
    monkeypatch.setattr(assistant, 'get_availability', availability)
    response = assistant.answer_question(state, question)
    assert response['status'] == 'answered' and response['books']
    assert '2/3' in response['answer'] and 'rỗi' in response['answer']
    assert '2026-11-03' in response['answer'] and calls
    assert len(calls) <= 2
    if question == QUESTION:
        assert 'Đăng ký mượn' in response['answer'] and 'mật khẩu' in response['answer']


@pytest.mark.parametrize(('status','count'), [('unavailable',0), ('unknown',None)])
def test_unavailable_and_unknown_are_not_claimed_borrowable(state, monkeypatch, status, count):
    monkeypatch.setattr(assistant, 'get_availability', lambda url: {'status':status,'available':count,'total':3 if count is not None else None,
        'checked_at':'2026-11-03T09:00:00+07:00','source_url':url})
    response = assistant.answer_question(state, QUESTION)
    assert response['books'] and response['sources']
    assert response['status'] == ('needs_confirmation' if status == 'unknown' else 'answered')
    assert ('0/3' if count == 0 else 'Chưa kiểm tra được') in response['answer']


def test_ordinary_search_does_not_fetch_live_counts(state, monkeypatch):
    monkeypatch.setattr(assistant,'get_availability',lambda url:pytest.fail('Ordinary metadata search made live request'))
    response = assistant.answer_question(state,'Tìm sách Python')
    assert response['books'] and response['status'] == 'answered'


@pytest.mark.parametrize('question', ['Có những sách Python nào còn rỗi và phí phạt bao nhiêu?',
    'Có những sách Python nào có thể mượn và thời hạn mượn bao lâu?',
    'Có những sách Python nào có thể mượn và sách Java nào còn rỗi?'])
def test_exclusions_and_fee_requests_are_not_ignored(state, monkeypatch, question):
    monkeypatch.setattr(assistant,'get_availability',lambda url:pytest.fail('Mixed exclusion/fee request must clarify'))
    response = assistant.answer_question(state,question)
    assert response['status'] == 'clarify'
