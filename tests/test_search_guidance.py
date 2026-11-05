"""Instruction questions must not become catalog queries or inherit a book topic."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services import assistant, catalog
from app.services.knowledge import seed


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS', 'true')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    store = Store(tmp_path/'library.sqlite3')
    seed(store.connect, Path(__file__).resolve().parents[1]/'data/faq/library.json')
    with store.connect() as db:
        for index, title in enumerate(('Hướng dẫn lập trình Python', 'Làm thế nào để kết bạn', 'Hướng dẫn viết luận văn', 'Python cơ bản', 'Học Python như thế nào?', 'Python và hướng dẫn tra cứu trên OPAC')):
            catalog.save_book(db, catalog.BookInput(title=title, published=True,
                checked_at='2026-10-28', source_url='https://lic.ut.edu.vn/synthetic-guidance-book/'+str(index)))
    def unexpected(*args, **kwargs):
        pytest.fail('Reviewed instructions must not require vector retrieval or free generation')
    monkeypatch.setattr(assistant, 'generate_answer', unexpected)
    return SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=False),
        vectors=SimpleNamespace(search=unexpected, search_chunks=unexpected))


@pytest.mark.parametrize('question', [
    'Làm thế nào để tra cứu sách tại thư viện?',
    'Lam the nao de tra cuu sach tai thu vien???',
    '  LÀM THẾ NÀO ĐỂ TRA CỨU SÁCH TẠI THƯ VIỆN?  ',
    'Cách tra cứu sách trên OPAC?',
    'Tra cứu sách tại thư viện bằng cách nào?',
    'Tìm sách trong thư viện ra sao?',
    'Làm sao tìm sách?',
    'Bạn có thể hướng dẫn tôi tìm tài liệu không?',
    'Chỉ cho mình cách kiếm sách với',
    'Tôi muốn biết cách tìm giáo trình',
    'Hướng dẫn tìm luận văn',
    'Cách tra cứu giáo trình ở đâu?',
    'HDSD tra cứu sách trên OPAC',
    'Chỉ tôi tra cứu sách với',
    'Tôi không biết tra cứu sách',
    'OPAC dùng như thế nào?',
    'Làm thế nào để tìm sách “Python nâng cao”?',
    'Làm thế nào để tra cứu sách “Không tìm thấy ánh mặt trời”?',
    'Muốn tra cứu sách thì phải làm gì?',
    'Để tìm sách ở thư viện tôi cần làm gì?',
    'Quy trình tra cứu OPAC gồm những bước nào?',
])
@pytest.mark.parametrize('history', [[], [
    {'role': 'user', 'content': 'Tìm sách Python'},
    {'role': 'assistant', 'content': 'Các sách Python', 'context_query': 'Tìm sách Python'},
]])
def test_lookup_instructions_return_reviewed_steps_not_books(state, question, history):
    response = assistant.answer_question(state, question, history)
    assert response['status'] == 'answered'
    assert response['mode'] == 'faq' and not response.get('books')
    assert 'Nhập tên tài liệu hoặc từ khóa' in response['answer']
    assert 'Chọn nhan đề' in response['answer']
    assert response['sources'][0]['url'].endswith('HDSD_TRACUU_OPAC.v1.1.pdf#page=3')


@pytest.mark.parametrize('question,content,url', [
    ('Làm thế nào để truy cập tài liệu điện tử?', 'điều kiện truy cập', '/opac/'),
    ('Lam the nao de truy cap tai lieu dien tu?', 'điều kiện truy cập', '/opac/'),
    ('Cách tải ebook của thư viện?', 'điều kiện truy cập', '/opac/'),
    ('Tìm tài liệu số và tải ebook thế nào?', 'điều kiện truy cập', '/opac/'),
    ('Tìm sách truyền thống trên OPAC thế nào?', 'Sách truyền thống', 'pdf#page=4'),
    ('Tôi muốn biết cách tìm giáo trình theo tên', 'Chọn trường phù hợp', 'pdf#page=6'),
    ('Làm thế nào để tìm sách theo tác giả?', 'Chọn trường phù hợp', 'pdf#page=6'),
    ('Hướng dẫn tìm kiếm nâng cao trên OPAC', 'AND', '/OSearchAdvanced.aspx'),
    ('OPAC không có kết quả thì làm sao?', 'Thử từ khóa ngắn hơn', '/opac/'),
    ('Tôi tìm sách trên OPAC không ra kết quả', 'Thử từ khóa ngắn hơn', '/opac/'),
])
def test_specialized_lookup_instructions_use_the_relevant_source(state, question, content, url):
    response = assistant.answer_question(state, question)
    assert response['status'] == 'answered' and not response.get('books')
    assert content in response['answer']
    assert response['sources'][0]['url'].endswith(url)


@pytest.mark.parametrize('question,title', [
    ('Tìm sách Hướng dẫn lập trình Python', 'Hướng dẫn lập trình Python'),
    ('Tìm sách Làm thế nào để kết bạn', 'Làm thế nào để kết bạn'),
    ('Tìm sách hướng dẫn viết luận văn', 'Hướng dẫn viết luận văn'),
    ('Tìm sách Python cơ bản', 'Python cơ bản'),
    ('Tìm sách “Học Python như thế nào?”', 'Học Python như thế nào?'),
    ('Tìm sách “Python và hướng dẫn tra cứu trên OPAC”', 'Python và hướng dẫn tra cứu trên OPAC'),
])
def test_instruction_words_inside_an_explicit_title_remain_catalog_search(state, question, title):
    response = assistant.answer_question(state, question)
    assert response['mode'] == 'catalog' and response['status'] == 'answered'
    assert response['books'][0]['title'] == title


@pytest.mark.parametrize('question', [
    'Tìm sách Python và hướng dẫn tra cứu trên OPAC',
    'Hướng dẫn tra cứu OPAC và tìm sách Python',
    'Tìm sách “Python” và hướng dẫn tra cứu trên OPAC',
    'Hướng dẫn tra cứu OPAC và tìm sách “Python”',
    'Tìm sách “Học Python như thế nào?” và hướng dẫn tra cứu OPAC',
])
def test_mixed_lookup_and_instructions_do_not_silently_drop_a_request(state, question):
    response = assistant.answer_question(state, question)
    assert response['status'] == 'clarify' and not response.get('books')


def test_withdrawn_guide_does_not_fall_back_to_an_unrelated_faq(state):
    with state.db() as db:
        db.execute("UPDATE knowledge SET published=0 WHERE source_url LIKE '%pdf#page=3'")
    response = assistant.answer_question(state, 'Làm thế nào để tra cứu sách tại thư viện?')
    assert response['status'] == 'not_found'
    assert not response['sources'] and not response.get('books')


def test_reservation_comparison_is_a_service_question_not_a_book_request(state):
    response = assistant.answer_question(state, 'Đặt chỗ mượn sách khác gia hạn thế nào?')
    assert response['status'] == 'answered' and not response.get('books')
    assert 'gia hạn là kéo dài hạn trả' in response['answer']
    assert response['sources'][0]['url'].endswith('pdf#page=7')
