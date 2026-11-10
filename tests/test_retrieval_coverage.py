"""Regression diagnostics from the exposed independent source snapshot, not a new holdout."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.retrieval import retrieve_knowledge


ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def snapshot():
    payload=json.loads((ROOT/'tests/evaluation/independent-library-2026-11-07.json').read_text(encoding='utf-8'))
    rows={}
    for name in ('library.json','public-library-2026-10-31.json'):
        for row in json.loads((ROOT/'data/faq'/name).read_text(encoding='utf-8')):
            row_id=len(rows)+1
            rows[row_id]={**row,'id':row_id}
    for row in payload['source_evidence'].values():
        if 'question' in row:
            rows[row['id']]={**rows.get(row['id'],{'aliases':[],'keywords':[]}),**row}
    return list(rows.values()),{case['id']:case for case in payload['cases']}


@pytest.mark.parametrize(('case_id','expected_first','required'),[
    ('ind-lib-03',24,{24}),
    ('ind-lib-04',22,{22,31}),
    ('ind-lib-07',10,{10}),
    ('ind-lib-13',26,{26}),
])
def test_verbose_service_questions_keep_specific_source_evidence(snapshot,case_id,expected_first,required):
    rows,cases=snapshot
    found=retrieve_knowledge(cases[case_id]['question'],rows)
    assert found['ranked'] and found['ranked'][0][0]['id']==expected_first
    assert required<={row['id'] for row,_ in found['ranked'][:3]}
    for excerpt in found['evidence']:
        row=next(row for row in rows if row['id']==excerpt['source_id'])
        assert excerpt['text'] in row['answer']
    if len(found['ranked'])>1 and found['ranked'][0][0]['category']!=found['ranked'][1][0]['category']:
        assert found['ranked'][0][1]-found['ranked'][1][1]>.08


def test_generic_metadata_does_not_suppress_specific_answer_body():
    generic={'id':1,'question':'Tra cứu thư viện','aliases':[],'keywords':['tra cứu'],
             'answer':'Mở mục lục để tra cứu.','category':'opac'}
    specific={'id':2,'question':'Tài nguyên thông tin','aliases':[],'keywords':[],
              'answer':'AlphaIndex và BetaIndex là danh mục nghiên cứu chuyên ngành.','category':'resources'}
    found=retrieve_knowledge('Tra cứu AlphaIndex và BetaIndex',[generic,specific])
    assert found['ranked'][0][0] is specific
    assert any(excerpt['source_id']==2 for excerpt in found['evidence'])


def test_source_body_supplement_does_not_override_curated_intent():
    author={'id':1,'question':'Tìm theo tác giả hoặc nhan đề như thế nào?','aliases':[],'keywords':[],
            'answer':'Chọn trường tác giả trên OPAC.','category':'opac'}
    incidental={'id':2,'question':'Tải ebook','aliases':[],'keywords':[],
                'answer':'Tìm theo tác giả trên OPAC để tải ebook.','category':'resources'}
    found=retrieve_knowledge('Cách tìm theo tác giả trên OPAC?',[author,incidental])
    assert [row['id'] for row,_ in found['ranked']]==[1]


def test_stale_semantic_row_cannot_restore_withdrawn_evidence(snapshot):
    rows,cases=snapshot
    withdrawn=next(row for row in rows if row['id']==24)
    current=[row for row in rows if row['id']!=24]
    vectors=SimpleNamespace(search_chunks=lambda *args:[{'row':withdrawn,'text':withdrawn['answer'],'score':.99}])
    found=retrieve_knowledge('DOAB DOAJ',current,vectors)
    assert all(row['id']!=24 for row,_ in found['ranked'])
    assert all(excerpt['source_id']!=24 for excerpt in found['evidence'])


def test_unrecognized_words_do_not_turn_one_incidental_token_into_evidence():
    row={'id':1,'question':'Nguồn đọc thêm','aliases':[],'keywords':[],
         'answer':'AlphaIndex có tài liệu tham khảo.','category':'resources'}
    found=retrieve_knowledge('AlphaIndex abcxyz zzzunknown',[row])
    assert found['ranked']==[] and found['evidence']==[]
