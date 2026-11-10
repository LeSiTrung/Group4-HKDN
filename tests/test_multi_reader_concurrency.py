from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app


def test_five_readers_can_save_conversations_concurrently_without_cross_account_access(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    headers={'X-Requested-With':'LibraryAssistant'}
    with TestClient(create_app(tmp_path,testing=True),headers=headers) as host:
        clients=[TestClient(host.app,headers=headers) for _ in range(5)]
        try:
            for index,client in enumerate(clients):
                response=client.post('/api/auth/register',json={'name':f'Synthetic {index}',
                    'email':f'synthetic-{index}@example.test','password':'Synthetic-concurrency-password-123'})
                assert response.status_code==201
            def converse(client):
                first=client.post('/api/chat',json={'message':'Xin chào'})
                assert first.status_code==200
                cid=first.json()['conversation_id']
                second=client.post('/api/chat',json={'message':'Hướng dẫn tra cứu OPAC','conversation_id':cid})
                assert second.status_code==200 and second.json()['sources']
                return cid
            with ThreadPoolExecutor(max_workers=5) as pool:
                ids=list(pool.map(converse,clients))
            assert len(set(ids))==5
            for index,client in enumerate(clients):
                history=client.get(f'/api/conversations/{ids[index]}').json()
                assert len(history['messages'])==4
                assert client.get(f'/api/conversations/{ids[(index+1)%5]}').status_code==404
            with host.app.state.db() as db:
                assert db.execute('SELECT count(*) FROM conversations').fetchone()[0]==5
                assert db.execute('SELECT count(*) FROM messages').fetchone()[0]==20
        finally:
            for client in clients:
                client.close()
