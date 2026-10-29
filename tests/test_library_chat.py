"""Library-only scope and long-message transport/storage; no live providers."""
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services import assistant, llm_service


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','none')
    monkeypatch.setenv('ENABLE_VECTORS','false')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        yield client


@pytest.mark.parametrize('question',['Python','Tôi muốn học Python','Email là gì?','Cơ sở dữ liệu là gì?','Phi trong toán học là gì?','2 + 3 bằng bao nhiêu?','Viết giúp tôi một bài văn'])
def test_outside_topic_redirects_to_library(client,monkeypatch,question):
    monkeypatch.setattr(assistant,'generate_answer',lambda *args: pytest.fail('General knowledge has no library evidence'))
    result=client.post('/api/chat',json={'message':question}).json()
    assert result['status'] in ('clarify','not_found') and result['suggestions']
    assert result['mode']!='general' and not result['sources']
    assert 'thư viện' in result['answer'] and not hasattr(llm_service,'generate_chat')


@pytest.mark.parametrize('question',['Xin chào bạn','Chào thư viện','Cảm ơn bạn','Alo'])
def test_social_messages_are_library_focused(client,question):
    result=client.post('/api/chat',json={'message':question}).json()
    assert result['status']=='answered' and result['suggestions']
    assert 'thư viện' in result['answer'] and not result['sources']


def register(client,email):
    assert client.post('/api/auth/register',json={'name':'Long reader','email':email,'password':'synthetic-long-password-2026'}).status_code==201


def test_long_original_reaches_answer_and_history_without_clipping(client):
    question='  Hướng dẫn tra cứu OPAC\n'+('Tôi cần tìm tài liệu. '*250)+'  '
    seen=[]
    client.app.state.answer=lambda q,h=None: seen.append(q) or {'answer':'Thông điệp kiểm thử.','status':'answered','sources':[],'suggestions':[],'mode':'faq'}
    register(client,'long-reader@example.test')
    response=client.post('/api/chat',json={'message':question})
    assert response.status_code==200 and seen==[question]
    cid=response.json()['conversation_id']
    assert client.get(f'/api/conversations/{cid}').json()['messages'][0]['content']==question


def test_large_utf8_payload_is_stored_whole_with_explicit_context_notice(client,monkeypatch):
    question='Nội dung thư viện cần hỗ trợ. '*4000
    monkeypatch.setattr(assistant,'generate_answer',lambda *args: pytest.fail('Oversized context must not call provider'))
    register(client,'large-reader@example.test')
    response=client.post('/api/chat',json={'message':question})
    assert response.status_code==200
    result=response.json()
    assert result['status']=='clarify' and 'chia' in result['answer']
    assert client.get(f"/api/conversations/{result['conversation_id']}").json()['messages'][0]['content']==question


@pytest.mark.parametrize('question,history',[
    ('Có phục vụ sau 20h không?',[{'role':'user','content':'Giờ mở cửa hôm nay cơ sở 1'}]),
    ('Thứ bảy?',[{'role':'user','content':'Giờ mở cửa hôm nay cơ sở 1'},{'role':'assistant','content':'Cần xác nhận.'},{'role':'user','content':'Còn hôm nay?'}]),
])
def test_followup_retains_library_evidence_boundary(client,monkeypatch,question,history):
    monkeypatch.setattr(assistant,'generate_answer',lambda *args: pytest.fail('Unknown hours cannot be generated'))
    result=client.post('/api/chat',json={'message':question,'history':history}).json()
    assert result['status']=='clarify' and result['mode']!='general'
    assert '21' not in result['answer']


def test_large_history_is_bounded_before_catalog_search(client,monkeypatch):
    monkeypatch.setattr(assistant,'search_books',lambda *args: pytest.fail('Context limit precedes expensive search'))
    result=client.post('/api/chat',json={'message':'Có cuốn nào dành cho người mới?','history':[{'role':'user','content':'Tìm sách về '+'python '*6000}]}).json()
    assert result['status']=='clarify' and 'ngữ cảnh' in result['answer']


def test_transport_bound_remains_for_chat_and_other_routes(client):
    assert client.post('/api/chat',content=b'x'*(1048576+1)).status_code==413
    assert client.post('/api/auth/logout',content=b'x'*65537).status_code==413
