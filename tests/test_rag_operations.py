import json
import sys
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import cli
from app.main import create_app
from app.services import llm_service
from app.services.knowledge import today


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as client:
        assert client.post('/api/auth/register', json={'name': 'Operator', 'email': 'rag@example.test',
            'password': 'operator-password-123'}).status_code == 201
        with client.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
            db.execute('DELETE FROM knowledge')
        yield client


def add_source(client, **changes):
    body = {'title': 'Synthetic retrieval fixture', 'question': 'Tra cứu mục lục OPAC',
        'answer': 'Mở mục lục OPAC để tra cứu tài liệu.', 'aliases': [], 'keywords': ['mục lục', 'OPAC'],
        'category': 'faq', 'source_url': 'https://lic.ut.edu.vn/synthetic/',
        'source_title': 'Synthetic source', 'checked_at': str(today()),
        'status': 'reviewed_public', 'published': True}
    body.update(changes)
    response = client.post('/api/admin/knowledge', json=body)
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize('path,body', [('/api/admin/ai/check', None), ('/api/admin/retrieval', {'query': 'OPAC'})])
def test_diagnostics_require_admin(client, path, body):
    with client.app.state.db() as db:
        db.execute("UPDATE users SET role='reader'")
    assert client.post(path, json=body).status_code == 403
    client.cookies.clear()
    assert client.post(path, json=body).status_code == 401


@pytest.mark.parametrize('query', ['', '   ', 'x' * 1001])
def test_preview_rejects_blank_or_oversized_queries(client, query):
    assert client.post('/api/admin/retrieval', json={'query': query}).status_code == 422


def test_preview_only_includes_current_reviewed_sources_and_no_reader_data(client):
    row = add_source(client)
    add_source(client, published=False, answer='draft-private-marker')
    add_source(client, status='needs_confirmation', answer='unreviewed-private-marker')
    add_source(client, valid_until=str(today() - timedelta(days=1)), answer='expired-private-marker')
    with client.app.state.db() as db:
        conversation = db.execute("INSERT INTO conversations(user_id,title) VALUES (1,'private-reader-marker')").lastrowid
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user','private-reader-marker')", (conversation,))
    response = client.post('/api/admin/retrieval', json={'query': 'Tra cứu mục lục OPAC'})
    assert response.status_code == 200
    result = response.json()
    assert result['method'] == 'keyword' and result['degraded'] is False
    assert len(result['sources']) == 1
    source = result['sources'][0]
    assert source['id'] == row['id'] and source['source_url'] == row['source_url']
    assert source['checked_at'] == str(today()) and source['score'] > 0
    assert source['excerpts'] and 'OPAC' in ' '.join(source['excerpts'])
    assert 'private-marker' not in response.text and 'private-reader-marker' not in response.text


def test_preview_empty_has_no_model_or_vector_side_effects(client, monkeypatch):
    monkeypatch.setattr(client.app.state.vectors, '_init', lambda: pytest.fail('preview initialized disabled vectors'))
    monkeypatch.setattr(llm_service, '_generate', lambda *a: pytest.fail('preview generated an answer'))
    result = client.post('/api/admin/retrieval', json={'query': 'Không có nguồn phù hợp'}).json()
    assert result == {'method': 'none', 'degraded': False, 'sources': []}


def test_preview_only_lists_sources_selected_for_context(client):
    rows = [add_source(client, answer=f'Nguồn thử nghiệm OPAC số {number}.') for number in range(4)]
    response = client.post('/api/admin/retrieval', json={'query': 'Tra cứu mục lục OPAC'})
    assert response.status_code == 200
    assert [source['id'] for source in response.json()['sources']] == [row['id'] for row in rows[:3]]
    assert all(source['excerpts'] for source in response.json()['sources'])


@pytest.mark.parametrize('enabled,testing,uses_vectors', [
    ('false', False, False), ('true', True, False), ('true', False, True)])
