import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app import main


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
