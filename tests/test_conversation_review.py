"""Conversation regressions using a temporary synthetic catalog and no model IO."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.catalog import BookInput, save_book


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as client:
        with client.app.state.db() as db:
            save_book(db, BookInput(
                title='Python cho người mới', author='Trần An', year='2025',
                subjects='Python; lập trình; người mới',
                description='Synthetic beginner programming fixture, not real library inventory.',
                source_url='https://lic.ut.edu.vn/synthetic-conversation-python/',
                checked_at='2026-10-28', published=True,
            ))
        yield client


def ask(client, message, followup=False):
    payload = {'message': message}
    if followup:
        payload['history'] = [{'role': 'user', 'content': 'Tìm sách về Python'}]
    response = client.post('/api/chat', json=payload)
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize('message', ['Có sách Python không?', 'Tim cuon Python cho nguoi moi'])
def test_natural_catalog_requests_retrieve_reviewed_record(client, message):
    reply = ask(client, message)
    assert any(book['title'] == 'Python cho người mới' for book in reply['books'])
    assert any(source['url'].endswith('/synthetic-conversation-python/') for source in reply['sources'])


@pytest.mark.parametrize(('message', 'value'), [
    ('Tác giả là ai?', 'Trần An'),
    ('Nam xuat ban la nam nao?', '2025'),
])
def test_bare_attribute_followup_uses_previous_book(client, message, value):
    reply = ask(client, message, followup=True)
    assert value in reply['answer']
    assert reply['books']


@pytest.mark.parametrize('message', ['Cuốn đó có ISBN là gì?', 'Cuốn đó ở kệ nào?'])
def test_missing_book_metadata_reports_its_limit_without_losing_book(client, message):
    reply = ask(client, message, followup=True)
    assert reply['books']
    assert reply['status'] == 'needs_confirmation'


@pytest.mark.parametrize(('message', 'followup'), [
    ('Tìm sách về Python, còn mượn được không?', False),
    ('Cuon do con muon duoc khong?', True),
])
def test_circulation_question_preserves_book_and_requires_live_confirmation(client, message, followup):
    reply = ask(client, message, followup=followup)
    assert reply['books']
    assert reply['status'] == 'needs_confirmation'


def test_negated_author_does_not_return_excluded_author_as_match(client):
    reply = ask(client, 'Tìm sách về Python không phải Trần An')
    assert reply['status'] == 'clarify' or all(book['author'] != 'Trần An' for book in reply['books'])


def test_mixed_book_and_hours_question_is_not_reported_as_absent_book(client):
    reply = ask(client, 'Tìm sách về Python. Thư viện mở cửa lúc mấy giờ hôm nay?')
    assert reply['status'] == 'clarify' or reply['books']
