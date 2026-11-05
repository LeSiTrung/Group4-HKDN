import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import channels
from app.database.connection import Store


@pytest.fixture
def client(tmp_path,monkeypatch):
    for key,value in {'MESSENGER_APP_SECRET':'synthetic-secret','MESSENGER_PAGE_ACCESS_TOKEN':'synthetic-token',
        'MESSENGER_PAGE_ID':'page','MESSENGER_GRAPH_VERSION':'v26.0','ZALO_APP_ID':'app','ZALO_OA_ID':'oa',
        'ZALO_OA_SECRET_KEY':'synthetic-secret','ZALO_ACCESS_TOKEN':'synthetic-token'}.items():
        monkeypatch.setenv(key,value)
    app=FastAPI()
    app.include_router(channels.router,prefix='/api')
    app.state.db=Store(tmp_path/'library.sqlite3').connect
    app.state.answer=lambda text:{'answer':'Bạn có thể tìm tài liệu qua OPAC.'}
    def acknowledged(request):
        return httpx.Response(200,json={'message_id':'outgoing'} if request.url.host=='graph.facebook.com' else {'error':0,'data':{'message_id':'outgoing'}})
    monkeypatch.setattr(channels,'_client',lambda:httpx.Client(transport=httpx.MockTransport(acknowledged)))
    with TestClient(app) as result:
        yield result


def send(client,channel,event):
    stamp=int(time.time()*1000)
    if channel=='messenger':
        payload={'object':'page','entry':[{'id':'page','messaging':[{'sender':{'id':event['recipient']},
            'recipient':{'id':'page'},'timestamp':stamp,'message':{'mid':event['message_id'],'text':event['text']}}]}]}
        raw=json.dumps(payload).encode()
        headers={'x-hub-signature-256':'sha256='+hmac.new(b'synthetic-secret',raw,hashlib.sha256).hexdigest()}
    else:
        payload={'app_id':'app','event_name':'user_send_text','timestamp':str(stamp),
            'sender':{'id':event['recipient']},'recipient':{'id':'oa'},
            'message':{'msg_id':event['message_id'],'text':event['text']}}
        raw=json.dumps(payload).encode()
        headers={'x-zevent-signature':'mac='+hashlib.sha256(b'app'+raw+str(stamp).encode()+b'synthetic-secret').hexdigest()}
    return client.post('/api/webhooks/'+channel,content=raw,headers=headers)


@pytest.mark.parametrize('channel',['messenger','zalo'])
@pytest.mark.parametrize('field',['recipient','message_id','text'])
def test_signed_malformed_unicode_is_ignored_without_claiming_or_sending(client,channel,field):
    event={'recipient':'reader','message_id':'incoming','text':'Tìm tài liệu'}
    event[field]='invalid\ud800'
    response=send(client,channel,event)
    assert response.status_code==200 and response.json()['processed']==0
    with client.app.state.db() as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='channel_events'").fetchone()
        assert not exists or db.execute('SELECT COUNT(*) FROM channel_events').fetchone()[0]==0


@pytest.mark.parametrize('channel',['messenger','zalo'])
def test_valid_vietnamese_emoji_message_is_delivered_and_deduplicated(client,channel):
    event={'recipient':'reader','message_id':'incoming-vietnamese','text':'Tìm sách tiếng Việt 📚'}
    first=send(client,channel,event)
    second=send(client,channel,event)
    assert first.status_code==200 and first.json()['processed']==1
    assert second.status_code==200 and second.json()['processed']==0
    with client.app.state.db() as db:
        assert db.execute('SELECT status FROM channel_events').fetchall()[0]['status']=='sent'
