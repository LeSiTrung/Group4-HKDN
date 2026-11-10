"""Local transaction safety contracts; synthetic accounts and no external IO."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.api import library
from app.main import create_app
from app.services.integrations import IntegrationError


HEADERS={'X-Requested-With':'LibraryAssistant'}
PASSWORD='Synthetic-transaction-password-123'
BODY={'access_token':'synthetic-library-token','loan_id':'synthetic-loan',
      'idempotency_key':'synthetic-transaction-key','confirmation':True}


def register(client,email='reader@example.test'):
    response=client.post('/api/auth/register',json={'name':'Synthetic reader','email':email,'password':PASSWORD})
    assert response.status_code==201
    return response.json()['user']


@pytest.fixture
def app(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    monkeypatch.setenv('LIBRARY_RENEW_URL','https://bridge.example/synthetic-renew')
    return create_app(tmp_path,testing=True)


@pytest.mark.parametrize('operation',['loans','renew'])
def test_anonymous_cannot_call_library_provider(app,monkeypatch,operation):
    monkeypatch.setattr(library,'library_'+operation,lambda *args:pytest.fail('Anonymous request reached provider'))
    with TestClient(app,headers=HEADERS) as client:
        assert client.post('/api/library/'+operation,json=BODY).status_code==401
        with app.state.db() as db:
            assert db.execute('SELECT count(*) FROM renewals').fetchone()[0]==0


@pytest.mark.parametrize('confirmation',[None,False])
def test_renewal_requires_explicit_confirmation(app,monkeypatch,confirmation):
    monkeypatch.setattr(library,'library_renew',lambda *args:pytest.fail('Unconfirmed request reached provider'))
    with TestClient(app,headers=HEADERS) as client:
        register(client)
        body={**BODY,'confirmation':confirmation}
        if confirmation is None:
            body.pop('confirmation')
        assert client.post('/api/library/renew',json=body).status_code==422
        with app.state.db() as db:
            assert db.execute('SELECT count(*) FROM renewals').fetchone()[0]==0


def test_unconfigured_renewal_sends_nothing_and_creates_no_ledger_entry(app,monkeypatch):
    monkeypatch.delenv('LIBRARY_RENEW_URL')
    monkeypatch.setattr(library,'library_renew',lambda *args:pytest.fail('Unconfigured request reached provider'))
    with TestClient(app,headers=HEADERS) as client:
        register(client)
        assert client.post('/api/library/renew',json=BODY).status_code==503
        with app.state.db() as db:
            assert db.execute('SELECT count(*) FROM renewals').fetchone()[0]==0


@pytest.mark.parametrize(('length','expected'),[(129,200),(200,200),(201,422)])
def test_renewal_accepts_the_bridge_loan_id_length_limit(app,monkeypatch,length,expected):
    calls=[]
    def provider(token,loan_id,key):
        calls.append(loan_id)
        return {'status':'renewed','loan_id':loan_id,'due_date':'2026-12-01'}
    monkeypatch.setattr(library,'library_renew',provider)
    with TestClient(app,headers=HEADERS) as client:
        register(client)
        loan_id='L'*length
        response=client.post('/api/library/renew',json={**BODY,'loan_id':loan_id})
        assert response.status_code==expected
        assert calls==([loan_id] if expected==200 else [])


def test_another_account_cannot_read_cached_receipt_or_reconcile(app,monkeypatch):
    calls=[]
    def provider(*args):
        calls.append(args)
        return {'status':'renewed','loan_id':BODY['loan_id'],'due_date':'2026-12-01','message':'Private receipt marker'}
    monkeypatch.setattr(library,'library_renew',provider)
    with TestClient(app,headers=HEADERS) as client:
        register(client)
        assert client.post('/api/library/renew',json=BODY).status_code==200
        assert client.post('/api/auth/logout').status_code==200
        register(client,'other-reader@example.test')
        response=client.post('/api/library/renew',json=BODY)
        assert response.status_code==409 and 'Private receipt marker' not in response.text
        assert client.get('/api/admin/renewals').status_code==403
        assert client.post('/api/admin/renewals/'+BODY['idempotency_key']+'/reconcile',json={
            'confirmation':True,'state':'failed','reference':'Synthetic forbidden reconciliation'}).status_code==403
        assert len(calls)==1


def test_concurrent_duplicate_is_not_sent_twice(app,monkeypatch):
    started,finish=Event(),Event()
    calls=[]
    def provider(*args):
        calls.append(args)
        started.set()
        assert finish.wait(10),'Synthetic provider was not released'
        return {'status':'renewed','loan_id':BODY['loan_id'],'due_date':'2026-12-01'}
    monkeypatch.setattr(library,'library_renew',provider)
    with TestClient(app,headers=HEADERS) as client:
        register(client)
        with ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(client.post,'/api/library/renew',json=BODY)
            try:
                assert started.wait(10),'Synthetic provider was not called'
                assert client.post('/api/library/renew',json=BODY).status_code==409
            finally:
                finish.set()
            result=first.result(timeout=10)
        assert result.status_code==200
        assert client.post('/api/library/renew',json=BODY).json()==result.json()
        assert len(calls)==1


def test_uncertain_renewal_survives_restart_until_audited_reconciliation(app,tmp_path,monkeypatch):
    calls=[]
    def timeout(*args):
        calls.append(args)
        raise IntegrationError('Synthetic timeout',409,uncertain=True)
    monkeypatch.setattr(library,'library_renew',timeout)
    with TestClient(app,headers=HEADERS) as client:
        register(client)
        assert client.post('/api/library/renew',json=BODY).status_code==409
    with TestClient(create_app(tmp_path,testing=True),headers=HEADERS) as client:
        assert client.post('/api/auth/login',json={'email':'reader@example.test','password':PASSWORD}).status_code==200
        for key in (BODY['idempotency_key'],'synthetic-retry-with-new-key'):
            assert client.post('/api/library/renew',json={**BODY,'idempotency_key':key}).status_code==409
        assert len(calls)==1
        with client.app.state.db() as db:
            row=dict(db.execute('SELECT * FROM renewals').fetchone())
            assert row['state']=='uncertain' and BODY['access_token'] not in str(row)
            db.execute("UPDATE users SET role='admin'")
        receipt=client.post('/api/admin/renewals/'+BODY['idempotency_key']+'/reconcile',json={
            'confirmation':True,'state':'succeeded','reference':'Synthetic library receipt','due_date':'2026-12-02'})
        assert receipt.status_code==200
        assert client.post('/api/library/renew',json=BODY).json()==receipt.json()['result']
        with client.app.state.db() as db:
            assert db.execute("SELECT count(*) FROM audit WHERE action='renewal.reconcile'").fetchone()[0]==1
        assert len(calls)==1
