from pathlib import Path
from runpy import run_path

import httpx
import pytest

from app.services import integrations as network

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/collect_opac.py'


@pytest.fixture
def source(monkeypatch,tmp_path):
    module=run_path(str(SCRIPT))
    calls=[]
    sleeps=[]
    monkeypatch.setattr(network,'_public_ip',lambda _: '93.184.216.34')
    monkeypatch.setattr(network,'wait_for_turn',lambda **kwargs:None)
    monkeypatch.setattr(module['time'],'sleep',sleeps.append)
    return module,calls,sleeps


def test_transient_get_transport_failure_retries_with_bounded_backoff(source,tmp_path,monkeypatch):
    module,calls,sleeps=source
    def handler(request):
        calls.append(request.url.path)
        if len(calls)<3:
            raise httpx.ReadTimeout('private diagnostic')
        return httpx.Response(200,text='User-agent: *\nDisallow: /')
    monkeypatch.setattr(network,'_client',lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    result=module['collect'](tmp_path,categories=['1'])
    assert result['blocked']=='robots_disallowed_requires_explicit_operator_acknowledgement'
    assert calls==['/robots.txt']*3 and sleeps==[30,60]
    assert result['transport_retries']==2


def test_persistent_transport_failure_stops_after_three_attempts(source,tmp_path,monkeypatch):
    module,calls,sleeps=source
    def handler(request):
        calls.append(request.url.path)
        raise httpx.ConnectError('private connection details')
    monkeypatch.setattr(network,'_client',lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    result=module['collect'](tmp_path,categories=['1'])
    assert result['blocked']=='safe_network_error' and not result['complete']
    assert len(calls)==3 and sleeps==[30,60]
    assert result['failure']['status_code']==502
    assert 'private' not in str(result['failure'])


@pytest.mark.parametrize('status',[401,403,429,500,503])
def test_http_refusal_is_never_retried(source,tmp_path,monkeypatch,status):
    module,calls,sleeps=source
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(status)
    monkeypatch.setattr(network,'_client',lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    result=module['collect'](tmp_path,categories=['1'])
    assert result['blocked']=='source_http_'+str(status)
    assert len(calls)==1 and not sleeps


def test_get_flag_never_authorizes_retrying_transactions(source,monkeypatch):
    _,_,_=source
    def timeout(request):
        raise httpx.ReadTimeout('private')
    monkeypatch.setattr(network,'_client',lambda:httpx.Client(transport=httpx.MockTransport(timeout)))
    for method,retryable in [('GET',True),('POST',False)]:
        with network._client() as client,pytest.raises(network.IntegrationError) as error:
            network._fetch(client,network.OPAC,{'opacthuvien.ut.edu.vn'},method=method)
        assert error.value.retryable is retryable
