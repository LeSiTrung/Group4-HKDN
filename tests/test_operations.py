from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.knowledge import today
from app.services.integrations import IntegrationError
from app.api import library, admin


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as c:
        c.post('/api/auth/register',json={'name':'Operator','email':'op@example.test','password':'operator-password-123'})
        with c.app.state.db() as db:
            db.execute("UPDATE users SET role='admin'")
        yield c


def test_verified_schedule_and_closed_exception(client):
    day=today()
    body={'branch':'1','weekday':day.weekday(),'opens':'08:00','closes':'17:00','valid_from':str(day-timedelta(days=30)),
          'valid_until':str(day+timedelta(days=30)),'note':'Test fixture only','verified_by':'Test operator',
          'source_url':'https://lic.ut.edu.vn/','source_title':'Test fixture schedule','checked_at':str(day)}
    assert client.post('/api/admin/schedules',json=body).status_code==201
    result=client.post('/api/chat',json={'message':'Giờ mở cửa hôm nay cơ sở 1'}).json()
    assert '08:00' in result['answer'] and result['sources'][0]['title']=='Test fixture schedule'
    body.update(valid_from=str(day),valid_until=str(day),closed=True,opens='',closes='')
    assert client.post('/api/admin/schedules',json=body).status_code==201
    result=client.post('/api/chat',json={'message':'Giờ mở cửa hôm nay cơ sở 1'}).json()
    assert 'Nghỉ phục vụ' in result['answer'] and '08:00' not in result['answer']


def test_crawl_import_never_publishes(client,monkeypatch):
    monkeypatch.setattr(admin,'crawl_pages',lambda *args:[{'title':'Imported text','url':'https://lic.ut.edu.vn/test-source/','text':'unreviewed policy'}])
    response=client.post('/api/admin/crawl',json={'url':'https://lic.ut.edu.vn/','max_pages':1})
    assert response.status_code==202
    rows=client.get('/api/admin/knowledge').json()
    row=next(r for r in rows if r['title']=='Imported text')
    assert row['published'] is False and row['status']=='needs_confirmation'
    assert client.get('/api/admin/jobs').json()[0]['status']=='done'


def test_renewal_timeout_blocks_different_key(client,monkeypatch):
    monkeypatch.setenv('LIBRARY_RENEW_URL','https://library.example/renew')
    calls=[]
    def timeout(*args):
        calls.append(args)
        raise IntegrationError('uncertain',409,uncertain=True)
    monkeypatch.setattr(library,'library_renew',timeout)
    body={'access_token':'private-fixture-token','loan_id':'loan1','idempotency_key':'first-request-key','confirmation':True}
    assert client.post('/api/library/renew',json=body).status_code==409
    body['idempotency_key']='second-request-key'
    assert client.post('/api/library/renew',json=body).status_code==409
    assert len(calls)==1
    with client.app.state.db() as db:
        assert 'private-fixture-token' not in str([dict(x) for x in db.execute('SELECT * FROM renewals')])


def test_successful_renewal_duplicate_returns_cached_ack(client,monkeypatch):
    monkeypatch.setenv('LIBRARY_RENEW_URL','https://library.example/renew')
    calls=[]
    def success(*args):
        calls.append(args)
        return {'status':'renewed','loan_id':'loan2','due_date':'2026-12-01'}
    monkeypatch.setattr(library,'library_renew',success)
    body={'access_token':'fixture','loan_id':'loan2','idempotency_key':'request-key-cached','confirmation':True}
    first=client.post('/api/library/renew',json=body)
    second=client.post('/api/library/renew',json=body)
    assert first.status_code==second.status_code==200
    assert first.json()==second.json() and len(calls)==1
    body['loan_id']='different'
    assert client.post('/api/library/renew',json=body).status_code==409


def test_feedback_owner_and_delete_history(client):
    reply=client.post('/api/chat',json={'message':'Hướng dẫn tra cứu OPAC'}).json()
    mid,cid=reply['message_id'],reply['conversation_id']
    assert client.post('/api/feedback',json={'message_id':mid,'rating':1}).status_code==200
    assert client.post('/api/feedback',json={'message_id':mid,'rating':0}).status_code==422
    exported=client.get('/api/export').json()
    assert exported['conversations'][0]['id']==cid
    assert 'password_hash' not in str(exported)
    assert client.delete(f'/api/conversations/{cid}').status_code==200
    with client.app.state.db() as db:
        assert db.execute('SELECT count(*) FROM feedback').fetchone()[0]==0


def test_unresolved_renewal_requires_audited_reconciliation(client):
    with client.app.state.db() as db:
        uid=db.execute('SELECT id FROM users').fetchone()[0]
        db.execute("INSERT INTO renewals VALUES ('unresolved-request',?,'loan1','uncertain',NULL)",(uid,))
        db.execute("UPDATE users SET role='reader'")
    assert client.request('DELETE','/api/auth/me',json={'password':'operator-password-123'}).status_code==409
    with client.app.state.db() as db:
        assert db.execute('SELECT state FROM renewals').fetchone()[0]=='uncertain'
        db.execute("UPDATE users SET role='admin'")
    assert client.post('/api/admin/renewals/unresolved-request/reconcile',json={'confirmation':True,'state':'failed','reference':'Synthetic test receipt'}).status_code==200
    with client.app.state.db() as db:
        assert db.execute('SELECT state FROM renewals').fetchone()[0]=='failed'
        assert db.execute("SELECT action FROM audit WHERE action='renewal.reconcile'").fetchone()
