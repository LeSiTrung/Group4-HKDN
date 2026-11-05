from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services import assistant, catalog
from app.services.knowledge import KnowledgeInput, insert_knowledge, today


QUESTIONS=[
    'Tôi cần chuẩn bị gì để mượn sách?',
    'Toi can chuan bi gi de muon sach?',
    'Mượn sách cần mang những giấy tờ gì?',
    'Tôi muốn mượn sách thì cần làm gì?',
    'Điều kiện mượn tài liệu là gì?',
    'Có cần thẻ sinh viên để mượn sách không?',
]


@pytest.mark.parametrize('question',QUESTIONS)
@pytest.mark.parametrize('with_history',[False,True])
def test_borrowing_procedure_never_searches_book_titles(tmp_path,monkeypatch,question,with_history):
    monkeypatch.setenv('ENABLE_VECTORS','false')
    monkeypatch.setenv('LLM_PROVIDER','none')
    store=Store(tmp_path/'library.sqlite3')
    with store.connect() as db:
        insert_knowledge(db,KnowledgeInput(title='Synthetic borrowing guide',question='Làm thủ tục mượn tài liệu tại quầy như thế nào?',
            aliases=QUESTIONS[:2],keywords=['thủ tục mượn','chuẩn bị','thẻ sinh viên'],
            answer='Hướng dẫn thủ tục mượn tại quầy từ nguồn thử nghiệm; không phải quy định thực tế.',
            category='borrowing_guide',source_title='Synthetic guide',source_url='https://lic.ut.edu.vn/synthetic-borrowing-guide/',
            checked_at=today(),status='reviewed_public',published=True))
        insert_knowledge(db,KnowledgeInput(title='Competing unrelated fixture',question=question,
            answer='Nguồn khác về tài khoản; không trả lời thủ tục tại quầy.',category='resources',
            source_title='Unrelated fixture',source_url='https://lic.ut.edu.vn/synthetic-unrelated/',
            checked_at=today(),status='reviewed_public',published=True))
    state=SimpleNamespace(db=store.connect,settings=SimpleNamespace(testing=False))
    monkeypatch.setattr(assistant,'search_books',lambda *args,**kwargs:pytest.fail('Procedure routed to catalog'))
    monkeypatch.setattr(assistant,'generate_answer',lambda *args,**kwargs:pytest.fail('Procedure must use the reviewed guide, not free generation'))
    history=[{'role':'user','content':'Tìm sách Python'},{'role':'assistant','content':'Các sách Python','context_query':'Tìm sách Python'}] if with_history else []
    response=assistant.answer_question(state,question,history)
    assert response['status']=='answered' and not response.get('books')
    assert response['sources'][0]['url'].endswith('/synthetic-borrowing-guide/')
    assert 'thủ tục' in response['answer']


def test_actual_book_topic_with_procedure_word_still_routes_to_catalog():
    assert catalog.is_book_request('Tìm cho tôi sách về thủ tục hải quan')
