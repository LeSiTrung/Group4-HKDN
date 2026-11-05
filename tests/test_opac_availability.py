import sys
from datetime import datetime
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services import opac_availability as service

URL = 'https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=5712'


def detail(count='3 / 3', identifier='5712', kind='Sách truyền thống', extra=''):
    return f'''<input id="hidItemID" value="{identifier}">
    <div class="TabbedPanelsContent"><li><span>Dạng tài liệu:</span>{kind}</li>
    <p>Số bản tài liệu rỗi:</p><span>{count}</span>{extra}</div>'''


@pytest.fixture
def network(monkeypatch):
    service._cache.clear()
    clock = [100.0]
    monkeypatch.setattr(service.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(service.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(service.network, '_public_ip', lambda _: '93.184.216.34')
    monkeypatch.setattr(service.network, '_client', lambda: pytest.fail('unexpected network request'))
    next_request=[100.0]
    def pace(**kwargs):
        service.time.sleep(max(0,next_request[0]-clock[0]))
        next_request[0]=clock[0]+10
    monkeypatch.setattr(service.network,'wait_for_turn',pace)

    def install(handler):
        monkeypatch.setattr(service.network, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False))
    return install


@pytest.mark.parametrize(('count', 'status', 'available', 'total'), [('3 / 5', 'available', 3, 5), ('0 / 3', 'unavailable', 0, 3), ('0 / 0', 'unavailable', 0, 0)])
def test_verified_aggregate_counts(network, count, status, available, total):
    def handler(request):
        assert request.method == 'GET'
        assert request.url.host == '93.184.216.34'
        assert request.headers['host'] == 'opacthuvien.ut.edu.vn'
        assert request.headers['user-agent'] == service.network.USER_AGENT
        assert request.extensions['sni_hostname'] == 'opacthuvien.ut.edu.vn'
        return httpx.Response(200, text=detail(count), headers={'content-type': 'text/html'})
    network(handler)
    result = service.get_availability(URL)
    assert (result['status'], result['available'], result['total']) == (status, available, total)
    assert result['source_url'] == URL
    assert datetime.fromisoformat(result['checked_at']).tzinfo is not None


@pytest.mark.parametrize('raw', [
    detail(identifier='99'), detail(kind='Tài liệu số'), detail('4 / 3'), detail('-1 / 3'), detail('3'),
    detail('١ / ٣'), detail().replace('Số bản tài liệu rỗi:', 'Không có số liệu:'),
    '<form>Vui lòng đăng nhập</form>', detail(extra='<p>Số bản tài liệu rỗi:</p><span>1 / 3</span>'),
    detail(extra='<p>Số bản được giữ chỗ:</p><span>4</span>'),
    '<input id="hidItemID" value="5712"><span id="spAvailable">Số bản tài liệu rỗi:</span><span>0 / 3</span>',
])
def test_unverified_pages_are_unknown_never_zero(network, raw):
    network(lambda _: httpx.Response(200, text=raw, headers={'content-type': 'text/html'}))
    result = service.get_availability(URL)
    assert result['status'] == 'unknown'
    assert result['available'] is result['total'] is None


def test_only_first_display_tab_is_read(network):
    raw = detail(extra='<p>Số bản được giữ chỗ:</p><span>0</span>')
    raw += '<div class="TabbedPanelsContent"><p>Số bản tài liệu rỗi:</p><span>99 / 99</span><p>911 private staff metadata</p></div>'
    network(lambda _: httpx.Response(200, text=raw, headers={'content-type': 'text/html'}))
    result = service.get_availability(URL)
    assert result['available'] == result['total'] == 3
    assert 'private' not in str(result)


@pytest.mark.parametrize('url', [URL + '&x=1', URL + '#x', URL.replace('5712', '0'), URL.replace('5712', '٠١'), URL.replace('5712', '05712'), URL.replace('https:', 'http:'), URL.replace('opacthuvien.ut.edu.vn', 'evil.example'), URL.replace('/opac/', '/other/'), URL.replace('.vn/', '.vn:443/'), None])
def test_rejects_noncanonical_sources_without_requests(network, url):
    with pytest.raises(service.network.IntegrationError):
        service.get_availability(url)


@pytest.mark.parametrize('status', [301, 302, 303, 307, 308, 403, 500])
def test_http_failure_or_redirect_never_follows_or_becomes_unavailable(network, status):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={'location': URL, 'content-type': 'text/html'}, text=detail('0 / 3'))
    network(handler)
    assert service.get_availability(URL)['status'] == 'unknown'
    assert len(requests) == 1


def test_timeout_unknown_and_cached(network):
    requests = []
    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout('test', request=request)
    network(handler)
    assert service.get_availability(URL)['status'] == 'unknown'
    assert service.get_availability(URL)['status'] == 'unknown'
    assert len(requests) == 1


def test_response_limit_and_content_type(network):
    network(lambda _: httpx.Response(200, content=b'x' * (service.network.MAX_BYTES + 1), headers={'content-type': 'text/html'}))
    assert service.get_availability(URL)['status'] == 'unknown'
    service._cache.clear()
    network(lambda _: httpx.Response(200, text=detail(), headers={'content-type': 'application/json'}))
    assert service.get_availability(URL)['status'] == 'unknown'


def test_cache_expiry_copy_and_global_pacing(network):
    times = []
    def handler(request):
        times.append(service.time.monotonic())
        identifier = request.url.params['intItemId']
        return httpx.Response(200, text=detail(identifier=identifier), headers={'content-type': 'text/html'})
    network(handler)
    first = service.get_availability(URL)
    first['available'] = 999
    assert service.get_availability(URL)['available'] == 3
    service.get_availability(URL.replace('5712', '5713'))
    assert times == [100.0, 110.0]
    service.time.sleep(61)
    service.get_availability(URL)
    assert len(times) == 3


def test_cache_entry_count_is_bounded(network, monkeypatch):
    monkeypatch.setattr(service.time, 'sleep', lambda _: None)
    network(lambda request: httpx.Response(200, text=detail(identifier=request.url.params['intItemId']), headers={'content-type': 'text/html'}))
    for identifier in range(1, 131):
        service.get_availability(URL.replace('5712', str(identifier)))
    assert len(service._cache) == 128
    assert URL.replace('5712', '1') not in service._cache


def test_dns_rejection_remains_unknown_without_http(network, monkeypatch):
    def reject(_):
        raise service.network.IntegrationError('private address')
    monkeypatch.setattr(service.network, '_public_ip', reject)
    network(lambda _: pytest.fail('private address must not be requested'))
    assert service.get_availability(URL)['status'] == 'unknown'
