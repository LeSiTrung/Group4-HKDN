import hashlib
import json
import sys
from pathlib import Path
from runpy import run_path

import httpx
import pytest


SCRIPT=Path(__file__).resolve().parents[1]/'scripts/collect_opac.py'
BASE='https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId='


def pack(directory,rows):
    path=directory/'catalog-listings.jsonl'
    raw=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows).encode()
    path.write_bytes(raw)
    path.with_name('catalog-listings-manifest.json').write_text(json.dumps({
        'records':len(rows),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}))
    return path


def listing(identifier,**changes):
    return {'id':identifier,'title':'Sách Python','fields':{},'categories':['1'],
            'fetched_at':'2026-11-01T18:00:00+00:00','source_url':BASE+identifier,**changes}


def detail(identifier):
    return f'<input id="hidItemID" value="{identifier}"><div class="popup-modul"><div class="ClearFix">Ldr 00025nam<br>245 __ $aPython</div></div>'


@pytest.fixture
def source(monkeypatch):
    module=run_path(str(SCRIPT))
    calls,gaps=[],[]
    response={'robots':'User-agent: *\nDisallow:\nCrawl-delay: 20','status':200}
    monkeypatch.setattr(module['network'],'_public_ip',lambda host:'93.184.216.34')
    monkeypatch.setattr(module['network'],'wait_for_turn',lambda **kwargs:gaps.append(kwargs))
    def handle(request):
        calls.append(str(request.url))
        if request.url.path=='/robots.txt':
            return httpx.Response(200,text=response['robots'])
        assert request.method=='GET' and request.url.path=='/opac/ODetail.aspx'
        return httpx.Response(response['status'],text=detail(request.url.params['intItemId']),headers={'content-type':'text/html'})
    monkeypatch.setattr(module['network'],'_client',lambda:httpx.Client(transport=httpx.MockTransport(handle)))
    return module,calls,gaps,response


def test_frozen_inventory_skips_listings_reuses_marc_and_preserves_pack(tmp_path,source):
    module,calls,gaps,_=source
    path=pack(tmp_path,[listing('5712'),listing('5713')])
    original=path.read_bytes()
    pages=tmp_path/'pages'; pages.mkdir()
    old_page=pages/'1-00001.json'; old_page.write_bytes(b'preserved listing snapshot')
    records=tmp_path/'records'; records.mkdir()
    record=module['parse_detail'](detail('5712'),'5712')
    cached=records/'5712.json'
    module['write_json'](cached,{'source_url':BASE+'5712','fetched_at':'2026-11-01T18:00:00+00:00',
        'record':record,'sha256':module['digest'](record)})
    cached_bytes=cached.read_bytes()
    result=module['collect'](tmp_path,details_from_pack=path)
    assert result['complete'] and result['phase']=='complete' and not result['blocked']
    assert result['listing_records']==result['detail_records']==2
    assert result['categories']=={} and 'frozen inventory' in result['scope']
    assert result['frozen_inventory']['pack_sha256']==hashlib.sha256(original).hexdigest()
    assert result['frozen_inventory']['records']==2
    assert [call.split('/')[-1] for call in calls]==['robots.txt','ODetail.aspx?intItemId=5713']
    assert [gap['minimum_gap'] for gap in gaps]==[10,20]
    assert all(gap['max_wait'] is None for gap in gaps)
    assert cached.read_bytes()==cached_bytes and path.read_bytes()==original
    assert old_page.read_bytes()==b'preserved listing snapshot'
    calls.clear()
    assert module['collect'](tmp_path,details_from_pack=path)['detail_records']==2
    assert len(calls)==1 and calls[0].endswith('/robots.txt')


@pytest.mark.parametrize('corruption',['hash','late_foreign_row'])
def test_invalid_pack_is_rejected_before_any_http(tmp_path,source,corruption):
    module,calls,_,_=source
    rows=[listing('5712'),listing('5713')]
    if corruption=='late_foreign_row':
        rows[-1]['source_url']='https://evil.example/book'
    path=pack(tmp_path,rows)
    if corruption=='hash':
        path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):
        module['collect'](tmp_path,details_from_pack=path)
    assert not calls


def test_field_limit_quarantined_ids_are_included_without_truncation(tmp_path,source):
    module,calls,_,_=source
    path=pack(tmp_path,[listing('5712'),listing('5713',fields={'Từ khóa':['x'*1001]})])
    original=path.read_bytes()
    result=module['collect'](tmp_path,details_from_pack=path)
    assert result['complete'] and result['detail_records']==result['listing_records']==2
    assert {call.rsplit('=',1)[-1] for call in calls[1:]}=={'5712','5713'}
    assert path.read_bytes()==original


@pytest.mark.parametrize('acknowledge',[False,True])
def test_frozen_inventory_still_requires_robots_acknowledgement(tmp_path,source,acknowledge):
    module,calls,_,response=source
    response['robots']='User-agent: *\nDisallow: /'
    path=pack(tmp_path,[listing('5712')])
    result=module['collect'](tmp_path,details_from_pack=path,acknowledge_robots=acknowledge)
    assert result['complete'] is acknowledge
    assert len(calls)==(2 if acknowledge else 1)
    assert result['robots_disallow_acknowledged'] is acknowledge


@pytest.mark.parametrize('status',[401,403,429])
def test_frozen_inventory_stops_http_denial_without_retry(tmp_path,source,status):
    module,calls,_,response=source
    response['status']=status
    path=pack(tmp_path,[listing('5712')])
    result=module['collect'](tmp_path,details_from_pack=path)
    assert not result['complete'] and result['blocked']=='source_http_'+str(status)
    assert result['detail_records']==0 and len(calls)==2


def test_cli_passes_frozen_inventory_option_and_scopes_manifest(tmp_path,source,monkeypatch):
    _,calls,_,_=source
    path=pack(tmp_path,[listing('5712')])
    monkeypatch.setattr(sys,'argv',[str(SCRIPT),'--output',str(tmp_path),'--details-from-pack',str(path)])
    with pytest.raises(SystemExit) as result:
        run_path(str(SCRIPT),run_name='__main__')
    assert result.value.code==0
    manifest=json.loads((tmp_path/'manifest.json').read_text())
    assert manifest['frozen_inventory']['records']==1 and manifest['complete']
    assert len(calls)==2 and 'OShow' not in ''.join(calls)


def test_network_failure_keeps_safe_operator_reason_and_checkpoint(tmp_path,source,monkeypatch):
    module,_,_,_=source
    path=pack(tmp_path,[listing('5712')])
    monkeypatch.setattr(module['time'],'sleep',lambda _:None)
    def timeout(request):
        raise httpx.ReadTimeout('private transport diagnostics must not be copied')
    monkeypatch.setattr(module['network'],'_client',lambda:httpx.Client(transport=httpx.MockTransport(timeout)))
    result=module['collect'](tmp_path,details_from_pack=path)
    assert result['blocked']=='safe_network_error' and not result['complete']
    assert result['failure']['status_code']==502
    assert result['failure']['url']=='https://opacthuvien.ut.edu.vn/robots.txt'
    assert 'private transport' not in json.dumps(result)