def test_preview_obeys_vector_configuration(client, monkeypatch, enabled, testing, uses_vectors):
    from app.services import retrieval
    monkeypatch.setenv('ENABLE_VECTORS', enabled)
    client.app.state.settings.testing = testing
    def retrieve(question, rows, vectors=None):
        assert (vectors is client.app.state.vectors) is uses_vectors
        return {'ranked': [], 'evidence': [], 'method': 'none', 'degraded': False}
    monkeypatch.setattr(retrieval, 'retrieve_knowledge', retrieve)
    assert client.post('/api/admin/retrieval', json={'query': 'OPAC'}).status_code == 200


def test_model_check_reports_outage_without_secrets_or_generation(client, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('LLM_API_KEY', 'private-key-marker')
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:11434')
    def handler(request):
        assert request.method == 'GET' and request.url.path == '/api/tags'
        raise httpx.ConnectError('private-key-marker provider raw error', request=request)
    monkeypatch.setattr(llm_service, 'client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    response = client.post('/api/admin/ai/check')
    assert response.status_code == 200
    assert response.json()['ready'] is False and response.json()['reachable'] is False
    assert response.json()['check'] == 'model_catalog'
    assert 'private-key-marker' not in response.text and 'provider raw error' not in response.text


@pytest.mark.parametrize('models,ready', [([], False), ([{'name': 'synthetic:latest'}], True)])
def test_model_check_requires_selected_model_in_catalog(client, monkeypatch, models, ready):
    monkeypatch.setenv('LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('LLM_MODEL', 'synthetic:latest')
    def handler(request):
        assert request.method == 'GET' and request.url.path == '/api/tags'
        return httpx.Response(200, json={'models': models})
    monkeypatch.setattr(llm_service, 'client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    response = client.post('/api/admin/ai/check')
    assert response.status_code == 200
    assert response.json()['reachable'] is True
    assert response.json()['model_available'] is ready and response.json()['ready'] is ready


def test_reindex_keeps_source_count_and_reports_namespace_totals(client, monkeypatch):
    monkeypatch.setattr(client.app.state.vectors, 'rebuild', lambda rows: 2)
    monkeypatch.setattr(client.app.state.vectors, 'status', lambda: {
        'ready': True, 'namespaces': {'knowledge': {'sources': 2, 'chunks': 6}}})
    result = client.post('/api/admin/reindex').json()
    assert result['count'] == 2 and result['status'] == 'ready'
    assert result['namespaces']['knowledge'] == {'sources': 2, 'chunks': 6}


@pytest.mark.parametrize('ready', [False, True])
def test_ai_check_cli_returns_readiness_without_creating_database(tmp_path, monkeypatch, capsys, ready):
    result = {'provider': 'ollama', 'model': 'synthetic', 'configured': True, 'ready': ready,
        'reachable': ready, 'model_available': ready, 'error': None if ready else 'unreachable', 'check': 'model_catalog'}
    monkeypatch.setattr(llm_service, 'check_model', lambda: result, raising=False)
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'unused-runtime'))
    monkeypatch.setattr(sys, 'argv', ['app.cli', 'ai-check'])
    with pytest.raises(SystemExit) as exit:
        cli.main()
    assert exit.value.code == (0 if ready else 1)
    assert json.loads(capsys.readouterr().out) == result
    assert not (tmp_path / 'unused-runtime').exists()


def test_index_cli_reports_chunk_totals_and_releases_lock(tmp_path, monkeypatch, capsys):
    class Index:
        model_name = 'synthetic'
        closed = False
        def __init__(self, settings):
            pass
        def rebuild(self, rows):
            return 2
        def status(self):
            return {'ready': True, 'namespaces': {'knowledge': {'sources': 2, 'chunks': 6}}}
        def close(self):
            Index.closed = True
    monkeypatch.setattr(cli, 'VectorIndex', Index)
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setattr(sys, 'argv', ['app.cli', 'index'])
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert result['indexed'] == 2 and result['namespaces']['knowledge'] == {'sources': 2, 'chunks': 6}
    assert Index.closed
