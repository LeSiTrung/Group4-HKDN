import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.parametrize('loans,renewal', [(False,False),(True,False),(False,True),(True,True)])
def test_health_distinguishes_loans_from_renewal(tmp_path,monkeypatch,loans,renewal):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    monkeypatch.setenv('LIBRARY_LOANS_URL','https://example.test/loans' if loans else '')
    monkeypatch.setenv('LIBRARY_RENEW_URL','https://example.test/renew' if renewal else '')
    with TestClient(create_app(tmp_path,testing=True)) as client:
        capabilities=client.get('/health').json()['capabilities']
        assert capabilities['library_loans_configured'] is loans
        assert capabilities['library_configured'] is renewal
