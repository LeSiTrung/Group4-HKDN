from types import SimpleNamespace

import pytest

from app.database.connection import Store
from app.services import catalog, recommendations
from app.services.knowledge import today


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    store = Store(tmp_path/'library.sqlite3')
    return SimpleNamespace(db=store.connect, settings=SimpleNamespace(testing=True))


def add(state, title, **changes):
    with state.db() as db:
        count = db.execute('SELECT COUNT(*) FROM books').fetchone()[0]
        return catalog.save_book(db, catalog.BookInput(title=title,
            source_url=f'https://lic.ut.edu.vn/synthetic-edge-{count}/', checked_at=today(),
            published=True, **changes))


def test_vietnamese_language_topic_does_not_turn_into_any_language(state):
    vietnamese = add(state, 'Giáo trình tiếng Việt')
    add(state, 'Giáo trình tiếng Anh')
    result = recommendations.recommend_books(state, 'Gợi ý sách tiếng Việt')
    assert [b['id'] for b in result['books']] == [vietnamese['id']]
    assert result['books'][0]['url'] == vietnamese['source_url']


@pytest.mark.parametrize('command', ['Tìm sách', 'Gợi ý sách'])
@pytest.mark.parametrize('title,query,other', [
    ('Quyền con người', 'quyen con nguoi', 'Quyền con vật'),
    ('Bạn đọc và thư viện', 'ban doc va thu vien', 'Đọc trong thư viện'),
    ('Người Việt trong lịch sử', 'nguoi viet trong lich su', 'Việt Nam trong lịch sử'),
    ('Những người bạn của tôi', 'nhung nguoi ban cua toi', 'Những người bạn'),
    ('Sách của bạn đọc', 'sach cua ban doc', 'Sách của tôi'),
    ('Giúp bạn đọc hiểu sách', 'giup ban doc hieu sach', 'Đọc hiểu'),
])
def test_search_wrapper_does_not_remove_words_inside_a_title(state, title, query, other, command):
    selected = add(state, title)
    add(state, other)
    question = command + ' ' + title
    parsed = catalog.book_query(question)
    assert parsed == query
    assert [b['id'] for b in catalog.search_books(state, parsed)] == [selected['id']]
    if command == 'Gợi ý sách':
        result = recommendations.recommend_books(state, question)
        assert result['query'] == query
        assert [b['id'] for b in result['books']] == [selected['id']]


def test_exact_title_composed_of_stop_words_is_still_searchable(state):
    selected = add(state, 'Những người bạn của tôi')
    add(state, 'Những người bạn')
    assert [b['id'] for b in catalog.search_books(state, 'nhung nguoi ban cua toi')] == [selected['id']]


@pytest.mark.parametrize('question', [
    'Tìm cho tôi sách về Python', 'Tra cứu sách theo chủ đề Python',
    'Có sách Python không?', 'Gợi ý cho mình 02 cuốn sách Python',
    'Mình muốn đọc sách về Python', 'Sách tương tự Python',
])
def test_grammatical_search_wrappers_are_removed_without_global_word_deletion(question):
    assert catalog.book_query(question) == 'python'


@pytest.mark.parametrize('count,expected', [('02', 2), ('100', 5)])
def test_counts_are_removed_from_the_topic_and_capped_in_results(state, count, expected):
    for number in range(6):
        add(state, f'Python thực hành tập {number + 1}')
    question = f'Gợi ý cho mình {count} cuốn Python'
    assert catalog.is_book_request(question)
    result = recommendations.recommend_books(state, question)
    assert result['query'] == 'python'
    assert len(result['books']) == expected


@pytest.mark.parametrize('count,expected', [('9' * 5000, 5), ('0' * 5000 + '2', 2)])
def test_long_numeric_request_cannot_overflow_integer_parsing(state, count, expected):
    for number in range(6):
        add(state, f'Python thực hành tập {number + 1}')
    result = recommendations.recommend_books(state, f'Gợi ý {count} cuốn Python')
    assert len(result['books']) == expected


