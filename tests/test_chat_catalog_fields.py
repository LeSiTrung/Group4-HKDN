from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services.assistant import answer_question
from app.services.catalog import BookInput, save_book
from app.services.knowledge import today


@pytest.fixture
def state(tmp_path):
    store = Store(tmp_path/'library.sqlite3')
    with store.connect() as db:
        for index, (title, author, subjects) in enumerate([
            ('Mở cửa tương lai', 'Nguyễn Văn An', ''),
            ('Tình trạng giao thông', 'Lê Minh', ''),
            ('Python thực hành', 'Trần Bình', ''),
            ('Sổ tay lập trình', 'Lê Minh', 'Python thực hành'),
            ('Tra cứu tài liệu theo tác giả Nguyễn Văn An', 'Trần Bình', ''),
        ]):
            save_book(db, BookInput(title=title, author=author, subjects=subjects,
                source_url=f'https://lic.ut.edu.vn/synthetic-fields/{index}', checked_at=today(), published=True))
    return SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=True))


@pytest.mark.parametrize('question,title', [
    ('Tìm sách “Mở cửa tương lai”', 'Mở cửa tương lai'),
    ('Tra cứu sách “Tình trạng giao thông”', 'Tình trạng giao thông'),
    ('Tra cứu theo nhan đề Python thực hành', 'Python thực hành'),
    ('Tìm sách theo nhan đề Python thực hành', 'Python thực hành'),
    ('Tra cứu tài liệu theo tác giả Nguyễn Văn An', 'Mở cửa tương lai'),
    ('Tìm theo tác giả Nguyễn Văn An', 'Mở cửa tương lai'),
])
def test_explicit_fields_and_quoted_titles_return_only_matching_books(state, question, title):
    response = answer_question(state, question)
    assert response['status'] == 'answered'
    assert [book['title'] for book in response['books']] == [title]


def test_author_followup_retains_title_field(state):
    response = answer_question(state, 'Tác giả là ai?', [
        {'role': 'user', 'content': 'Tra cứu theo nhan đề Python thực hành'},
    ])
    assert response['status'] == 'answered'
    assert 'Trần Bình' in response['answer']
