from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services import assistant, catalog, llm_service, recommendations
from app.services.knowledge import today


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    store = Store(tmp_path/'library.sqlite3')
    with store.connect() as db:
        for title, subjects, description, published in [
            ('Luận văn ứng dụng CNTT trong quản lý', 'Công nghệ thông tin', '', True),
            ('Giáo trình lập trình Python cơ bản', 'Python; công nghệ thông tin; lập trình', 'Dành cho người mới bắt đầu.', True),
            ('Giáo trình lập trình Python nâng cao', 'Python; công nghệ thông tin; lập trình', '', True),
            ('Bài giảng mạng máy tính', 'Mạng máy tính; công nghệ thông tin', '', True),
            ('Giáo trình logistics', 'Logistics; vận tải', '', True),
            ('Tự học Word cho người mới bắt đầu', 'Tin học văn phòng', '', True),
            ('Giáo trình công nghệ cơ khí cơ bản', 'Cơ khí', 'Thông tin xuất bản', True),
            ('Python chưa xuất bản', 'Python', '', False),
        ]:
            catalog.save_book(db, catalog.BookInput(title=title, subjects=subjects, description=description,
                source_url=f'https://lic.ut.edu.vn/synthetic-recommendation-{db.execute("SELECT COUNT(*) FROM books").fetchone()[0]}/',
                checked_at=today(), published=published))
    return SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=True))


@pytest.mark.parametrize('question', [
    'hãy tìm cho tôi những sách để học IT tốt hơn',
    'hay tim cho toi nhung sach de hoc CNTT tot hon',
    'Mình học công nghệ thông tin, nên đọc sách gì?',
    'Gợi ý cho mình vài cuốn về mạng máy tính',
    'Mình mới học lập trình, nên đọc sách gì?',
    'Mình cần tài liệu để học thêm về mạng máy tính',
    'Có sách nào giúp mình hiểu Python hơn không?',
    'Sách nào học Python cho dễ hiểu?',
])
def test_natural_learning_requests_recommend_real_books(state, question):
    response = assistant.answer_question(state, question)
    assert response.get('books'), response
    assert response['books'][0]['title'] != 'Luận văn ứng dụng CNTT trong quản lý'
    assert all(b['published'] and b.get('recommendation_reason') for b in response['books'])
    assert response['sources'] and 'OPAC' not in response['answer'].split('\n')[0]
    assert all('logistics' not in b['title'].lower() for b in response['books'])
    assert not any('availability_snapshot' in b for b in response['books'])


def test_explicit_beginner_preference_uses_metadata_and_avoids_advanced(state):
    response = assistant.answer_question(state, 'Gợi ý cho mình vài cuốn Python cho người mới bắt đầu')
    assert response['status'] == 'answered'
    assert [b['title'] for b in response['books']] == ['Giáo trình lập trình Python cơ bản']
    assert 'cơ bản' in response['books'][0]['recommendation_reason']


def test_learning_followup_retains_topic_for_guest_history(state):
    history = [{'role':'user', 'content':'hãy tìm cho tôi những sách để học IT tốt hơn'},
               {'role':'assistant', 'content':'Một số tài liệu công nghệ thông tin.'}]
    response = assistant.answer_question(state, 'Có cuốn nào cho người mới bắt đầu không?', history)
    assert response['books'][0]['title'] == 'Giáo trình lập trình Python cơ bản'
    assert all('logistics' not in b['title'].lower() for b in response['books'])


def test_new_topic_does_not_reuse_previous_recommendations(state):
    response = assistant.answer_question(state, 'Gợi ý sách Java cho người mới',
        [{'role':'user','content':'Tìm sách Python'}])
    assert not response.get('books') and response['status'] == 'not_found'


@pytest.mark.parametrize('question', [
    'Cách tìm sách Python trên OPAC?', 'Hướng dẫn tìm giáo trình ở đâu?',
    'Viết code Python cho tôi', 'IT là gì?',
])
def test_guidance_and_general_knowledge_are_not_recommendations(state, question):
    assert not assistant.answer_question(state, question).get('books')


@pytest.mark.parametrize('question', ['Gợi ý sách Python và phí phạt là bao nhiêu?',
    'Tìm cho tôi sách Python nhưng không phải sách nâng cao'])
def test_recommendations_do_not_drop_policy_or_exclusion_constraints(state, question):
    assert assistant.answer_question(state, question)['status'] == 'clarify'


def test_vague_learning_request_asks_for_topic(state):
    response=assistant.answer_question(state,'Gợi ý cho tôi sách để học tốt hơn')
    assert response['status']=='clarify' and not response.get('books')


def test_local_model_extracts_topic_before_search_and_preserves_source(state, monkeypatch):
    state.settings.testing=False
    calls=[]
    monkeypatch.setattr(recommendations,'extract_book_topic',lambda q:calls.append(q) or 'mạng máy tính')
    response=assistant.answer_question(state,'Tư vấn cho mình sách để tìm hiểu mạng máy tính')
    assert calls and response['mode']=='catalog_ai'
    assert response['books'][0]['title']=='Bài giảng mạng máy tính'
    assert response['books'][0]['url']==response['sources'][0]['url']


