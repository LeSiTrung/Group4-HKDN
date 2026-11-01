import json
from pathlib import Path
from runpy import run_path

import httpx
import pytest


SCRIPT=Path(__file__).resolve().parents[1]/'scripts/collect_dspace.py'
UID='0009688f-12f3-4902-9b95-7a31e878ee77'


def test_only_canonical_same_host_item_urls_are_accepted():
    module=run_path(str(SCRIPT))
    parse=module['item_id']
    assert parse('https://thuvienso.ut.edu.vn/items/'+UID)==UID
    for url in ['https://evil.example/items/'+UID,'http://thuvienso.ut.edu.vn/items/'+UID,
        'https://thuvienso.ut.edu.vn/items/../admin','https://thuvienso.ut.edu.vn/items/'+UID+'?admin=1']:
        with pytest.raises(ValueError):
            parse(url)


def test_snapshot_resume_rejects_changed_record_or_identity(tmp_path):
    module=run_path(str(SCRIPT))
    record={'uuid':UID,'type':'item','name':'Public title','metadata':{}}
    snapshot=module['snapshot'](UID,record)
    path=tmp_path/(UID+'.json')
    path.write_text(json.dumps(snapshot),encoding='utf-8')
    assert module['cached'](path,UID)
    snapshot['record']['name']='Modified'
    path.write_text(json.dumps(snapshot),encoding='utf-8')
    assert not module['cached'](path,UID)


def test_retry_after_is_bounded_and_understands_http_date():
    retry=run_path(str(SCRIPT))['retry_seconds']
    assert retry('12')==12
    assert retry('bogus')==2
    assert retry('Sat, 01 Jan 2000 00:00:00 GMT')==0
    with pytest.raises(ValueError):
        retry('600')


@pytest.mark.parametrize('crawl_delay',[0,2])
def test_collection_resumes_without_refetching_item_and_honors_robots(tmp_path,monkeypatch,crawl_delay):
    module=run_path(str(SCRIPT))
    service=module['network']
    monkeypatch.setattr(service,'_public_ip',lambda host:'93.184.216.34')
    clock=[0.0]
    monkeypatch.setattr(module['time'],'monotonic',lambda:clock[0])
    monkeypatch.setattr(module['time'],'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    calls=[]
    starts=[]
    denied=[]
    def handler(request):
        path=request.url.path
        calls.append(path)
        starts.append(clock[0])
        if path=='/robots.txt':
            return httpx.Response(200,text='User-agent: *\nDisallow: /server/api\n' if denied else f'User-agent: *\nDisallow:\nCrawl-delay: {crawl_delay}\n')
        if path=='/sitemap_index.xml':
            return httpx.Response(200,text='<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://thuvienso.ut.edu.vn/sitemap0.xml</loc></sitemap></sitemapindex>')
        if path=='/sitemap0.xml':
            return httpx.Response(200,text=f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://thuvienso.ut.edu.vn/items/{UID}</loc></url></urlset>')
        assert path=='/server/api/core/items/'+UID
        return httpx.Response(200,json={'uuid':UID,'type':'item','name':'A public title','metadata':{}})
    monkeypatch.setattr(service,'_client',lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    result=module['collect'](tmp_path)
    assert result['complete'] and result['collected']==1 and result['failed']==0
    assert all(later-earlier>=max(0.25,crawl_delay) for earlier,later in zip(starts,starts[1:]))
    calls.clear()
    result=module['collect'](tmp_path)
    assert result['complete'] and result['reused']==1 and '/server/api/core/items/'+UID not in calls
    denied.append(True)
    result=module['collect'](tmp_path/'denied')
    assert not result['complete'] and '/server/api/core/items/'+UID not in calls


def test_snapshot_rejects_record_from_another_uuid():
    create=run_path(str(SCRIPT))['snapshot']
    with pytest.raises(ValueError):
        create(UID,{'uuid':'11111111-1111-4111-8111-111111111111','type':'item','metadata':{}})


def test_private_item_is_skipped_without_retry_and_other_public_items_continue(tmp_path,monkeypatch):
    module=run_path(str(SCRIPT))
    service=module['network']
    other='11111111-1111-4111-8111-111111111111'
    calls=[]
    monkeypatch.setattr(service,'_public_ip',lambda host:'93.184.216.34')
    monkeypatch.setattr(module['time'],'sleep',lambda seconds:None)
    def handler(request):
        calls.append(request.url.path)
        if request.url.path=='/robots.txt':
            return httpx.Response(200,text='User-agent: *\nDisallow:\n')
        if request.url.path=='/sitemap_index.xml':
            return httpx.Response(200,text='<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://thuvienso.ut.edu.vn/sitemap0.xml</loc></sitemap></sitemapindex>')
        if request.url.path=='/sitemap0.xml':
            return httpx.Response(200,text='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>https://thuvienso.ut.edu.vn/items/{uid}</loc></url>' for uid in [UID,other])+'</urlset>')
        if request.url.path.endswith(UID):
            return httpx.Response(401)
        return httpx.Response(200,json={'uuid':other,'type':'item','name':'Public title','metadata':{}})
    monkeypatch.setattr(service,'_client',lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    result=module['collect'](tmp_path)
    assert result['complete'] and result['collected']==1 and result['restricted']==1 and result['failed']==0
    assert calls.count('/server/api/core/items/'+UID)==1
    module['collect'](tmp_path)
    assert calls.count('/server/api/core/items/'+UID)==1
