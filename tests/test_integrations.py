import hashlib
import hmac
import json
import socket
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services import integrations as service
from app.api import channels


@pytest.fixture
def network(monkeypatch):
    monkeypatch.setenv('CRAWL_ALLOWED_HOSTS', 'library.example')
    monkeypatch.setattr(service.socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))])
    monkeypatch.setattr(service.time, 'sleep', lambda _: None)
    def install(handler):
        monkeypatch.setattr(service, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False))
    return install


@pytest.mark.parametrize('url', ['http://library.example/', 'https://evil.example/', 'https://library.example:8443/', 'https://user:pass@library.example/', 'https://127.0.0.1/', 'https://library.example/\\evil'])
def test_crawl_rejects_untrusted_urls(network, url):
    network(lambda _: pytest.fail('unsafe request escaped validation'))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages(url)


def test_crawl_rejects_private_dns(network, monkeypatch):
    monkeypatch.setattr(service.socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('127.0.0.1', 443))])
    network(lambda _: pytest.fail('private request escaped validation'))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages('https://library.example/')


def test_crawl_rejects_multicast_dns(network, monkeypatch):
    monkeypatch.setattr(service.socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('224.0.0.1', 443))])
    network(lambda _: pytest.fail('multicast request escaped validation'))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages('https://library.example/')


@pytest.mark.parametrize('address', ['fec0::1', '2002:7f00:1::1'])
def test_crawl_rejects_ipv6_local_and_transition_dns(network, monkeypatch, address):
    monkeypatch.setattr(service.socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET6, 1, 6, '', (address, 443, 0, 0))])
    network(lambda _: pytest.fail('IPv6 local/transition request escaped validation'))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages('https://library.example/')


def test_crawl_robots_and_redirects(network):
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /private\n')
        if request.url.path == '/':
            return httpx.Response(302, headers={'location': '/private'})
        pytest.fail('robots-disallowed redirected request sent')
    network(handler)
    with pytest.raises(service.IntegrationError, match='robots'):
        service.crawl_pages('https://library.example/')


def test_crawl_bounds_extracts_and_pins_dns(network):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        assert request.url.host == '93.184.216.34'
        assert request.headers['host'] == 'library.example'
        assert request.extensions['sni_hostname'] == 'library.example'
        if request.url.path == '/robots.txt':
            return httpx.Response(404)
        return httpx.Response(200, headers={'content-type': 'text/html'}, text='<title>Library</title><script>secret</script><main>Hello <a href="/next">Next</a><a href="https://evil.example">Other</a></main>')
    network(handler)
    pages = service.crawl_pages('https://library.example/', 1)
    assert len(pages) == 1 and pages[0]['url'] == 'https://library.example/'
    assert 'Hello' in pages[0]['text'] and 'secret' not in pages[0]['text']
    assert calls == ['/robots.txt', '/']


def test_crawl_external_redirect_and_oversize_rejected(network):
    network(lambda r: httpx.Response(404) if r.url.path == '/robots.txt' else httpx.Response(302, headers={'location': 'https://evil.example/'}))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages('https://library.example/')
    network(lambda r: httpx.Response(404) if r.url.path == '/robots.txt' else httpx.Response(200, headers={'content-type': 'text/html'}, content=b'x' * 1_048_577))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages('https://library.example/')


def test_catalog_parses_observed_opac_markup(network):
    network(lambda r: httpx.Response(200, headers={'content-type': 'text/html'}, text='<div><h2 onclick="parent.showPopupDetail(1967);">10 năm Olympic cơ học</h2><p>Tác giả: Nguyễn A</p><p>Năm xuất bản: 1999</p></div>'))
    result = service.search_catalog('tàu', 'books')
    assert 'rdSearchOption=1' in result['search_url']
    assert result['items'][0]['title'] == '10 năm Olympic cơ học'
    assert result['items'][0]['url'].endswith('ODetail.aspx?intItemId=1967')
    assert result['items'][0]['year'] == '1999'


def test_catalog_digital_uses_browser_verified_option(network):
    network(lambda r: httpx.Response(200, text='<h2 onclick="parent.showPopupDetail(1967)">Digital title</h2>'))
    result = service.search_catalog('tàu', 'digital')
    assert 'rdSearchOption=-4' in result['search_url']
    assert result['items'][0]['title'] == 'Digital title'