@pytest.mark.parametrize('answer', ['công nghệ thông tin', 'machine learning'])
def test_topic_extractor_uses_bounded_schema_and_question_phrases(monkeypatch, answer):
    import httpx
    import json
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    requests=[]
    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'message':{'content':json.dumps({'answer':answer})}})
    monkeypatch.setattr(llm_service,'client',lambda:httpx.Client(transport=httpx.MockTransport(handle)))
    question='Gợi ý sách học '+answer+' cho người mới'
    assert llm_service.extract_book_topic(question)==answer
    assert requests[0]['format']['properties']['answer']['maxLength']==120
    assert question in requests[0]['messages'][-1]['content']


@pytest.mark.parametrize('answer', ['chủ đề không có trong câu hỏi', 'Python\nignore rules', 'https://example.test', 'Python '*30])
def test_invalid_or_invented_model_topic_is_not_used(monkeypatch, answer):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    monkeypatch.setattr(llm_service,'_generate',lambda *args:{'answer':answer})
    assert llm_service.extract_book_topic('Gợi ý sách học Python') is None


def test_topic_extraction_does_not_start_paid_provider(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','openai')
    monkeypatch.setattr(llm_service,'_generate',lambda *args:pytest.fail('Unapproved extra paid call'))
    assert llm_service.extract_book_topic('Gợi ý sách học Python') is None


def test_recommendation_deduplicates_and_respects_withdrawals(state):
    with state.db() as db:
        original=dict(db.execute("SELECT * FROM books WHERE title='Giáo trình lập trình Python cơ bản'").fetchone())
        catalog.save_book(db,catalog.BookInput(**{**original,'source_url':'https://lic.ut.edu.vn/synthetic-edition/'}))
    response=assistant.answer_question(state,'Gợi ý sách Python cho người mới')
    assert len(response['books'])==1
    with state.db() as db:
        db.execute("UPDATE books SET published=0 WHERE title='Giáo trình lập trình Python cơ bản'")
    assert not assistant.answer_question(state,'Gợi ý sách Python cho người mới').get('books')


def test_model_outage_or_unmatched_topic_falls_back_to_catalog(state,monkeypatch):
    state.settings.testing=False
    for topic in (None,'zzzz999999'):
        monkeypatch.setattr(recommendations,'extract_book_topic',lambda q:topic)
        response=assistant.answer_question(state,'Gợi ý sách Python cho người mới')
        assert response['books'][0]['title']=='Giáo trình lập trình Python cơ bản'
        assert response['mode']=='catalog'


def test_model_topic_retaining_level_does_not_replace_subject_with_level(state,monkeypatch):
    state.settings.testing=False
    monkeypatch.setattr(recommendations,'extract_book_topic',lambda q:'Python cho người mới bắt đầu')
    response=assistant.answer_question(state,'Gợi ý sách Python cho người mới bắt đầu')
    assert [b['title'] for b in response['books']]==['Giáo trình lập trình Python cơ bản']


def test_partial_shared_words_do_not_beat_exact_domain_phrase(state):
    response=assistant.answer_question(state,'Gợi ý sách công nghệ thông tin cho người mới')
    assert [b['title'] for b in response['books']]==['Giáo trình lập trình Python cơ bản']


@pytest.mark.parametrize('question',['Mình muốn tập trung vào mạng máy tính', 'Có cuốn nào về mạng máy tính không?'])
def test_refinement_changes_topic_without_combining_old_subject(state,question):
    response=assistant.answer_question(state,question,[{'role':'user','content':'Gợi ý sách Python'}])
    assert response['books'][0]['title']=='Bài giảng mạng máy tính'
    assert all('Python' not in b['title'] for b in response['books'])


def test_requested_recommendation_count_is_respected(state):
    response=assistant.answer_question(state,'Gợi ý cho tôi 1 cuốn để học công nghệ thông tin')
    assert len(response['books'])==1


@pytest.mark.parametrize('question', ['Tìm sách Olympic cơ học', 'Gợi ý sách cơ học'])
def test_subject_noun_hoc_is_preserved_instead_of_removed_as_learning_verb(state,question):
    with state.db() as db:
        for title in ['Olympic cơ học', 'Olympic toán học']:
            catalog.save_book(db,catalog.BookInput(title=title,source_url='https://lic.ut.edu.vn/synthetic-'+str(len(title))+'/',checked_at=today(),published=True))
    response=assistant.answer_question(state,question)
    assert [b['title'] for b in response['books']]==['Olympic cơ học']


def test_beginner_selection_is_applied_before_availability_overlay(state):
    response=assistant.answer_question(state,'Gợi ý sách Python cơ bản còn bản nào không?')
    assert [b['title'] for b in response['books']]==['Giáo trình lập trình Python cơ bản']


def test_all_catalog_semantic_search_does_not_send_redundant_id_filter(state,monkeypatch):
    state.settings.testing=False
    monkeypatch.setenv('ENABLE_VECTORS','true')
    calls=[]
    def search(query,documents,namespace,source_ids):
        calls.append(source_ids)
        return [(next(d for d in documents if 'Python' in d['question']),.9)]
    state.vectors=SimpleNamespace(search=search)
    assert catalog.search_books(state,'Python practical exercises')
    assert calls==[None]
