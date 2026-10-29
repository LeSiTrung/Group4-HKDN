"""Independent final-review reproductions; synthetic data and mocked IO."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import llm_service
from app.api import library
from app.services.integrations import IntegrationError


@pytest.mark.parametrize('envelope', [{'choices': []}, {'choices': [{'message': {'content': '[' * 3000 + ']' * 3000}}]}])
def test_malformed_openai_envelope_returns_fallback(monkeypatch, envelope):
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.setenv('LLM_BASE_URL', 'https://provider.example/v1')
    monkeypatch.setenv('LLM_API_KEY', 'synthetic-key')
    monkeypatch.setattr(llm_service, 'client', lambda: httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope))))
    assert llm_service.generate_answer('Question', [{'id': 1, 'answer': 'Evidence'}]) is None


@pytest.mark.parametrize('final_state', ['succeeded', 'failed'])
@pytest.mark.parametrize('late_result', ['ack', 'uncertain', 'error'])
def test_inflight_renewal_does_not_overwrite_final_reconciliation(tmp_path, monkeypatch, final_state, late_result):
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/renew')
    with TestClient(create_app(tmp_path, testing=True), headers={'X-Requested-With': 'LibraryAssistant'}) as client:
        client.post('/api/auth/register', json={'name': 'Operator', 'email': 'reviewer@example.test', 'password': 'Synthetic-password-123'})
        with client.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")

        def receive_late_ack(*args):
            receipt = client.post('/api/admin/renewals/inflight-review-key/reconcile', json={'confirmation': True, 'state': final_state, 'reference': 'Official corrected receipt', 'due_date': '2027-01-01' if final_state == 'succeeded' else None})
            assert receipt.status_code == 200
            if late_result == 'uncertain':
                raise IntegrationError('Synthetic timeout', 409, uncertain=True)
            if late_result == 'error':
                raise IntegrationError('Synthetic definite failure', 502, uncertain=False)
            return {'status': 'renewed', 'loan_id': 'loan', 'due_date': '2026-12-01'}

        monkeypatch.setattr(library, 'library_renew', receive_late_ack)
        response = client.post('/api/library/renew', json={'access_token': 'synthetic-token', 'loan_id': 'loan', 'confirmation': True, 'idempotency_key': 'inflight-review-key'})
        record = client.get('/api/admin/renewals').json()[0]
        assert record['state'] == final_state
        assert record['result']['reference'] == 'Official corrected receipt'
        assert record['result']['origin'] == 'manual_reconciliation'
        if final_state == 'succeeded':
            assert record['result']['due_date'] == '2027-01-01'
            assert response.status_code == 200 and response.json() == record['result']
        else:
            assert response.status_code == 409