def test_learning_verb_before_subject_does_not_prevent_recommendations(state):
    python = add(state, 'Python thực hành')
    add(state, 'Giáo trình tâm lý học')
    result = recommendations.recommend_books(state, 'Gợi ý sách học Python')
    assert [b['id'] for b in result['books']] == [python['id']]


@pytest.mark.parametrize('question', ['Gợi ý sách tâm lý học', 'Gợi ý sách khoa học dữ liệu'])
def test_learning_word_inside_subject_is_not_removed(state, question):
    psychology = add(state, 'Giáo trình tâm lý học')
    data_science = add(state, 'Giáo trình khoa học dữ liệu')
    add(state, 'Giáo trình toán học')
    expected = psychology if 'tâm lý' in question else data_science
    result = recommendations.recommend_books(state, question)
    assert [b['id'] for b in result['books']] == [expected['id']]


@pytest.mark.parametrize('question', [
    'Có cuốn nào học Java cho người mới không?',
    'Có cuốn nào dành cho người mới về Java không?',
    'Có sách nào cho người mới về Java không?',
])
@pytest.mark.parametrize('history', [
    [{'role': 'user', 'content': 'Tìm sách Python'}],
    [{'role': 'assistant', 'content': 'Tài liệu Python.', 'context_query': 'Tìm sách Python'}],
])
def test_explicit_followup_topic_replaces_old_topic(state, question, history):
    add(state, 'Python cơ bản')
    java = add(state, 'Java cơ bản')
    context = catalog.contextual_question(question, history)
    result = recommendations.recommend_books(state, context)
    assert [b['id'] for b in result['books']] == [java['id']]
    assert 'python' not in result['query']


@pytest.mark.parametrize('question', ['Có cuốn nào dành cho người mới không?', 'Có cuốn nào học cơ bản không?',
    'Có sách nào dành cho người mới không?', 'Có quyển nào học cơ bản không?'])
def test_followup_without_a_new_subject_keeps_prior_topic(state, question):
    python = add(state, 'Python cơ bản')
    add(state, 'Java cơ bản')
    context = catalog.contextual_question(question, [{'role': 'user', 'content': 'Tìm sách Python'}])
    result = recommendations.recommend_books(state, context)
    assert [b['id'] for b in result['books']] == [python['id']]


@pytest.mark.parametrize('question', ['Gợi ý cho tôi sách để học tốt hơn', 'Gợi ý sách cho người mới bắt đầu'])
def test_empty_topic_does_not_recommend_arbitrary_published_books(state, question):
    add(state, 'Python cơ bản')
    result = recommendations.recommend_books(state, question)
    assert result['books'] == []
    assert result['query'] == ''


@pytest.mark.parametrize('level,question', [
    ('beginner', 'Gợi ý sách Python cho người mới'),
    ('advanced', 'Gợi ý sách Python nâng cao'),
])
def test_level_evidence_is_grounded_and_excludes_contradictory_metadata(state, level, question):
    beginner = add(state, 'Python thực hành nhập môn')
    advanced = add(state, 'Python chuyên sâu')
    add(state, 'Python cơ bản và nâng cao')
    add(state, 'Python tham khảo')
    expected = beginner if level == 'beginner' else advanced
    result = recommendations.recommend_books(state, question)
    assert [b['id'] for b in result['books']] == [expected['id']]
    assert result['level_unconfirmed'] is False
    assert result['books'][0]['recommendation_reason']


def test_unknown_difficulty_is_reported_without_inventing_level_evidence(state):
    python = add(state, 'Python tham khảo')
    add(state, 'Python nâng cao')
    result = recommendations.recommend_books(state, 'Gợi ý sách Python cho người mới')
    assert [b['id'] for b in result['books']] == [python['id']]
    assert result['level_unconfirmed'] is True
    assert 'mức phù hợp' not in result['books'][0]['recommendation_reason']
