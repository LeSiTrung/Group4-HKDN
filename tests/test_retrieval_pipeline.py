import json
from types import SimpleNamespace

import httpx

from app.services import llm_service


def document(row_id=1, **changes):
    return dict(id=row_id, question='Tài nguyên thư viện', aliases=[], keywords=[],
                answer='Mục lục chung.\n'+'Nội dung giới thiệu. '*100+'\nĐăng nhập kho luận văn bằng tài khoản bạn đọc.',
                category='resources', status='reviewed_public', published=True, source_url='https://lic.ut.edu.vn/',
                source_title='LIC', checked_at='2026-10-28', **changes)


def test_lexical_tail_retrieval_selects_complete_original_excerpts():
    from app.services.retrieval import retrieve_knowledge
    row=document()
    found=retrieve_knowledge('Thư viện đăng nhập kho luận văn bằng tài khoản nào?',[row])
    assert found['ranked'][0][0] is row
    assert found['method']=='keyword' and not found['degraded']
    assert any('kho luận văn' in x['text'] for x in found['evidence'])
    assert all(x['text'] in row['answer'] for x in found['evidence'])


def test_hybrid_fuses_both_channels_and_deduplicates_sources():
    from app.services.retrieval import retrieve_knowledge
    row=document(); other=document(2)
    calls=[]
    def search(question,rows):
        calls.append(question)
        return [{'row':other,'text':'Nội dung giới thiệu.','score':0.7,'chunk_id':'other'},
                {'row':row,'text':'Đăng nhập kho luận văn bằng tài khoản bạn đọc.','score':0.8,'chunk_id':'tail'}]
    found=retrieve_knowledge('Thư viện đăng nhập kho luận văn bằng tài khoản nào?',[row,other],SimpleNamespace(search_chunks=search))
    assert calls and found['method']=='hybrid'
    assert len({r['id'] for r,_ in found['ranked']})==len(found['ranked'])
    assert all(x['source_id'] in (1,2) for x in found['evidence'])


def test_semantic_excerpts_keep_best_hit_first_in_model_evidence():
    from app.services.retrieval import retrieve_knowledge
    row=document()
    best='Đăng nhập kho luận văn bằng tài khoản bạn đọc.'
    hits=[{'row':row,'text':best,'score':.9,'chunk_id':'best'},
          {'row':row,'text':'Nội dung giới thiệu.','score':.6,'chunk_id':'less-relevant'}]
    found=retrieve_knowledge('Thư viện tra cứu hướng dẫn chuyên sâu',[row],SimpleNamespace(search_chunks=lambda *args:hits))
    assert found['evidence'][0]['text']==best


def test_strong_faq_avoids_model_and_vector_work():
    from app.services.retrieval import retrieve_knowledge
    row=document(); row['question']='Tra cứu OPAC'
    def unnecessary(*args):
        raise AssertionError('Exact reviewed FAQ needs no vector search')
    found=retrieve_knowledge('Tra cứu OPAC',[row],SimpleNamespace(search_chunks=unnecessary))
    assert found['ranked']==[(row,10)] and found['method']=='keyword'


def test_curated_question_match_is_not_made_ambiguous_by_incidental_body_words():
    from app.services.retrieval import retrieve_knowledge
    author=document(); author.update(question='Tìm theo tác giả hoặc nhan đề như thế nào?',answer='Chọn trường tác giả trên OPAC.')
    incidental=document(2); incidental.update(question='Tải ebook',answer='Tìm theo tác giả trên OPAC để tải ebook.')
    found=retrieve_knowledge('Cách tìm theo tác giả trên OPAC?',[author,incidental])
    assert [row['id'] for row,_ in found['ranked']]==[1]


def test_long_query_uses_full_lexical_text_without_truncated_embedding():
    from app.services.retrieval import retrieve_knowledge
    row=document()
    calls=[]
    vectors=SimpleNamespace(search_chunks=lambda *args:calls.append(True) or [])
    found=retrieve_knowledge('Thư viện '*100+'đăng nhập kho luận văn bằng tài khoản nào?',[row],vectors)
    assert found['ranked'] and found['method']=='keyword' and found['degraded']
    assert not calls


def test_vector_outage_preserves_lexical_and_rejects_unknown_hit():
    from app.services.retrieval import retrieve_knowledge
    row=document()
    def fail(*args):
        raise RuntimeError('private-provider-url-and-secret')
    found=retrieve_knowledge('Thư viện kho luận văn đăng nhập tài khoản',[row],SimpleNamespace(search_chunks=fail))
    assert found['ranked'] and found['degraded'] and 'private' not in str(found)
    found=retrieve_knowledge('Thư viện hoán dụ abcxyz',[row],SimpleNamespace(search_chunks=lambda *args:[{'row':document(99),'text':'Invented','score':.99,'chunk_id':'fake'}]))
    assert found['ranked']==[]


