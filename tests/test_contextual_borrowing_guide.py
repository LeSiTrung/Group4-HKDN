from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services import assistant, llm_service
from app.services.knowledge import KnowledgeInput, insert_knowledge, today


QUESTION = 'Vậy tôi muốn mượn sách ở thư viện để mang về trong 2 ngày thì phải làm sao, tôi muốn mượn sách ở cơ sở 3 trường mình'
GUIDE = 'Xuất trình thẻ bạn đọc. Mang sách đến quầy thủ thư để ghi mượn. Kiểm tra hạn trả trước khi rời quầy.'


@pytest.mark.parametrize('output,mode', [
    ('1,2', 'rag'),
    ('Bạn được mượn tối đa hai ngày tại cơ sở 3.', 'fallback'),
    (None, 'fallback'),
])
def test_detailed_borrowing_uses_local_model_without_adding_policy(tmp_path, monkeypatch, output, mode):
    monkeypatch.setenv('LLM_PROVIDER', 'ollama')
    store = Store(tmp_path/'library.sqlite3')
    with store.connect() as db:
        insert_knowledge(db, KnowledgeInput(title='Hướng dẫn thử nghiệm', question='Thủ tục mượn tại quầy',
            answer=GUIDE, category='borrowing_guide', source_title='Thư viện UTH',
            source_url='https://lic.ut.edu.vn/synthetic-borrowing/', checked_at=today(),
            status='reviewed_public', published=True))

    calls = []
    def generate(messages, schema):
        calls.append(messages)
        return {'answer': output} if output else None

    monkeypatch.setattr(llm_service, '_generate', generate)
    state = SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=False))
    response = assistant.answer_question(state, QUESTION)
    assert len(calls) == 1 and 'Mang sách đến quầy thủ thư' in calls[0][-1]['content']
    assert response['mode'] == mode and response['status'] == 'needs_confirmation'
    assert 'cơ sở 3' in response['answer'] and '2 ngày' in response['answer']
    assert 'xác nhận' in response['answer'] and 'được mượn tối đa' not in response['answer']
    assert ' '.join(GUIDE.split()) in ' '.join(response['answer'].split())
    assert 'thẻ bạn đọc.\n\nMang sách' in response['answer']
    assert response['sources'][0]['url'].endswith('/synthetic-borrowing/')
