import hashlib

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api import auth,library
from app.main import create_app


@pytest.mark.parametrize('when',['before_fetch','during_fetch'])
@pytest.mark.parametrize('session_state',['revoked','expired'])
def test_ended_session_cannot_fetch_or_receive_private_library_loans(tmp_path,monkeypatch,when,session_state):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        assert client.post('/api/auth/register',json={'name':'Synthetic loan reader','email':'loans@example.test',
            'password':'Synthetic-loan-password-123'}).status_code==201
        token_hash=hashlib.sha256(client.cookies.get('library_session').encode()).hexdigest()
        calls=[]
        def end_session():
            with client.app.state.db() as db:
                if session_state=='revoked':
                    db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash,))
                else:
                    db.execute('UPDATE sessions SET expires_at=0 WHERE token_hash=?',(token_hash,))
        def provider(token):
            calls.append(token)
            if when=='during_fetch':
                end_session()
            return {'loans':[{'loan_id':'private-loan','title':'Private loan marker'}]}
        if when=='before_fetch':
            def expired_after_auth(request:Request):
                user=auth.optional_user(request)
                end_session()
                return user
            client.app.dependency_overrides[auth.optional_user]=expired_after_auth
        monkeypatch.setattr(library,'library_loans',provider)
        response=client.post('/api/library/loans',json={'access_token':'synthetic-library-token'})
        assert response.status_code==401 and 'Private loan marker' not in response.text
        assert len(calls)==(1 if when=='during_fetch' else 0)
        assert client.cookies.get('library_session') is None
