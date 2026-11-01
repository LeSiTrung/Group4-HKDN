import json
from pathlib import Path
from runpy import run_path

import httpx
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/collect_lic.py'
BASE = 'https://lic.ut.edu.vn'


def test_inventory_uses_page_locations_not_image_locations():
    module = run_path(str(SCRIPT))
    raw = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"><url><loc>https://lic.ut.edu.vn/</loc><image:image><image:loc>https://lic.ut.edu.vn/photo.jpg</image:loc></image:image></url></urlset>'
    assert module['sitemap_locations'](raw) == ('urlset', [BASE + '/'])
    with pytest.raises(ValueError):
        module['sitemap_locations'](b'<other/>')


def test_scope_rejects_external_credentials_queries_and_media():
    scope = run_path(str(SCRIPT))['url_scope']
    assert scope(BASE + '/noi-quy-thu-vien/#top') == (BASE + '/noi-quy-thu-vien/', None)
    for url, reason in [(BASE + '/picture.pdf', 'media'), (BASE + '/?s=book', 'query'),
                        (BASE + '/nhan-su/', 'personnel'), (BASE + '/blocks/demo/', 'template'),
                        (BASE + '/amunra-casino-avis/', 'spam'), ('https://evil.example/', 'unsafe_host'),
                        ('https://user:password@lic.ut.edu.vn/', 'unsafe_host')]:
        assert scope(url)[1] == reason


def test_unrelated_page_is_not_library_content_because_of_site_title():
    parse = run_path(str(SCRIPT))['parse_page']
    page = parse('<title>Admission news - Trung tâm Thông tin - Thư viện</title><main>University admission opening dates and undergraduate registration instructions.</main>', BASE + '/admission/')
    assert page['status'] == 'quarantine_unrelated'


def test_source_denial_is_checkpointed_without_retry_or_followup(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        return httpx.Response(403)
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path)
    assert not result['complete'] and result['blocked'] == 'source_denied_403'
    assert calls == ['/robots.txt', '/sitemap_index.xml']


def test_redirect_hops_are_paced_and_busy_source_has_bounded_retries(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    clock = [0.0]
    monkeypatch.setattr(module['time'], 'monotonic', lambda: clock[0])
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    starts, calls = [], []
    def handler(request):
        starts.append(clock[0])
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        if request.url.path == '/sitemap_index.xml':
            return httpx.Response(302, headers={'location': BASE + '/actual-sitemap.xml'})
        return httpx.Response(503, headers={'retry-after': '2'})
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path)
    assert result['blocked'] == 'source_busy_503' and not result['complete']
    assert calls.count('/sitemap_index.xml') == 3 and calls.count('/actual-sitemap.xml') == 3
    assert all(b - a >= 1 for a, b in zip(starts, starts[1:]))


