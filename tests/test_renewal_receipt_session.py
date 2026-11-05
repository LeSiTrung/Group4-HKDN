import hashlib

import pytest
from fastapi.testclient import TestClient

from app.api import library
from app.main import create_app
from app.services.integrations import IntegrationError


@pytest.mark.parametrize('session_state',['revoked','expired'])
@pytest.mark.parametrize(('provider_result','ledger_state'),[('ack','succeeded'),('timeout','uncertain'),('rejected','failed')])
def test_sent_renewal_keeps_provider_result_but_does_not_disclose_it_to_ended_session(tmp_path,monkeypatch,session_state,provider_result,ledger_state):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    monkeypatch.setenv('LIBRARY_RENEW_URL','https://bridge.example/synthetic-renew')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        assert client.post('/api/auth/register',json={'name':'Synthetic renewal reader','email':'receipt@example.test',
            'password':'Synthetic-receipt-password-123'}).status_code==201
        token_hash=hashlib.sha256(client.cookies.get('library_session').encode()).hexdigest()
        def provider(*args):
            with client.app.state.db() as db:
                if session_state=='revoked':
                    db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash,))
                else:
                    db.execute('UPDATE sessions SET expires_at=0 WHERE token_hash=?',(token_hash,))
            if provider_result=='timeout':
                raise IntegrationError('Synthetic uncertain acknowledgement',409,uncertain=True)
            if provider_result=='rejected':
                raise IntegrationError('Synthetic definite rejection',502,uncertain=False)
            return {'status':'renewed','loan_id':'synthetic-loan','due_date':'2026-12-01'}
        monkeypatch.setattr(library,'library_renew',provider)
        response=client.post('/api/library/renew',json={'access_token':'synthetic-bridge-token','loan_id':'synthetic-loan',
            'confirmation':True,'idempotency_key':'synthetic-receipt-key'})
        with client.app.state.db() as db:
            record=db.execute('SELECT * FROM renewals WHERE idempotency_key=?',('synthetic-receipt-key',)).fetchone()
        assert record['state']==ledger_state
        if provider_result=='ack':
            assert '2026-12-01' in record['result']
        assert response.status_code==401 and '2026-12-01' not in response.text
        assert client.cookies.get('library_session') is None


def test_late_receipt_cannot_update_a_replacement_account_reusing_numeric_id_and_key(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    monkeypatch.setenv('LIBRARY_RENEW_URL','https://bridge.example/synthetic-renew')
    app=create_app(tmp_path,testing=True)
    headers={'X-Requested-With':'LibraryAssistant'}
    password='Synthetic-original-password-123'
    with TestClient(app,headers=headers) as admin,TestClient(app,headers=headers) as original,TestClient(app,headers=headers) as replacement:
        assert admin.post('/api/auth/register',json={'name':'Synthetic admin','email':'admin@example.test','password':password}).status_code==201
        with app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
        first=original.post('/api/auth/register',json={'name':'Original reader','email':'original@example.test','password':password}).json()['user']
        key='synthetic-reused-receipt-key'
        def provider(*args):
            assert admin.post('/api/admin/renewals/'+key+'/reconcile',json={'confirmation':True,'state':'failed',
                'reference':'Synthetic confirmed rejection'}).status_code==200
            assert original.request('DELETE','/api/auth/me',json={'password':password}).status_code==200
            second=replacement.post('/api/auth/register',json={'name':'Replacement reader','email':'replacement@example.test',
                'password':'Synthetic-replacement-password-456'}).json()['user']
            assert second['id']==first['id']
            # The new account has independently accepted a new operation with this key.
            with app.state.db() as db:
                db.execute("INSERT INTO renewals VALUES(?,?,?,'pending',NULL)",(key,second['id'],'synthetic-loan'))
            return {'status':'renewed','loan_id':'synthetic-loan','due_date':'2026-12-01'}
        monkeypatch.setattr(library,'library_renew',provider)
        response=original.post('/api/library/renew',json={'access_token':'synthetic-original-token','loan_id':'synthetic-loan',
            'confirmation':True,'idempotency_key':key})
        with app.state.db() as db:
            record=db.execute('SELECT state,result FROM renewals WHERE idempotency_key=?',(key,)).fetchone()
        assert record['state']=='pending' and record['result'] is None
        assert response.status_code==409 and '2026-12-01' not in response.text
