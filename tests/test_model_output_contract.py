import json

import httpx
import pytest

from app.services import llm_service


@pytest.mark.parametrize('answer',['Nguồn bị lỗi \ud800','\udfff'])
def test_model_invalid_unicode_is_rejected_before_it_can_break_chat_response(monkeypatch,answer):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    def provider(request):
        return httpx.Response(200,json={'message':{'content':json.dumps({'answer':answer,'source_ids':[1]})}})
    monkeypatch.setattr(llm_service,'client',lambda:httpx.Client(transport=httpx.MockTransport(provider)))
    result=llm_service.generate_answer('Hướng dẫn tra cứu sách',[{'id':1,'answer':'Dùng OPAC để tìm tài liệu.'}])
    assert result is None


def test_model_preserves_valid_vietnamese_and_emoji(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    answer='Bạn có thể tìm tài liệu tại OPAC 📚.'
    def provider(request):
        return httpx.Response(200,json={'message':{'content':json.dumps({'answer':answer,'source_ids':[1]})}})
    monkeypatch.setattr(llm_service,'client',lambda:httpx.Client(transport=httpx.MockTransport(provider)))
    result=llm_service.generate_answer('Hướng dẫn tra cứu sách',[{'id':1,'answer':'Dùng OPAC để tìm tài liệu.'}])
    assert result=={'answer':answer,'source_ids':[1]}
