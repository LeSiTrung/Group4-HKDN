import json
from pathlib import Path
from runpy import run_path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/collect_opac.py'


@pytest.fixture(autouse=True)
def paced_mock_requests(monkeypatch):
    from app.services import integrations
    next_request=[0.0]
    def pace(minimum_gap=10,**kwargs):
        now=integrations.time.monotonic()
        integrations.time.sleep(max(0,next_request[0]-now))
        next_request[0]=integrations.time.monotonic()+minimum_gap
    monkeypatch.setattr(integrations,'wait_for_turn',pace)


@pytest.mark.parametrize('permanent', [False, True])
def test_checkpoint_retries_windows_sharing_lock_without_losing_old_file(tmp_path, monkeypatch, permanent):
    module = run_path(str(SCRIPT))
    target = tmp_path / 'manifest.json'
    target.write_text('{"old": true}')
    replace = Path.replace
    attempts = []
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    def locked(path, destination):
        attempts.append(1)
        if permanent or len(attempts) < 3:
            raise PermissionError('simulated Windows sharing lock')
        return replace(path, destination)
    monkeypatch.setattr(Path, 'replace', locked)
    if permanent:
        with pytest.raises(PermissionError):
            module['write_json'](target, {'new': True})
        assert json.loads(target.read_text()) == {'old': True}
        assert len(attempts) == 8
    else:
        module['write_json'](target, {'new': True})
        assert json.loads(target.read_text()) == {'new': True}
        assert len(attempts) == 3


def test_additional_public_categories_keep_source_dictionary_ids():
    module = run_path(str(SCRIPT))
    assert module['category_url']('36') == module['BASE'] + 'OShow.aspx?DicID=10&BrowseId=36'
    assert module['category_url']('11-7') == module['BASE'] + 'OShow.aspx?DicID=11&BrowseId=7'
    assert {'36', '11-7'}.issubset(module['CATEGORIES'])


def listing(page=1, total=2, identifier='5712'):
    return f'''<form><input type="hidden" name="__VIEWSTATE" value="opaque">
    <input type="hidden" id="hidCurrentPage" name="hidCurrentPage" value="{page}">
    <div class="divPage">Mục {page} đến {page} của {total}</div>
    <div class="item-box"><h2><a onclick="parent.showPopupDetail({identifier})">{page}. Sách Python</a></h2>
    <div class="item-intro"><p><b>Tác giả:</b> Nguyễn Văn A</p><p><b>Từ khóa:</b> Python; Tin học</p></div></div></form>'''


@pytest.mark.parametrize(('number', 'label'), [(1000, '1.000'), (10000, '10.000'), (12345, '12.345')])
def test_listing_accepts_source_thousands_separators_in_ordinals(number, label):
    parse = run_path(str(SCRIPT))['parse_listing']
    raw = listing(number, total=number).replace(f'>{number}. ', f'>{label}. ')
    row, _ = parse(raw, number)
    assert row['first'] == number and row['records'][0]['title'] == 'Sách Python'
    with pytest.raises(ValueError, match='identity'):
        parse(raw.replace(f'>{label}. ', '>10.00. '), number)


def test_listing_requires_exact_page_ordinals_and_retains_metadata():
    module = run_path(str(SCRIPT))
    row, form = module['parse_listing'](listing(), 1)
    assert row['total'] == 2 and row['first'] == 1 and row['last'] == 1
    assert row['records'][0]['title'] == 'Sách Python'
    assert row['records'][0]['fields']['Tác giả'] == ['Nguyễn Văn A']
    assert form['__VIEWSTATE'] == 'opaque'
    with pytest.raises(ValueError, match='page'):
        module['parse_listing'](listing(), 2)
    with pytest.raises(ValueError):
        module['parse_listing']('<html>Cloudflare challenge</html>', 1)


def test_detail_keeps_repeated_marc_fields_and_excludes_internal_9xx():
    parse = run_path(str(SCRIPT))['parse_detail']
    raw = '''<input id="hidItemID" value="5712"><div class="TabbedPanelsContent"><div class="popup-modul"><h3>Thông tin biên mục:</h3>
    <div class="ClearFix">Ldr\t \t00025nam<br>001\t \tGTVT123<br>245\t__\t$aPython /$cNguyễn Văn A<br>
    653\t__\t$aTin học<br>653\t__\t$aPython<br>852\t \t$aGTVT$bKS1V$jABC<br>911\t \tNgười biên mục</div></div></div>'''
    row = parse(raw, '5712')
    assert [x['tag'] for x in row['marc']] == ['Ldr', '001', '245', '653', '653', '852']
    assert 'Người biên mục' not in json.dumps(row, ensure_ascii=False)
    with pytest.raises(ValueError):
        parse('<html>Please log in</html>', '5712')
    with pytest.raises(ValueError, match='identity'):
        parse(raw, '9999')


