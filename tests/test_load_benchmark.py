import pytest

from scripts.benchmark_load import loopback_url, summarize


@pytest.mark.parametrize('url',[
    'https://library.example/', 'http://127.0.0.1.evil.test',
    'http://user:secret@127.0.0.1:8000', 'http://127.0.0.1:8000/api',
    'http://127.0.0.1:8000?token=secret', 'http://127.0.0.1:8000/#chat',
])
def test_load_test_rejects_non_loopback_or_credential_urls(url):
    with pytest.raises(ValueError):
        loopback_url(url)


def test_load_summary_counts_wrong_answers_and_rate_limits_as_failures():
    rows=[{'elapsed_ms':10,'http_status':200,'ok':True,'mode':'faq'},
          {'elapsed_ms':30,'http_status':200,'ok':False,'mode':'fallback'},
          {'elapsed_ms':20,'http_status':429,'ok':False,'mode':None}]
    result=summarize(rows,2)
    assert result['requests']==3 and result['successful']==1 and result['failed']==2
    assert result['http_statuses']=={'200':2,'429':1}
    assert result['modes']=={'faq':1,'fallback':1}
    assert result['p50_ms']==20 and result['p95_ms']==29
    assert result['requests_per_second']==1.5