def test_catalog_parses_live_anchor_cards_without_mixing_metadata(network):
    html = '''<ul class="ClearFix">
    <li><div class="item-box box-raised"><h2 class="clr-cyan"><a onclick="parent.showPopupDetail(1967)" style="cursor:pointer;">1. <span class="hightlight-text"></span> 10 năm Olympic cơ học toàn quốc 1989 - 1998</a></h2>
    <div class="item-info ClearFix"><div class="item-intro col-right-7">
    <p><span><b>Tác giả:&nbsp;</b>GS. TS. Đào Huy Bích (Chủ biên)</span></p>
    <p><span><b>Chỉ số Phân loại thập phân Dewey:&nbsp;</b>533 M558N/01</span></p>
    <p><span><b>Thông tin xuất bản:&nbsp;</b>Hà Nội , 1998</span></p>
    <p><span><b>Dạng tài liệu:&nbsp;</b>Sách truyền thống</span></p></div></div>
    <h3><a onclick="parent.checkMyList(1967)">Lưu danh sách</a></h3></div></li>
    <li><div class="item-box box-raised"><h2><a onclick="parent.showPopupDetail(6310)">2. 10th International conference</a></h2>
    <div class="item-intro"><p><b>Thông tin xuất bản:</b>America : Woodhead Publishing , 2012</p></div></div></li>
    <li><div class="item-box box-raised"><h2><a onclick="parent.showPopupDetail(9222)">3. 2007 ABS Annual review</a></h2>
    <div class="item-intro"><p><b>Tác giả:</b>ABS &amp; Affiliated Companies</p><p><b>Thông tin xuất bản:</b>Houston : ABS</p></div></div></li>
    </ul>'''
    network(lambda r: httpx.Response(200, text=html))
    items = service.search_catalog('tàu')['items']
    assert len(items) == 3
    assert items[0]['title'] == '10 năm Olympic cơ học toàn quốc 1989 - 1998'
    assert items[0]['author'] == 'GS. TS. Đào Huy Bích (Chủ biên)'
    assert items[0]['year'] == '1998'
    assert items[1]['author'] == '' and items[1]['year'] == '2012'
    assert items[2]['author'] == 'ABS & Affiliated Companies' and items[2]['year'] == ''


@pytest.mark.parametrize('response', [httpx.Response(403), httpx.Response(200, text='<h1>Challenge</h1>'), httpx.Response(200, text='<h2 onclick="parent.showPopupDetail(1)"></h2>')])
def test_catalog_never_disguises_upstream_failure_as_empty_success(network, response):
    network(lambda r: response)
    with pytest.raises(service.IntegrationError):
        service.search_catalog('tàu')


def test_catalog_explicit_no_results_and_validation(network):
    network(lambda r: httpx.Response(200, headers={'content-type': 'text/html'}, text='<div>Không tìm thấy kết quả</div>'))
    assert service.search_catalog('unlikely')['items'] == []
    for query, kind in [('', 'all'), ('x', 'invalid'), ('x' * 201, 'all')]:
        with pytest.raises(service.IntegrationError):
            service.search_catalog(query, kind)


def test_catalog_skips_malformed_detail_urls(network):
    network(lambda r: httpx.Response(200, text='<a href="https://[invalid/">Bad URL</a><h2 onclick="parent.showPopupDetail(1967)">Safe title</h2>'))
    assert service.search_catalog('title')['items'][0]['title'] == 'Safe title'


def test_library_unconfigured_and_no_fabricated_ack(network, monkeypatch):
    monkeypatch.delenv('LIBRARY_LOANS_URL', raising=False)
    monkeypatch.delenv('LIBRARY_RENEW_URL', raising=False)
    with pytest.raises(service.IntegrationError) as error:
        service.library_loans('private-token')
    assert error.value.status_code == 503
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    network(lambda r: httpx.Response(200, json={'status': 'ok'}))
    with pytest.raises(service.IntegrationError) as error:
        service.library_renew('private-token', 'loan-1', 'key-1')
    assert error.value.uncertain