def test_collector_resumes_pages_reconciles_ids_and_stops_denial(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    clock = [0.0]
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(module['time'], 'monotonic', lambda: clock[0])
    calls, starts = [], []
    denied = []
    def handler(request):
        calls.append((request.method, request.url.path))
        starts.append(clock[0])
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /\nCrawl-delay: 10')
        if denied and request.method == 'POST':
            return httpx.Response(403)
        page = 2 if request.method == 'POST' else 1
        if page == 2:
            assert b'hidCurrentPage=2' in request.content
        return httpx.Response(200, text=listing(page, identifier=str(5711 + page)), headers={'content-type': 'text/html'})
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path, categories=['1'], max_pages=1, details=False, acknowledge_robots=True)
    assert not result['complete'] and result['listing_records'] == 1
    assert result['robots_disallow_acknowledged'] and result['blocked'] == 'page_budget_exhausted'
    assert all(b-a >= 10 for a, b in zip(starts, starts[1:]))
    starts.clear()
    result = module['collect'](tmp_path, categories=['1'], details=False, acknowledge_robots=True)
    assert result['complete'] and result['listing_records'] == 2
    assert result['categories']['1']['unique_records'] == 2
    assert all(b-a >= 10 for a, b in zip(starts, starts[1:]))
    calls.clear()
    result = module['collect'](tmp_path, categories=['1'], details=False, acknowledge_robots=True)
    assert result['complete'] and not any(method == 'POST' for method, _ in calls)
    (tmp_path/'pages/1-00002.json').write_text('{}')
    denied.append(True)
    result = module['collect'](tmp_path, categories=['1'], details=False, acknowledge_robots=True)
    assert not result['complete'] and result['blocked'] == 'source_http_403'
    assert sum(method == 'POST' for method, _ in calls) == 1


def test_robots_requires_explicit_acknowledgement(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    def handler(request):
        assert request.url.path == '/robots.txt'
        return httpx.Response(200, text='User-agent: *\nDisallow: /')
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    report = module['collect'](tmp_path)
    assert report['blocked'] == 'robots_disallowed_requires_explicit_operator_acknowledgement'
    assert not report['complete']


def test_cached_listing_schema_cannot_fake_completeness(tmp_path):
    module = run_path(str(SCRIPT))
    url = module['BASE'] + 'OShow.aspx?DicID=10&BrowseId=1'
    invalid = {'page': 1, 'first': 1, 'last': 2, 'total': 2, 'records': []}
    path = tmp_path/'page.json'
    module['write_json'](path, {'source_url': url, 'fetched_at': '2026-11-01T12:00:00+00:00',
                              'record': invalid, 'sha256': module['digest'](invalid)})
    assert module['read_snapshot'](path, url, 1) is None


@pytest.mark.parametrize('status', [401, 403, 429, 522])
def test_busy_or_denied_source_is_not_retried(tmp_path, monkeypatch, status):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        return httpx.Response(status)
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    report = module['collect'](tmp_path, categories=['1'])
    assert report['blocked'] == 'source_http_' + str(status) and not report['complete']
    assert calls == ['/robots.txt', '/opac/OShow.aspx']


def test_selective_robots_rule_is_checked_on_listing(tmp_path, monkeypatch):
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    def handler(request):
        assert request.url.path == '/robots.txt'
        return httpx.Response(200, text='User-agent: *\nDisallow: /opac/OShow.aspx')
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path, categories=['1'])
    assert result['blocked'] == 'robots_disallowed_requires_explicit_operator_acknowledgement'


@pytest.mark.parametrize('recovers', [True, False])
def test_empty_success_page_gets_one_checked_session_refresh(tmp_path, monkeypatch, recovers):
    from urllib.parse import parse_qs
    module = run_path(str(SCRIPT))
    network = module['network']
    monkeypatch.setattr(network, '_public_ip', lambda host: '93.184.216.34')
    monkeypatch.setattr(module['time'], 'sleep', lambda seconds: None)
    posts = []
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow:')
        page = int(parse_qs(request.content.decode())['hidCurrentPage'][0]) if request.method == 'POST' else 1
        if request.method == 'POST':
            posts.append(page)
        raw = listing(page, total=3, identifier=str(5711 + page))
        if page == 3 and (posts.count(3) == 1 or not recovers):
            raw = '<input id="hidCurrentPage" value="3"><p>Không tìm thấy biểu ghi nào.</p>'
        return httpx.Response(200, text=raw, headers={'content-type': 'text/html'})
    monkeypatch.setattr(network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    result = module['collect'](tmp_path, categories=['1'], details=False)
    assert result['complete'] is recovers
    assert result['listing_records'] == (3 if recovers else 2)
    assert result['blocked'] == (None if recovers else 'listing_summary_missing')
    assert result['session_refreshes'] == 1 and posts == [2, 3, 3]
