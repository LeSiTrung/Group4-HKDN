import json
import pytest
from fastapi.testclient import TestClient
from app.main import create_app


PASSWORD = 'feedback-test-password-123'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as c:
        c.post('/api/auth/register', json={'email': 'reader@example.test', 'name': 'Private Reader', 'password': PASSWORD})
        yield c


def admin(client):
    with client.app.state.db() as db:
        db.execute("UPDATE users SET role='admin'")


def rated_answer(client, rating=1, question='Question', answer='Answer', comment='Comment'):
    with client.app.state.db() as db:
        user_id = db.execute('SELECT id FROM users').fetchone()[0]
        conversation_id = db.execute('INSERT INTO conversations(user_id,title) VALUES (?,?)', (user_id, 'Private title')).lastrowid
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user','Unrelated private turn')", (conversation_id,))
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user',?)", (conversation_id, question))
        message_id = db.execute("INSERT INTO messages(conversation_id,role,content,sources,status,mode) VALUES (?,'assistant',?,?,'answered','faq')", (conversation_id, answer, json.dumps([{'title': 'Source', 'url': 'https://lic.uth.edu.vn/'}]))).lastrowid
    assert client.post('/api/feedback', json={'message_id': message_id, 'rating': rating, 'comment': comment}).status_code == 200
    return conversation_id, message_id


def test_feedback_review_requires_admin(client):
    assert client.get('/api/admin/feedback').status_code == 403
    client.cookies.clear()
    assert client.get('/api/admin/feedback').status_code == 401


def test_review_only_exposes_rated_turn_and_immediate_question(client):
    _, first = rated_answer(client, question='<script>unsafe question</script>', comment='<img src=x onerror=alert(1)>')
    _, second = rated_answer(client, rating=-1)
    with client.app.state.db() as db:
        conversation_id = db.execute('SELECT id FROM conversations ORDER BY id DESC').fetchone()[0]
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'assistant','Unrated private answer')", (conversation_id,))
    admin(client)
    result = client.get('/api/admin/feedback', params={'page_size': 1}).json()
    assert result['summary'] == {'positive': 1, 'negative': 1}
    assert (result['total'], result['page'], result['page_size']) == (2, 1, 1)
    assert result['items'][0]['message_id'] == second
    item = client.get('/api/admin/feedback', params={'rating': 1}).json()['items'][0]
    assert set(item) == {'message_id', 'question', 'answer', 'rating', 'comment', 'status', 'mode', 'sources'}
    assert item['message_id'] == first
    assert item['question'] == '<script>unsafe question</script>'
    assert item['comment'] == '<img src=x onerror=alert(1)>'
    assert item['sources'] == [{'title': 'Source', 'url': 'https://lic.uth.edu.vn/'}]
    assert 'Private' not in json.dumps(result) and 'Unrelated' not in json.dumps(result)
    assert client.get('/api/admin/feedback', params={'page': 2, 'page_size': 1}).json()['items'][0]['message_id'] == first
    assert client.get('/api/admin/feedback', params={'page': 3, 'page_size': 1}).json()['items'] == []


def test_preceding_question_never_crosses_conversation_or_skips_turn(client):
    other_conversation, _ = rated_answer(client)
    with client.app.state.db() as db:
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user','Private question in another conversation')", (other_conversation,))
    _, message_id = rated_answer(client)
    with client.app.state.db() as db:
        conversation_id = db.execute('SELECT conversation_id FROM messages WHERE id=?', (message_id,)).fetchone()[0]
        previous = db.execute('SELECT id FROM messages WHERE conversation_id=? AND id<? ORDER BY id DESC LIMIT 1', (conversation_id, message_id)).fetchone()[0]
        db.execute("UPDATE messages SET role='assistant', content='Private preceding answer' WHERE id=?", (previous,))
    admin(client)
    assert client.get('/api/admin/feedback').json()['items'][0]['question'] == ''
    with client.app.state.db() as db:
        db.execute('DELETE FROM messages WHERE conversation_id=? AND id<?', (conversation_id, message_id))
    assert client.get('/api/admin/feedback').json()['items'][0]['question'] == ''


def test_large_valid_page_is_empty_not_server_error(client):
    rated_answer(client)
    admin(client)
    result = client.get('/api/admin/feedback', params={'page': 10**30})
    assert result.status_code == 200
    assert result.json()['items'] == []


@pytest.mark.parametrize('params', [{'rating': 0}, {'rating': 2}, {'rating': 'bad'}, {'page': 0}, {'page_size': 0}, {'page_size': 51}])
def test_review_validates_query_bounds(client, params):
    admin(client)
    assert client.get('/api/admin/feedback', params=params).status_code == 422


@pytest.mark.parametrize('delete_account', [False, True])
def test_feedback_disappears_after_owner_deletion(client, delete_account):
    conversation_id, _ = rated_answer(client)
    if delete_account:
        assert client.request('DELETE', '/api/auth/me', json={'password': PASSWORD}).status_code == 200
        client.post('/api/auth/register', json={'email': 'other@example.test', 'name': 'Admin', 'password': PASSWORD})
        admin(client)
    else:
        assert client.delete(f'/api/conversations/{conversation_id}').status_code == 200
        admin(client)
    assert client.get('/api/admin/feedback').json() == {'items': [], 'total': 0, 'page': 1, 'page_size': 20, 'summary': {'positive': 0, 'negative': 0}}
