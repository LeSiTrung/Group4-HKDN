from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services.assistant import answer_question
from app.services.catalog import BookInput, save_book
from app.services.knowledge import KnowledgeInput, insert_knowledge, today


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    store = Store(tmp_path/'library.sqlite3')
    return SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=True))


@pytest.mark.parametrize('question', ['Thư viện hỗ trợ phát hành tài liệu không?', 'Thu vien ho tro phat hanh tai lieu khong?'])
def test_publishing_does_not_mean_penalty(state, question):
    with state.db() as db:
        insert_knowledge(db, KnowledgeInput(title='Synthetic publishing fixture', question=question,
            answer='Hỗ trợ liên kết nhà xuất bản cho giáo trình đã nghiệm thu.', category='publishing',
            source_url='https://lic.ut.edu.vn/synthetic-publishing/', source_title='Synthetic fixture',
            checked_at=today(), status='reviewed_public', published=True))
    result = answer_question(state, question)
    assert result['status'] == 'answered'
    assert 'nghiệm thu' in result['answer'] and result['sources']


@pytest.mark.parametrize('question', ['Tìm sách phát triển phần mềm', 'Tim sach phat trien phan mem', 'Có sách phát triển phần mềm không?'])
def test_development_book_title_does_not_mean_penalty(state, question):
    with state.db() as db:
        save_book(db, BookInput(title='Phát triển phần mềm', source_url='https://lic.ut.edu.vn/synthetic-development/',
                               checked_at=today(), published=True))
    result = answer_question(state, question)
    assert result['status'] == 'answered' and len(result['books']) == 1


@pytest.mark.parametrize('question', ['Phí phát hành tài liệu bao nhiêu?', 'Mức phạt quá hạn tài liệu bao nhiêu?', 'Phi phat hanh tai lieu bao nhieu?',
    'Thư viện phạt hành vi làm hư tài liệu thế nào?', 'Thu vien phat hanh vi lam hu tai lieu the nao?',
    'Thư viện xử phạt hành chính thế nào?', 'Thu vien xu phat hanh chinh the nao?',
    'Thư viện phạt hành khách thế nào?', 'Thu vien phat hanh khach the nao?'])
def test_real_fee_or_penalty_still_requires_current_authority(state, question):
    with state.db() as db:
        insert_knowledge(db, KnowledgeInput(title='Synthetic unverified source', question=question,
            answer='Dữ liệu thử nghiệm chưa xác nhận mức phí.', category='publishing',
            source_url='https://lic.ut.edu.vn/synthetic-policy-guard/', source_title='Synthetic fixture',
            checked_at=today(), status='reviewed_public', published=True))
    result = answer_question(state, question)
    assert result['status'] == 'needs_confirmation' and result['sources']
