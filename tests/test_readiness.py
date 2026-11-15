import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app import main


def test_blank_crawl_interval_disables_scheduler_and_shuts_down(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAWL_INTERVAL_HOURS', '')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/ready').status_code == 200


@pytest.mark.parametrize('interval', ['invalid', 'inf', 'nan'])
def test_invalid_crawl_interval_fails_at_startup(tmp_path, monkeypatch, interval):
    monkeypatch.setenv('CRAWL_INTERVAL_HOURS', interval)
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    with pytest.raises(ValueError, match='CRAWL_INTERVAL_HOURS'):
        with TestClient(create_app(tmp_path)):
            pytest.fail('Invalid crawl configuration reached a running server')


@pytest.mark.parametrize('ready',[False,True])
def test_readiness_checks_configured_model_and_database(tmp_path,monkeypatch,ready):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    monkeypatch.setattr(main,'check_model',lambda:{'ready':ready,'configured':True})
    with TestClient(create_app(tmp_path,testing=True)) as client:
        response=client.get('/ready')
        assert response.status_code==(200 if ready else 503)
        assert response.json()=={'status':'ready' if ready else 'unavailable','checks':{'database':True,'model':ready}}


def test_readiness_database_failure_is_not_a_successful_healthcheck(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    with TestClient(create_app(tmp_path,testing=True)) as client:
        def unavailable():
            raise OSError('private database details')
        client.app.state.db=unavailable
        response=client.get('/ready')
        assert response.status_code==503
        assert response.json()['checks']['database'] is False
        assert 'private' not in response.text


def test_faq_only_service_does_not_require_a_model(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setattr(main,'check_model',lambda:pytest.fail('Disabled LLM must not be contacted'))
    with TestClient(create_app(tmp_path,testing=True)) as client:
        assert client.get('/ready').status_code==200


@pytest.mark.parametrize('withdrawal',[
    'published=0',
    "valid_from='9999-01-01'",
    "valid_until='2000-01-01'",
])
def test_readiness_requires_knowledge_that_can_be_served(tmp_path,monkeypatch,withdrawal):
    monkeypatch.setenv('LLM_PROVIDER','none')
    with TestClient(create_app(tmp_path,testing=True)) as client:
        with client.app.state.db() as db:
            db.execute('UPDATE knowledge SET '+withdrawal)
        response=client.get('/ready')
        assert response.status_code==503,response.json()
        assert response.json()['checks']=={'database':False,'model':True}
        with client.app.state.db() as db:
            db.execute('UPDATE knowledge SET published=1,valid_from=NULL,valid_until=NULL WHERE id=(SELECT MIN(id) FROM knowledge)')
        assert client.get('/ready').status_code==200
