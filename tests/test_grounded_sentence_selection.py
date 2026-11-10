import json

import httpx
import pytest

from app.services.llm_service import generate_answer


def provider(monkeypatch,selection):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    monkeypatch.setattr('app.services.llm_service.client',lambda:httpx.Client(transport=httpx.MockTransport(
        lambda request:httpx.Response(200,json={'message':{'content':json.dumps({'answer':selection})}}))))


def test_model_selects_source_sentences_and_server_renders_facts_and_citations(monkeypatch):
    provider(monkeypatch,'2,1')
    rows=[{'id':24,'answer':'DOAB giới thiệu sách truy cập mở.'},
          {'id':25,'answer':'DOAJ giới thiệu tạp chí truy cập mở.'}]
    assert generate_answer('Hai nguồn khác nhau thế nào?',rows)=={
        'answer':'DOAJ giới thiệu tạp chí truy cập mở.\n\nDOAB giới thiệu sách truy cập mở.',
        'source_ids':[25,24]}


def test_same_sentence_selected_from_two_sources_is_read_once_with_both_citations(monkeypatch):
    provider(monkeypatch,'1,2')
    sentence='Đăng nhập trực tiếp trên OPAC, không gửi mật khẩu trong chat.'
    generated=generate_answer('Đăng nhập thư viện thế nào?',[
        {'id':1,'answer':sentence},{'id':2,'answer':sentence},
    ])
    assert generated['answer']==sentence
    assert generated['source_ids']==[1,2]


@pytest.mark.parametrize('selection',['0','3','1,1','1,999','true','1,2.5','1,DOAB có tạp chí','','9'*5000])
def test_invalid_sentence_selections_cannot_reach_the_user(monkeypatch,selection):
    provider(monkeypatch,selection)
    assert generate_answer('Tra cứu',[{'id':1,'answer':'Dùng OPAC để tra cứu.'}]) is None


def test_partial_excerpt_never_becomes_an_affirmative_sentence(monkeypatch):
    provider(monkeypatch,'1')
    assert generate_answer('Có mang sách ra ngoài được không?',
        [{'id':1,'answer':'Không được tự mang sách ra ngoài.'}],
        evidence=[{'source_id':1,'text':'được tự mang sách ra ngoài.','chunk_id':'partial'}]) is None


@pytest.mark.parametrize('source,fragment',[
    ('Không được\ntự mang sách ra ngoài.','tự mang sách ra ngoài.'),
    ('Chỉ khi được thủ thư đồng ý,\nbạn mới được mang sách ra ngoài.','bạn mới được mang sách ra ngoài.'),
    ('Các hành vi bị cấm:\n- Mang sách ra ngoài mà chưa ghi mượn.','- Mang sách ra ngoài mà chưa ghi mượn.'),
    ('Các hành vi bị cấm:\n1. Làm hỏng sách.\n2. Mang sách ra ngoài.','2. Mang sách ra ngoài.'),
])
def test_wrapped_rule_cannot_be_selected_without_its_condition(monkeypatch,source,fragment):
    provider(monkeypatch,'1')
    assert generate_answer('Có thể mang sách ra ngoài không?', [{'id':1,'answer':source}],
        evidence=[{'source_id':1,'text':fragment,'chunk_id':'wrapped-tail'}]) is None


def test_model_can_select_complete_wrapped_rule(monkeypatch):
    provider(monkeypatch,'1')
    generated=generate_answer('Có thể mang sách ra ngoài không?',
        [{'id':1,'answer':'Không được\ntự mang sách ra ngoài.'}])
    assert generated=={'answer':'Không được tự mang sách ra ngoài.','source_ids':[1]}


@pytest.mark.parametrize('claim',[
    'Đã gia hạn thành công cho bạn.',
    'Mình đã giữ chỗ cho bạn.',
    'Mình đã giữ một bản cho bạn.',
    'Giữ chỗ thành công.',
    'Minh da giu cho cho ban.',
    'Mình đã\ngiữ chỗ cho bạn.',
])
def test_source_sentence_cannot_masquerade_as_a_completed_transaction(monkeypatch,claim):
    provider(monkeypatch,'1')
    assert generate_answer('Gia hạn giúp tôi',[{'id':1,'answer':claim}]) is None


def test_pending_transaction_guidance_can_still_be_selected(monkeypatch):
    provider(monkeypatch,'1')
    sentence='Bạn có thể giữ chỗ trên OPAC nếu biểu ghi hỗ trợ.'
    generated=generate_answer('Giữ chỗ thế nào?',[{'id':1,'answer':sentence}])
    assert generated and generated['answer']==sentence
