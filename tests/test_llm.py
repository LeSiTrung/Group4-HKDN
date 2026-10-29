import httpx
from app.services import llm_service


def test_provider_outage_does_not_invent_answer(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    assert llm_service.generate_answer('Question', []) is None


def test_unknown_citation_is_rejected(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    real = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200,json={'message':{'content':'{"answer":"invented","source_ids":[999]}'}}))
    monkeypatch.setattr(llm_service, 'client', lambda: real(transport=transport))
    assert llm_service.generate_answer('Question',[{'id':1,'answer':'Evidence'}]) is None
