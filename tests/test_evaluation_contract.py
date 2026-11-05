from pathlib import Path
from runpy import run_path

import json
from collections import OrderedDict


def test_evaluation_rejects_wrong_answer_provenance_mode():
    check=run_path(str(Path(__file__).resolve().parents[1]/'scripts/evaluate.py'))['failures']
    case={'status':'answered','mode':'rag'}
    assert check(case,{'status':'answered','answer':'A response','mode':'faq'})
    assert not check(case,{'status':'answered','answer':'A response','mode':'rag'})


def test_offline_evaluation_never_contacts_live_opac(tmp_path, monkeypatch):
    from app.services import opac_availability
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    monkeypatch.setenv('ENABLE_VECTORS', 'false')
    def unexpected(*args, **kwargs):
        raise AssertionError('Offline evaluation contacted the live OPAC')
    monkeypatch.setattr(opac_availability, '_fetch', unexpected)
    monkeypatch.setattr(opac_availability, '_cache', OrderedDict())
    cases=tmp_path/'cases.json'
    cases.write_text(json.dumps([{'id':'offline-availability',
        'message':'Tìm sách Olympic cơ học, còn mượn được không?',
        'status':'needs_confirmation','book':'10 năm Olympic cơ học'}]),encoding='utf-8')
    output=tmp_path/'report.json'
    monkeypatch.setattr('sys.argv',['evaluate','--cases',str(cases),'--output',str(output)])
    main=run_path(str(Path(__file__).resolve().parents[1]/'scripts/evaluate.py'))['main']
    assert main()==0
    report=json.loads(output.read_text(encoding='utf-8'))
    assert report['passed']==1
    assert all(book['availability_snapshot']['status']=='unknown' for book in report['results'][0]['response']['books'])
