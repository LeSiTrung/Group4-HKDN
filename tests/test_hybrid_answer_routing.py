from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.knowledge import KnowledgeInput, insert_knowledge, published_rows, today


@pytest.mark.parametrize('ambiguous',[False,True])
def test_semantic_similarity_does_not_replace_lexical_intent_confidence(tmp_path,monkeypatch,ambiguous):
    monkeypatch.setenv('ENABLE_VECTORS','true')
    monkeypatch.setenv('LLM_PROVIDER','none')
    with TestClient(create_app(tmp_path,testing=True),headers={'X-Requested-With':'LibraryAssistant'}) as client:
        pack=Path(__file__).resolve().parents[1]/'data/faq/public-library-2026-11-01.json'
        orientation=next(row for row in json.loads(pack.read_text(encoding='utf-8')) if row['category']=='orientation')
        with client.app.state.db() as db:
            insert_knowledge(db,KnowledgeInput.model_validate(orientation))
            if ambiguous:
                insert_knowledge(db,KnowledgeInput(title='Competing library intent',question=orientation['question'],
                    aliases=orientation['aliases'],keywords=orientation['keywords'],answer='Synthetic competing service, not a library rule.',
                    category='resources',source_url='https://lic.ut.edu.vn/synthetic-competing-service/',
                    source_title='Synthetic source',checked_at=today(),status='reviewed_public',published=True))
        rows=published_rows(client.app.state.db)
        target=next(row for row in rows if row['category']=='orientation')
        other=next(row for row in rows if row['question']=='Thư viện có những cơ sở dữ liệu điện tử nào?')
        # Exercise actual fusion with close cosine scores and independently scored keywords.
        monkeypatch.setattr(client.app.state.vectors,'search_chunks',lambda *args:[
            {'row':target,'text':target['answer'],'score':.86,'chunk_id':'class'},
            {'row':other,'text':other['answer'],'score':.84,'chunk_id':'databases'},
        ])
        client.app.state.settings.testing=False
        result=client.post('/api/chat',json={'message':'Thư viện tổ chức lớp hướng dẫn sử dụng và khai thác cơ sở dữ liệu cho bạn đọc như thế nào?'}).json()
        if ambiguous:
            assert result['status']=='clarify' and not result['sources'],result
        else:
            assert result['status']=='answered',result
            assert result['answer']==target['answer'],result
            assert result['sources'][0]['url']==target['source_url'],result