def test_library_renew_passes_key_and_reports_timeout_without_retry(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers['idempotency-key'] == 'key-1'
        assert request.headers['authorization'] == 'Bearer private-token'
        raise httpx.ReadTimeout('private upstream details')
    network(handler)
    with pytest.raises(service.IntegrationError) as error:
        service.library_renew('private-token', 'loan-1', 'key-1')
    assert len(calls) == 1 and error.value.uncertain
    assert 'private' not in str(error.value.detail)


def test_library_valid_contract(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_LOANS_URL', 'https://bridge.example/approved-loans')
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    network(lambda r: httpx.Response(200, json={'loans': [{'id': '1'}]}) if 'loans' in r.url.path else httpx.Response(200, json={'status': 'renewed', 'loan_id': '1', 'due_date': '2026-11-01'}))
    assert service.library_loans('token')['loans'][0]['id'] == '1'
    assert service.library_renew('token', '1', 'k')['status'] == 'renewed'


def test_library_loans_returns_only_safe_fields_and_normalizes_numeric_ids(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_LOANS_URL', 'https://bridge.example/approved-loans')
    network(lambda r: httpx.Response(200, json={'loans': [{'id': 42, 'loan_id': 42, 'title': {'nested': 'unsafe'}, 'book_title': 'Safe title', 'due_date': '2026-11-01', 'debug': 'private'}], 'warning': {'nested': 'unsafe'}, 'message': 'Known acknowledgement', 'private': 'must not pass'}))
    assert service.library_loans('token') == {'loans': [{'id': '42', 'loan_id': '42', 'book_title': 'Safe title', 'due_date': '2026-11-01'}], 'message': 'Known acknowledgement'}


@pytest.mark.parametrize('loan', [{'id': {'nested': 'unsafe'}}, {'id': True}, {'title': 'Missing ID'}, {'id': '42', 'due_date': 'tomorrow'}, {'id': '42', 'due_date': {'nested': 'unsafe'}}])
def test_library_loans_rejects_unusable_ids_or_dates(network, monkeypatch, loan):
    monkeypatch.setenv('LIBRARY_LOANS_URL', 'https://bridge.example/approved-loans')
    network(lambda r: httpx.Response(200, json={'loans': [loan]}))
    with pytest.raises(service.IntegrationError) as error:
        service.library_loans('token')
    assert error.value.status_code == 502


def test_library_renew_normalizes_ack_and_filters_nested_optional_data(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    network(lambda r: httpx.Response(200, json={'status': 'renewed', 'loan_id': 42, 'due_date': '2026-11-01', 'message': {'unsafe': 'nested'}, 'warning': 'w' * 2000, 'private': 'must not pass'}))
    assert service.library_renew('token', '42', 'key') == {'status': 'renewed', 'loan_id': '42', 'due_date': '2026-11-01', 'warning': 'w' * 1000}


def test_library_renew_does_not_accept_boolean_loan_id_ack(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    network(lambda r: httpx.Response(200, json={'status': 'renewed', 'loan_id': True, 'due_date': '2026-11-01'}))
    with pytest.raises(service.IntegrationError) as error:
        service.library_renew('token', 'True', 'key')
    assert error.value.uncertain


def test_library_renew_rejects_invalid_due_date(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    network(lambda r: httpx.Response(200, json={'status': 'renewed', 'loan_id': '1', 'due_date': 'tomorrow'}))
    with pytest.raises(service.IntegrationError) as error:
        service.library_renew('token', '1', 'key')
    assert error.value.uncertain


def test_library_rejects_non_ascii_header_values_before_network(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_LOANS_URL', 'https://bridge.example/approved-loans')
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    network(lambda r: pytest.fail('invalid header reached upstream'))
    with pytest.raises(service.IntegrationError) as error:
        service.library_loans('mã-truy-cập')
    assert error.value.status_code == 400
    with pytest.raises(service.IntegrationError) as error:
        service.library_renew('token', 'loan', 'khóa')
    assert error.value.status_code == 400


def test_crawl_fails_closed_on_unavailable_robots_and_limits(network):
    network(lambda r: httpx.Response(503))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages('https://library.example/')
    for count in (0, 11, True, '3'):
        with pytest.raises(service.IntegrationError) as error:
            service.crawl_pages('https://library.example/', count)
        assert error.value.status_code == 400


def test_crawl_rejects_zero_request_rate(network):
    network(lambda r: httpx.Response(200, text='User-agent: *\nRequest-rate: 0/100\n'))
    with pytest.raises(service.IntegrationError):
        service.crawl_pages('https://library.example/')


def test_library_deep_invalid_json_keeps_renewal_uncertain(network, monkeypatch):
    monkeypatch.setenv('LIBRARY_RENEW_URL', 'https://bridge.example/approved-renew')
    network(lambda r: httpx.Response(200, content=b'[' * 3000 + b']' * 3000))
    with pytest.raises(service.IntegrationError) as error:
        service.library_renew('token', 'loan', 'key')
    assert error.value.uncertain


@pytest.fixture
def webhook(monkeypatch, tmp_path):
    monkeypatch.setenv('MESSENGER_APP_SECRET', 'test-secret')
    monkeypatch.setenv('MESSENGER_VERIFY_TOKEN', 'verify')
    monkeypatch.setenv('MESSENGER_PAGE_ACCESS_TOKEN', 'test-token')
    monkeypatch.setenv('MESSENGER_PAGE_ID', 'page')
    monkeypatch.setenv('MESSENGER_GRAPH_VERSION', 'v26.0')
    monkeypatch.setenv('ZALO_APP_ID', 'app')
    monkeypatch.setenv('ZALO_OA_ID', 'oa')
    monkeypatch.setenv('ZALO_OA_SECRET_KEY', 'zalo-secret')
    monkeypatch.setenv('ZALO_ACCESS_TOKEN', 'test-token')
    database = tmp_path / 'events.sqlite'
    @contextmanager
    def db():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()
    app = FastAPI()
    app.include_router(channels.router, prefix='/api')
    answers, sends = [], []
    app.state.db = db
    app.state.answer = lambda text: answers.append(text) or {'answer': 'Tra cứu tại OPAC'}
    def handler(request):
        sends.append(request)
        return httpx.Response(200, json={'message_id': 'out', 'recipient_id': 'reader'} if request.url.host == 'graph.facebook.com' else {'error': 0, 'data': {'message_id': 'out'}})
    monkeypatch.setattr(channels, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    return TestClient(app), answers, sends


def messenger_body():
    return json.dumps({'object': 'page', 'entry': [{'id': 'page', 'messaging': [{'sender': {'id': 'reader'}, 'recipient': {'id': 'page'}, 'timestamp': int(time.time() * 1000), 'message': {'mid': 'incoming-1', 'text': 'Tra cứu'}}]}]}).encode()


def test_messenger_handshake_signature_and_persistent_dedup(webhook):
    client, answers, sends = webhook
    response = client.get('/api/webhooks/messenger', params={'hub.mode': 'subscribe', 'hub.verify_token': 'verify', 'hub.challenge': '123'})
    assert response.status_code == 200 and response.text == '123'
    raw = messenger_body()
    assert client.post('/api/webhooks/messenger', content=raw).status_code == 403
    signature = 'sha256=' + hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()
    for _ in range(2):
        assert client.post('/api/webhooks/messenger', content=raw, headers={'x-hub-signature-256': signature}).status_code == 200
    assert answers == ['Tra cứu'] and len(sends) == 1
    assert json.loads(sends[0].content)['messaging_type'] == 'RESPONSE'


def test_messenger_unicode_handshake_and_invalid_shape(webhook):
    client, answers, sends = webhook
    response = client.get('/api/webhooks/messenger', params={'hub.mode': 'subscribe', 'hub.verify_token': 'không hợp lệ', 'hub.challenge': '123'})
    assert response.status_code == 403
    raw = b'[]'
    signature = 'sha256=' + hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()
    assert client.post('/api/webhooks/messenger', content=raw, headers={'x-hub-signature-256': signature}).status_code == 400
    assert not answers and not sends


def test_messenger_ignores_echo_old_and_wrong_page(webhook):
    client, answers, sends = webhook
    payload = json.loads(messenger_body())
    for mutation in ('echo', 'old', 'page', 'oversize'):
        current = json.loads(json.dumps(payload))
        candidate = current['entry'][0]['messaging'][0]
        if mutation == 'echo':
            candidate['message']['is_echo'] = True
        elif mutation == 'old':
            candidate['timestamp'] = 1
        elif mutation == 'page':
            candidate['recipient']['id'] = 'wrong-page'
        else:
            candidate['message']['text'] = 'x' * 4001
        raw = json.dumps(current).encode()
        signature = 'sha256=' + hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()
        assert client.post('/api/webhooks/messenger', content=raw, headers={'x-hub-signature-256': signature}).status_code == 200
    assert not answers and not sends


def test_zalo_signature_and_replay(webhook):
    client, answers, sends = webhook
    stamp = str(int(time.time() * 1000))
    raw = json.dumps({'app_id': 'app', 'event_name': 'user_send_text', 'timestamp': stamp, 'sender': {'id': 'reader'}, 'recipient': {'id': 'oa'}, 'message': {'msg_id': 'z-1', 'text': 'Sách'}}).encode()
    signature = hashlib.sha256(b'app' + raw + stamp.encode() + b'zalo-secret').hexdigest()
    assert client.post('/api/webhooks/zalo', content=raw, headers={'x-zevent-signature': 'bad'}).status_code == 403
    for _ in range(2):
        assert client.post('/api/webhooks/zalo', content=raw, headers={'x-zevent-signature': 'mac=' + signature}).status_code == 200
    assert answers == ['Sách'] and len(sends) == 1


def test_channel_timeout_is_held_and_never_retried(webhook, monkeypatch):
    client, answers, _ = webhook
    sends = []
    def timeout(request):
        sends.append(request)
        raise httpx.ReadTimeout('sensitive token details')
    monkeypatch.setattr(channels, '_client', lambda: httpx.Client(transport=httpx.MockTransport(timeout)))
    raw = messenger_body()
    signature = 'sha256=' + hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()
    for _ in range(2):
        response = client.post('/api/webhooks/messenger', content=raw, headers={'x-hub-signature-256': signature})
        assert response.status_code == 200
    assert len(sends) == 1 and len(answers) == 1


def test_channel_dedup_survives_concurrent_delivery(webhook):
    from concurrent.futures import ThreadPoolExecutor
    client, answers, sends = webhook
    raw = messenger_body()
    signature = 'sha256=' + hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()
    def post(_):
        return client.post('/api/webhooks/messenger', content=raw, headers={'x-hub-signature-256': signature}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(post, range(2))) == [200, 200]
    assert len(answers) == 1 and len(sends) == 1
