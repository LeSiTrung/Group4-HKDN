import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from runpy import run_path

import pytest

from app.database.connection import Store
from app.services import dspace_catalog

ID='0009688f-12f3-4902-9b95-7a31e878ee77'
OTHER='0028316f-de77-4ebc-80bb-eb1fb365d3f2'


def snapshot(identifier=ID, **record_changes):
    record={'uuid':identifier,'name':'Nghiên cứu XML','type':'item','inArchive':True,
        'withdrawn':False,'discoverable':True,'metadata':{
            'dc.contributor.author':[{'value':'Nguyễn A'},{'value':'GVHD: ThS. Nguyễn B'}],
            'dc.date.issued':[{'value':'2006'}],
            'creativework.keywords':[{'value':'XML'}],
            'dc.subject':[{'value':'Công nghệ thông tin'}],
            'dc.type':[{'value':'Khóa luận'}]}}
    record.update(record_changes)
    return {'source_url':'https://thuvienso.ut.edu.vn/items/'+identifier,
        'fetched_at':datetime.now(timezone.utc).isoformat(),
        'sha256':hashlib.sha256(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'record':record}


def test_normalize_public_metadata_preserves_provenance_and_missing_abstract():
    source=snapshot()
    row=dspace_catalog.normalize_snapshot(source,published=True)
    assert row.title=='Nghiên cứu XML' and row.author=='Nguyễn A'
    assert row.kind=='digital' and row.year=='2006' and row.description==''
    assert row.source_url==source['source_url'] and row.published is True
    assert 'XML' in row.subjects and 'Khóa luận' in row.subjects
    assert len(source['record']['metadata']['dc.contributor.author'])==2


@pytest.mark.parametrize('changes,reason',[
    ({'withdrawn':True},'not_public_archived'),
    ({'inArchive':False},'not_public_archived'),
    ({'discoverable':False},'not_public_archived'),
    ({'discoverable':None},'not_public_archived'),
    ({'inArchive':'true'},'not_public_archived'),
    ({'type':'collection'},'not_item'),
    ({'name':'x'*501},'field_limits'),
    ({'name':'   '},'missing_title'),
])
def test_normalization_rejects_nonpublic_and_invalid_records(changes,reason):
    with pytest.raises(ValueError,match=reason):
        dspace_catalog.normalize_snapshot(snapshot(**changes))


@pytest.mark.parametrize('key,value,reason',[
    ('source_url','https://thuvienso.ut.edu.vn.evil.test/items/'+ID,'source_identity'),
    ('source_url','https://thuvienso.ut.edu.vn/items/'+OTHER,'source_identity'),
    ('sha256','0'*64,'integrity'),
    ('fetched_at','2026-01-01','timestamp'),
])
def test_wrapper_identity_integrity_and_timestamp_are_validated(key,value,reason):
    source=snapshot(); source[key]=value
    with pytest.raises(ValueError,match=reason):
        dspace_catalog.normalize_snapshot(source)


def test_unknown_or_multiple_issue_years_are_not_invented():
    source=snapshot(metadata={'dc.date.issued':[{'value':'2006/2007'}]})
    assert dspace_catalog.normalize_snapshot(source).year==''
    source=snapshot(metadata={'dc.date.issued':[{'value':'2006-01-12'}]})
    assert dspace_catalog.normalize_snapshot(source).year=='2006'
    source=snapshot(metadata={'dc.date.issued':[{'value':'2006'},{'value':'2007'}]})
    assert dspace_catalog.normalize_snapshot(source).year==''


def test_stage_reconciles_every_file_and_does_not_accept_misnamed_identity(tmp_path):
    (tmp_path/(ID+'.json')).write_text(json.dumps(snapshot()),encoding='utf-8')
    (tmp_path/'bad.json').write_text('{bad json',encoding='utf-8')
    (tmp_path/(OTHER+'.json')).write_text(json.dumps(snapshot()),encoding='utf-8')
    rows,report=dspace_catalog.stage_snapshots(tmp_path,published=True)
    assert len(rows)==1 and report['discovered']==3 and report['accepted']==1
    assert {r['reason'] for r in report['rejected']}=={'invalid_json','filename_identity'}
    assert report['accepted']+len(report['rejected'])==report['discovered']


def test_import_is_idempotent_and_preserves_operator_edits(tmp_path):
    store=Store(tmp_path/'library.sqlite3')
    row=dspace_catalog.normalize_snapshot(snapshot(),published=True)
    assert dspace_catalog.import_books(store.connect,[row])=={'imported':1,'skipped_existing':0}
    with store.connect() as db:
        db.execute("UPDATE books SET title='Operator edit',published=0")
    assert dspace_catalog.import_books(store.connect,[row])=={'imported':0,'skipped_existing':1}
    with store.connect() as db:
        result=db.execute('SELECT title,published FROM books').fetchall()
    assert len(result)==1 and result[0]['title']=='Operator edit' and result[0]['published']==0


def test_import_rolls_back_all_rows_when_a_write_fails(tmp_path,monkeypatch):
    store=Store(tmp_path/'library.sqlite3')
    rows=[dspace_catalog.normalize_snapshot(snapshot(identifier),published=True) for identifier in (ID,OTHER)]
    save=dspace_catalog.save_book
    def fail_second(db,body):
        if body.source_url.endswith(OTHER):
            raise RuntimeError('Synthetic storage failure')
        return save(db,body)
    monkeypatch.setattr(dspace_catalog,'save_book',fail_second)
    with pytest.raises(RuntimeError,match='Synthetic'):
        dspace_catalog.import_books(store.connect,rows)
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM books').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM audit').fetchone()[0]==0


def test_cli_dry_run_does_not_create_database(tmp_path,monkeypatch,capsys):
    directory=tmp_path/'records'; directory.mkdir()
    (directory/(ID+'.json')).write_text(json.dumps(snapshot()),encoding='utf-8')
    runtime=tmp_path/'unused-runtime'
    monkeypatch.setenv('DATA_DIR',str(runtime))
    monkeypatch.setattr(sys,'argv',['import_dspace.py',str(directory),'--publish'])
    script=run_path(str(Path(__file__).resolve().parents[1]/'scripts/import_dspace.py'))
    assert script['main']()==0
    report=json.loads(capsys.readouterr().out)
    assert report['accepted']==1 and report['applied'] is False
    assert not runtime.exists()
