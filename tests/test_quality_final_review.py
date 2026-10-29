"""Independent review repros; synthetic catalog/schedule and no provider IO."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import BookInput, save_book
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as client:
        day = today()
        with client.app.state.db() as db:
            for subject in ('Python', 'Java'):
                save_book(db, BookInput(
                    title=f'{subject} cơ bản', author='Synthetic Author',
                    subjects=subject, source_url=f'https://lic.ut.edu.vn/synthetic-{subject}/',
                    checked_at=day, published=True,
                ))
            db.execute('INSERT INTO schedules(branch,weekday,opens,closes,valid_from,valid_until,verified_by,source_url,source_title,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       ('1', day.weekday(), '08:00', '17:00', day.isoformat(), day.isoformat(), 'Synthetic operator', 'https://lic.ut.edu.vn/', 'Synthetic schedule', day.isoformat()))
        yield client


def test_lookup_command_words_do_not_hide_existing_book(client):
    result = client.post('/api/chat', json={'message': 'Tra cứu sách Python'}).json()
    assert any(book['title'] == 'Python cơ bản' for book in result['books']), result


def test_explicit_new_book_topic_replaces_old_context(client):
    result = client.post('/api/chat', json={
        'message': 'Có cuốn Java không?',
        'history': [{'role': 'user', 'content': 'Tìm sách Python'}],
    }).json()
    assert any(book['title'] == 'Java cơ bản' for book in result['books']), result


def test_own_overdue_loan_question_does_not_become_catalog_search(client):
    result = client.post('/api/chat', json={'message': 'Tôi có sách quá hạn, phí bao nhiêu?'}).json()
    assert result['status'] == 'needs_confirmation', result
    assert any('/noi-quy-thu-vien/' in source['url'] for source in result['sources']), result


@pytest.mark.parametrize('other_day', ['mai', 'ngày mốt', (today() + timedelta(days=1)).strftime('ngày %d tháng %m')])
def test_today_and_other_day_cannot_confirm_today_only_window(client, other_day):
    result = client.post('/api/chat', json={'message': f'Giờ mở cửa hôm nay và {other_day} cơ sở 1?'}).json()
    assert result['status'] == 'clarify', result
    assert '08:00' not in result['answer']