def test_collection_resume_corrupt_snapshot_and_denial(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    clock = [0.0]
    monkeypatch.setattr(module['time'], 'monotonic', lambda: clock[0])
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    calls, starts = [], []
    deny = []
    def handler(request):
        path = request.url.path
        calls.append(path)
        starts.append(clock[0])
        if path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /\n' if deny else 'User-agent: *\nDisallow:\nCrawl-delay: 2\nSitemap: ' + BASE + '/sitemap_index.xml')
        if path == '/sitemap_index.xml':
            return httpx.Response(200, text='<urlset><url><loc>' + BASE + '/</loc></url><url><loc>' + BASE + '/noi-quy-thu-vien/</loc></url><url><loc>' + BASE + '/nhan-su/</loc></url></urlset>')
        content = '<title>Thư viện</title><main><p>Nội quy thư viện và dịch vụ thư viện công khai.</p><a href="/missing/">missing</a><a href="/document.pdf">file</a></main>'
        if path == '/missing/':
            return httpx.Response(404)
        return httpx.Response(200, text=content, headers={'content-type': 'text/html; charset=utf-8'})
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path)
    assert result['complete'] and result['counts']['accepted'] == 1 and result['counts']['duplicate'] == 1
    assert result['counts']['missing_404'] == 1 and result['counts']['skipped_personnel'] == 1
    assert all(b - a >= 2 for a, b in zip(starts[1:], starts[2:]))
    calls.clear()
    result = module['collect'](tmp_path)
    assert result['complete'] and result['reused'] == 3 and '/' not in calls
    record = next((tmp_path / 'pages').glob('*.json'))
    record.write_text('{broken', encoding='utf-8')
    calls.clear()
    result = module['collect'](tmp_path)
    assert result['complete'] and result['reused'] == 2
    cached = json.loads(record.read_text(encoding='utf-8'))
    del cached['fetched_at']
    record.write_text(json.dumps(cached), encoding='utf-8')
    result = module['collect'](tmp_path)
    assert result['complete'] and result['reused'] == 2
    cached = json.loads(record.read_text(encoding='utf-8'))
    cached['page']['links'] = None
    cached['sha256'] = module['digest'](cached['page'])
    record.write_text(json.dumps(cached), encoding='utf-8')
    result = module['collect'](tmp_path)
    assert result['complete'] and result['reused'] == 2
    cached = json.loads(record.read_text(encoding='utf-8'))
    cached['page']['status'] = 'accepted' if cached['page']['status'] != 'accepted' else 'quarantine_empty'
    record.write_text(json.dumps(cached), encoding='utf-8')
    result = module['collect'](tmp_path)
    assert result['complete'] and result['reused'] == 2
    deny.append(True)
    calls.clear()
    result = module['collect'](tmp_path)
    assert not result['complete'] and result['blocked'] == 'robots_denied' and calls == ['/robots.txt']


def test_explicit_page_budget_never_reports_full_coverage(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        if request.url.path == '/sitemap_index.xml':
            return httpx.Response(200, text='<urlset><url><loc>' + BASE + '/</loc></url><url><loc>' + BASE + '/next/</loc></url></urlset>')
        return httpx.Response(404)
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path, max_pages=1)
    assert not result['complete'] and result['blocked'] == 'page_budget_exhausted' and result['pending'] == 1
    result = module['collect'](tmp_path, max_pages=1)
    assert result['complete'] and result['reused'] == 1 and result['counts']['missing_404'] == 2


def test_query_exclusion_does_not_shadow_clean_page_link(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    calls = []
    def handler(request):
        calls.append(request.url.path)
        assert not request.url.query
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        if request.url.path == '/sitemap_index.xml':
            return httpx.Response(200, text='<urlset><url><loc>' + BASE + '/</loc></url></urlset>')
        if request.url.path == '/':
            return httpx.Response(200, text='<main>Thư viện hỗ trợ bạn đọc tìm kiếm tài liệu.<a href="/next/?s=secret">query</a><a href="/next/">page</a></main>', headers={'content-type': 'text/html'})
        return httpx.Response(404)
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path)
    assert result['complete'] and '/next/' in calls and result['counts']['skipped_query'] == 1
    assert 'secret' not in json.dumps(result)


@pytest.mark.parametrize(('target', 'reason'), [('/nhan-su/member/', 'personnel'), ('/casino-offer/', 'spam'), ('/file.pdf', 'media')])
def test_redirect_cannot_fetch_excluded_page_class(tmp_path, monkeypatch, target, reason):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        if request.url.path == '/sitemap_index.xml':
            return httpx.Response(200, text='<urlset><url><loc>' + BASE + '/article/</loc></url></urlset>')
        if request.url.path in ('/', '/article/'):
            return httpx.Response(302, headers={'location': BASE + target})
        return httpx.Response(200, text='<main>Library information for readers and public books.</main>', headers={'content-type': 'text/html'})
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path)
    assert target not in calls and result['counts']['skipped_redirect_' + reason] == 2


def test_malformed_sitemap_and_source_denial_checkpoint(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        return httpx.Response(200, text='<broken')
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path)
    assert not result['complete'] and result['blocked'] == 'malformed_sitemap'
    assert json.loads((tmp_path / 'manifest.json').read_text())['complete'] is False