def model_response(monkeypatch,answer):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    calls=[]
    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={'message':{'content':json.dumps({'answer':answer,'source_ids':[1]})}})
    monkeypatch.setattr(llm_service,'client',lambda:httpx.Client(transport=httpx.MockTransport(handle)))
    return calls


def test_generation_uses_retrieved_excerpt_instead_of_whole_long_source(monkeypatch):
    answer='Đăng nhập kho luận văn bằng tài khoản bạn đọc.'
    calls=model_response(monkeypatch,answer)
    row=document(); row['answer']='Phần giới thiệu. '*600+answer
    assert llm_service.generate_answer('Thư viện đăng nhập kho luận văn thế nào?',[row],evidence=[{'source_id':1,'text':answer,'chunk_id':'tail'}])
    prompt=calls[0]['messages'][-1]['content']
    assert answer in prompt and 'Phần giới thiệu.' not in prompt
    assert 'trích đoạn' in calls[0]['messages'][0]['content'].lower()


def test_generation_cannot_use_numbers_only_in_unseen_source(monkeypatch):
    calls=model_response(monkeypatch,'Tài liệu có 999 trang.')
    row=document(); row['answer']='Tài liệu có 999 trang. Đăng nhập bằng tài khoản bạn đọc.'
    assert llm_service.generate_answer('Thư viện đăng nhập thế nào?',[row],evidence=[{'source_id':1,'text':'Đăng nhập bằng tài khoản bạn đọc.','chunk_id':'selected'}]) is None
    assert calls


def test_chunk_boundary_cannot_turn_part_of_a_number_into_a_grounded_fact(monkeypatch):
    from app.services.rag_service import chunk_text
    row=document(); row['answer']='x '*190+'12345'
    chunks=chunk_text(row['answer'])
    assert chunks[0].endswith('1234')
    model_response(monkeypatch,'Danh mục có 1234 biểu ghi.')
    evidence=[{'source_id':1,'text':text,'chunk_id':str(i)} for i,text in enumerate(chunks)]
    assert llm_service.generate_answer('Danh mục thư viện có bao nhiêu biểu ghi?',[row],evidence=evidence) is None


def test_excerpt_url_prefix_is_not_a_new_supported_destination(monkeypatch):
    model_response(monkeypatch,'Mở https://lic.ut.edu')
    row=document(); row['answer']='Mở https://lic.ut.edu.vn/ để tra cứu.'
    assert llm_service.generate_answer('Tra cứu thư viện ở đâu?',[row],evidence=[{'source_id':1,'text':'Mở https://lic.ut.edu','chunk_id':'partial'}]) is None


def test_fabricated_or_unrelated_excerpt_cannot_reach_provider(monkeypatch):
    calls=model_response(monkeypatch,'Bịa')
    row=document()
    for source_id,text in ((99,row['answer']),(1,'Bằng chứng không có trong nguồn')):
        assert llm_service.generate_answer('Thư viện',[row],evidence=[{'source_id':source_id,'text':text,'chunk_id':'fake'}]) is None
    assert not calls


def test_model_catalog_check_reports_installed_model_without_generating(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','ollama'); monkeypatch.setenv('LLM_MODEL','qwen3:4b')
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,json={'models':[{'name':'qwen3:4b'}]})
    monkeypatch.setattr(llm_service,'client',lambda:httpx.Client(transport=httpx.MockTransport(handle)))
    status=llm_service.check_model()
    assert status['ready'] and status['model_available'] and status['check']=='model_catalog'
    assert calls[0].method=='GET' and calls[0].url.path=='/api/tags'


def test_missing_model_and_external_provider_are_not_claimed_ready(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    monkeypatch.setattr(llm_service,'client',lambda:httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'models':[]}))))
    assert llm_service.check_model()['error']=='model_missing'
    monkeypatch.setenv('LLM_PROVIDER','openai'); monkeypatch.setenv('LLM_BASE_URL','https://provider.example/v1'); monkeypatch.setenv('LLM_API_KEY','private-secret')
    monkeypatch.setattr(llm_service,'client',lambda:(_ for _ in ()).throw(AssertionError('No external API call allowed')))
    status=llm_service.check_model()
    assert status['configured'] and not status['ready'] and 'private-secret' not in str(status)
